import os
import asyncio
import json
import re
import requests
from datetime import datetime
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from pydantic_ai import Agent, BinaryContent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider


# Externe configuratie
from models import WoningLijst, Woning, VisionBeoordeling 
from prompts import genereer_verkenner_prompt, genereer_taxateur_prompt, genereer_vision_prompt
from makelaars import MAKELAARS

load_dotenv()

# --- CONFIGURATIE ---
MEMORY_FILE = "huizen_gezien.json"

provider = GoogleProvider(api_key=os.getenv('GEMINI_API_KEY'))

CASCADE_MODELS = [
    'gemini-pro-latest',
    'gemini-flash-latest',
    'gemini-flash-lite-latest',
    'gemini-3.5-flash',
    'gemini-3.5-flash-lite'
]

# --- PROFIELEN LOGICA ---
def laad_profielen():
    if not os.path.exists('profielen.json'):
        print("❌ Kan profielen.json niet vinden. Zorg dat het bestand bestaat.")
        return []
    try:
        with open('profielen.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ Fout bij het inlezen van profielen.json: {e}")
        return []

# --- GECENTRALISEERDE GEHEUGEN LOGICA ---
def laad_geheugen():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Fout bij het inlezen van geheugen ({MEMORY_FILE}): {e}")
            return {}
    return {}

def sla_geheugen_op(geheugen):
    with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(geheugen, f, indent=4)

# --- TELEGRAM NOTIFICATIE LOGICA ---
def stuur_telegram_notificatie(adres, score, motivatie, url, regio, profiel_chat_id):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    
    # Fallback: Als in profielen.json een dummy-waarde staat, gebruik dan de .env variabele
    chat_id = profiel_chat_id if profiel_chat_id and "JOUW_" not in profiel_chat_id else os.getenv("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print("⚠️ Telegram configuratie ontbreekt in .env of profielen.json.")
        return
    
    # HTML is veel veiliger dan Markdown, omdat underscores in URLs niet meer crashen
    bericht = f"🌟 <b>Nieuwe Match in {regio}!</b>\n\n🏠 {adres}\n⭐ Score: {score}/10\n\n💡 {motivatie}\n\n🔗 {url}"
    
    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": bericht,
        "parse_mode": "HTML"
    }
    
    try:
        response = requests.post(api_url, json=payload)
        if response.status_code == 200:
            print(f"📱 ✅ Telegram notificatie verstuurd voor {adres}")
        else:
            print(f"📱 ❌ Fout bij versturen Telegram: {response.text}")
    except Exception as e:
        print(f"📱 ❌ Telegram API error: {e}")

# --- DE CASCADE RUNNER ---
async def cascade_run(agent_factory, system_prompt, user_prompt):
    last_error = None
    for model_naam in CASCADE_MODELS:
        model = GoogleModel(model_naam, provider=provider)
        agent = agent_factory(model, system_prompt)
        retries, max_retries, wachttijd = 0, 2, 2
        
        print(f"🤖 Poging met model: {model_naam}...")
        while retries <= max_retries:
            try:
                return await agent.run(user_prompt)
            except Exception as e:
                err = str(e).lower()
                if any(msg in err for msg in ["503", "high demand", "unavailable"]):
                    retries += 1
                    await asyncio.sleep(wachttijd)
                    wachttijd *= 2
                    continue
                elif "429" in err or "quota" in err:
                    print(f"   🚫 Quota bereikt voor {model_naam}. Volgende...")
                    break 
                else: 
                    raise e
        last_error = f"Laatste model {model_naam} faalde."
    raise Exception(f"Model Cascade volledig uitgeput. {last_error}")

# --- AGENT FACTORIES ---
def get_verkenner(model, system_prompt):
    return Agent(model, output_type=WoningLijst, system_prompt=system_prompt)

def get_taxateur(model, system_prompt):
    return Agent(model, output_type=Woning, system_prompt=system_prompt)

def get_vision_agent(model, system_prompt):
    return Agent(model, output_type=VisionBeoordeling, system_prompt=system_prompt)

# --- DE ROBUUSTE UNIVERSELE SCRAPER ---
async def scrape_url(url, base_url, is_detail=False):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080}
        )
        page = await context.new_page()
        
        try:
            print(f"Browsen naar: {url}...")
            # Aangepast naar networkidle voor de tragere RealWorks sites
            await page.goto(url, wait_until="networkidle", timeout=60000)
            
            text, links, hoofd_foto_url = "", [], None
            
            for attempt in range(3):
                try:
                    cookie_buttons = page.get_by_role("button", name=re.compile("accepteer|akkoord|ok|cookies", re.IGNORECASE))
                    if await cookie_buttons.count() > 0:
                        await cookie_buttons.first.click()
                        await asyncio.sleep(1)
                except: pass

                await page.mouse.wheel(0, 1000)
                await asyncio.sleep(2 + attempt) 
                
                content = await page.content()
                soup = BeautifulSoup(content, 'html.parser')
                target = soup.find('main') or soup.find('article') or soup.body
                text = target.get_text(separator=' ', strip=True) if target else ""
                
                if len(text) > 500:
                    break
                print(f"   ⏳ Pagina lijkt nog leeg ({len(text)} tekens), geduld (poging {attempt+1}/3)...")

            # --- NIEUW: FOTO VANGEN OP DETAILPAGINA ---
            if is_detail:
                meta_image = soup.find('meta', property='og:image')
                if meta_image and meta_image.get('content'):
                    hoofd_foto_url = meta_image['content']
                    # Zorg dat het een volledige link is
                    if hoofd_foto_url.startswith('/'):
                        hoofd_foto_url = base_url.rstrip('/') + hoofd_foto_url

            # Filter en verzamel links
            if not is_detail:
                for a in soup.find_all('a', href=True):
                    href = a['href'].strip()
                    # .pdf en .jpg toegevoegd aan uitsluitingen
                    if not href or any(n in href.lower() for n in ['facebook', 'linkedin', 'instagram', 'funda.nl', 'google', '.pdf', '.jpg']): 
                        continue

                    is_internal = any(x in href for x in ['/wonen/aanbod/', '/woningen/', '/aanbod/', '/woning/', '/woningaanbod/', '/koopwoningen/'])
                    is_external = href.startswith('http') and base_url.split('//')[-1].split('/')[0] not in href
                    
                    if is_internal or is_external:
                        full_url = href if href.startswith('http') else f"{base_url.rstrip('/')}/{href.lstrip('/')}"
                        if full_url not in links: links.append(full_url)

            print(f"   📊 Eindresultaat: {len(text)} tekens. Foto gevonden: {'Ja' if hoofd_foto_url else 'Nee'}")
            await browser.close()
            # We sturen nu 3 variabelen terug!
            return text, links, hoofd_foto_url

        except Exception as e:
            print(f"⚠️ Fout bij {url}: {e}")
            await browser.close()
            return "", [], None

# --- MAIN LOOP ---
async def main():
    profielen = laad_profielen()
    
    if not profielen:
        print("❌ Geen profielen ingeladen. Script stopt.")
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
                                    profiel.get('telegram_chat_id')
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