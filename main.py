import os
import asyncio
import requests
from datetime import datetime
from dotenv import load_dotenv
from pydantic_ai import BinaryContent

# Externe modules & configuratie
from memory import laad_profielen, laad_geheugen, sla_geheugen_op
from scraper import scrape_url
from agents import cascade_run, get_verkenner, get_taxateur, get_vision_agent
from services import stuur_telegram_notificatie, bereken_loopafstand
from prompts import genereer_verkenner_prompt, genereer_taxateur_prompt, genereer_vision_prompt
from makelaars import MAKELAARS

load_dotenv()

# --- MAIN LOOP ---
async def main():
    profielen = laad_profielen()
    
    if not profielen:
        print("❌ Geen actieve profielen ingeladen. Script stopt.")
        return

    # Laad het gecentraliseerde geheugen in
    volledig_geheugen = laad_geheugen()
    wijzigingen_gemaakt = False

    for profiel in profielen:
        profiel_id = profiel['id']
        
        # Maak een eigen sectie aan in het geheugen als dit profiel nog niet bestaat
        if profiel_id not in volledig_geheugen:
            volledig_geheugen[profiel_id] = {}
            
        profiel_geheugen = volledig_geheugen[profiel_id]

        print(f"\n" + "="*50)
        print(f"🚀 START ZOEKTOCHT VOOR PROFIEL: {profiel['naam']} ({profiel['regio']})")
        print("="*50)

        eind_resultaat = []
        makelaars_lijst = MAKELAARS.get(profiel['regio'], [])
        
        if not makelaars_lijst:
            print(f"❌ Geen makelaars gevonden in makelaars.py voor regio: {profiel['regio']}")
            continue

        verkenner_sys_prompt = genereer_verkenner_prompt(profiel)
        taxateur_sys_prompt = genereer_taxateur_prompt(profiel)

        for m in makelaars_lijst:
            print(f"\n--- SCAN START: {m['naam']} ---")
            ruwe_tekst, gevonden_links, _ = await scrape_url(m['url'], m['base'])
            
            if len(ruwe_tekst) < 500:
                print(f"❌ Content bleef te summier voor {m['naam']}.")
                continue

            try:
                res_verkenner = await cascade_run(
                    get_verkenner, 
                    verkenner_sys_prompt,
                    f"Analyseer aanbod van {m['naam']}.\nTekst: {ruwe_tekst[:25000]}\nURLs: {gevonden_links}"
                )
                
                print(f"   ✅ Verkenner vond {len(res_verkenner.output.woningen)} woningen.")
                
                for woning in res_verkenner.output.woningen:
                    if not woning.url or woning.url in profiel_geheugen:
                        if woning.url in profiel_geheugen: 
                            print(f"⏩ Bekend in geheugen van {profiel['naam']}: {woning.adres}")
                        continue

                    print(f"🔎 Deep Scan: {woning.adres}")
                    details, _, foto_url = await scrape_url(woning.url, m['base'], is_detail=True)
                    
                    if len(details) > 1000:
                        try:
                            check = await cascade_run(
                                get_taxateur, 
                                taxateur_sys_prompt, 
                                f"Beoordeel deze woning: {details[:30000]}"
                            )
                            woning_data = check.output
                            woning_data.url = woning.url

                            # --- VISION CHECK: Alleen bij hoge scores en als er een foto is ---
                            if woning_data.match_score >= 7 and foto_url:
                                print(f"👁️ Hoge tekst-score ({woning_data.match_score})! Foto visueel keuren...")
                                try:
                                    img_resp = requests.get(foto_url, timeout=10)
                                    if img_resp.status_code == 200:
                                        vision_prompt = genereer_vision_prompt(profiel)
                                        foto_input = [
                                            "Beoordeel deze foto aan de hand van je instructies.",
                                            BinaryContent(data=img_resp.content, media_type='image/jpeg')
                                        ]
                                        vision_check = await cascade_run(get_vision_agent, vision_prompt, foto_input)
                                        
                                        v_score = vision_check.output.score_aanpassing
                                        v_motivatie = vision_check.output.vision_motivatie
                                        
                                        # Toepassen en begrenzen op 10
                                        nieuwe_score = min(10, woning_data.match_score + v_score)
                                        
                                        # Motivatie samenvoegen
                                        woning_data.motivatie = f"{woning_data.motivatie}\n\n📸 <b>Vision Check:</b> {v_motivatie} (Score aanpassing: {v_score})"
                                        woning_data.match_score = nieuwe_score
                                        print(f"   📸 Foto beoordeeld: {v_score} punten. Nieuwe score: {nieuwe_score}/10")
                                except Exception as e:
                                    print(f"⚠️ Vision check mislukt voor {woning.adres}: {e}")

                            # --- LOCATIE CHECK VIA GOOGLE MAPS ---
                            locatie_info_telegram = ""
                            if woning_data.match_score >= 7 and os.getenv("GOOGLE_MAPS_API_KEY"):
                                print(f"📍 Hoge tekst-score ({woning_data.match_score})! Loopafstand naar centrum berekenen...")
                                
                                # Slim de juiste stad bepalen voor het centrum
                                stad = "Apeldoorn" if "apeldoorn" in profiel['regio'].lower() else ""
                                if "ermelo" in woning_data.adres.lower(): stad = "Ermelo"
                                elif "harderwijk" in woning_data.adres.lower(): stad = "Harderwijk"
                                
                                bestemming = f"Centrum {stad}" if stad else "Centrum"
                                
                                afstand_txt, duur_txt, minuten = bereken_loopafstand(woning_data.adres, bestemming)
                                
                                if minuten is not None:
                                    locatie_info_telegram = f"\n🚶 <b>Locatie:</b> {afstand_txt} naar {bestemming} ({duur_txt} lopen)"
                                    
                                    # Strenge aftrek alleen voor je moeder als het te ver is
                                    if profiel['id'] == "moeder_harderwijk_ermelo" and minuten > 15:
                                        woning_data.match_score -= 2
                                        woning_data.motivatie = f"📍 <b>Locatie penalty:</b> Het is {duur_txt} ({afstand_txt}) lopen naar {bestemming}. Dat is te ver.\n\n" + woning_data.motivatie
                                        print(f"   🚶 Te ver ({int(minuten)} min). Score -2. Nieuwe score: {woning_data.match_score}/10")
                                    else:
                                        print(f"   🚶 Loopafstand berekend voor {profiel['naam']}: {duur_txt} ({afstand_txt}).")

                            profiel_geheugen[woning.url] = {
                                "adres": woning_data.adres, "score": woning_data.match_score,
                                "motivatie": woning_data.motivatie, "buurt": woning_data.buurt,
                                "prijs": woning_data.prijs, "datum": datetime.now().strftime("%Y-%m-%d %H:%M")
                            }
                            wijzigingen_gemaakt = True
                            eind_resultaat.append(woning_data)

                            if woning_data.match_score >= 8:
                                stuur_telegram_notificatie(
                                    woning_data.adres, 
                                    woning_data.match_score, 
                                    woning_data.motivatie, 
                                    woning_data.url,
                                    profiel['regio'],
                                    profiel.get('telegram_chat_id'),
                                    locatie_info=locatie_info_telegram
                                )

                            await asyncio.sleep(1)
                        except Exception as e:
                            print(f"❌ Analyse mislukt voor {woning.adres}: {e}")
                    else:
                        print(f"⚠️ Detailpagina van {woning.adres} kon niet gelezen worden.")
            except Exception as e:
                print(f"❌ Fout bij verwerken lijst {m['naam']}: {e}")

        print("\n" + "-"*40 + f"\nRESULTATEN VOOR {profiel['naam'].upper()}\n" + "-"*40)
        unieke_matches = {res.url: res for res in eind_resultaat}.values()
        
        if not unieke_matches:
            print("Geen nieuwe woningen gevonden die aan het Woon-DNA voldoen.")
        else:
            for res in sorted(unieke_matches, key=lambda x: x.match_score, reverse=True):
                print(f"🌟 {res.adres} - SCORE: {res.match_score}/10")
                print(f"   💡 {res.motivatie}")
                print(f"   🔗 {res.url}\n")

    # Opslaan van het totale geheugen als er bij minstens 1 profiel iets is gewijzigd
    if wijzigingen_gemaakt:
        sla_geheugen_op(volledig_geheugen)
        print("\n--- Gecentraliseerd geheugen (huizen_gezien.json) bijgewerkt met nieuwe resultaten. ---")

if __name__ == "__main__":
    asyncio.run(main())