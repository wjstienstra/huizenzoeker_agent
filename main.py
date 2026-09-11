import os
import asyncio
from datetime import datetime
from dotenv import load_dotenv

# Externe modules & configuratie
from memory import laad_profielen, laad_geheugen, sla_geheugen_op
from scraper import scrape_url
from agents import cascade_run, get_verkenner, get_taxateur
from services import stuur_telegram_notificatie, evalueer_en_selecteer_locatie
from prompts import genereer_verkenner_prompt, genereer_taxateur_prompt
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
                    details, _, _ = await scrape_url(woning.url, m['base'], is_detail=True)
                    
                    if len(details) > 1000:
                        try:
                            check = await cascade_run(
                                get_taxateur, 
                                taxateur_sys_prompt, 
                                f"Beoordeel deze woning: {details[:30000]}"
                            )
                            woning_data = check.output
                            woning_data.url = woning.url

                            # --- LOCATIE CHECK & HARD RADIUS FILTER ---
                            locatie_info_telegram = ""
                            afstand_centrum = 0.0
                            if os.getenv("GOOGLE_MAPS_API_KEY"):
                                print(f"📍 Locatie verifiëren via Google Maps voor: {woning_data.adres}...")
                                # Aangenomen dat evalueer_en_selecteer_locatie nu ook de supermarkt meeneemt en teruggeeft:
                                # (is_valid, afstand_centrum, afstand_supermarkt, locatie_info_telegram)
                                is_valid, afstand_centrum, afstand_supermarkt, locatie_info_telegram = evalueer_en_selecteer_locatie(woning_data.adres, profiel['id'])
                                
                                if not is_valid:
                                    print(f" 🛑 Woning overschrijdt de maximale straal en is genegeerd.")
                                    continue 
                                    
                                # Lineaire score-aftrek als de dichtstbijzijnde kern te ver weg is (ruimer opgesteld, bijv. > 3.0 km)
                                if afstand_centrum > 3.0:
                                    strafpunten = int((afstand_centrum - 3.0) * 1.5)
                                    if strafpunten > 0:
                                        woning_data.match_score = max(1, woning_data.match_score - strafpunten)
                                        woning_data.motivatie = f"📍 <b>Afstands-penalty:</b> {afstand_centrum:.1f} km van het centrum (-{strafpunten} punten).\n\n" + woning_data.motivatie
                                        print(f" 🚶 Afstand tot centrum is {afstand_centrum:.1f} km. Score verlaagd met {strafpunten} punten. Nieuwe score: {woning_data.match_score}/10")

                            # --- OPSLAAN IN GEHEUGEN & NOTIFICATIE ---
                            profiel_geheugen[woning.url] = {
                                "adres": woning_data.adres, 
                                "score": woning_data.match_score,
                                "motivatie": woning_data.motivatie, 
                                "buurt": woning_data.buurt,
                                "prijs": woning_data.prijs, 
                                "datum": datetime.now().strftime("%Y-%m-%d %H:%M")
                            }
                            wijzigingen_gemaakt = True
                            eind_resultaat.append(woning_data)

                            # Dynamische drempel per profiel voor Telegram notificaties (geen supermarkt-filter, puur informatief)
                            drempel_score = 7.5 if profiel['id'] == 'apeldoorn' else 7.0

                            if woning_data.match_score >= drempel_score:
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