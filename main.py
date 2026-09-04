import os
import asyncio
import json
import re
import requests
from datetime import datetime
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from pydantic_ai import Agent
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider
from models import WoningLijst, Woning 

# Externe configuratie
from prompts import VERKENNER_SYSTEM_PROMPT, TAXATEUR_SYSTEM_PROMPT
from makelaars import MAKELAARS

load_dotenv()

# --- CONFIGURATIE ---
MEMORY_FILE = "gezien_huizen.json"
provider = GoogleProvider(api_key=os.getenv('GEMINI_API_KEY'))

CASCADE_MODELS = [
    'gemini-pro-latest',
    'gemini-flash-latest',
    'gemini-flash-lite-latest',
    'gemini-3.5-flash',
    'gemini-3.5-flash-lite'
]

# --- GEHEUGEN LOGICA ---
def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, 'r') as f:
                return json.load(f)
        except: return {}
    return {}

def save_memory(memory):
    with open(MEMORY_FILE, 'w') as f:
        json.dump(memory, f, indent=4)

# --- TELEGRAM NOTIFICATIE LOGICA ---
def stuur_telegram_notificatie(adres, score, motivatie, url):
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print("⚠️ Telegram configuratie ontbreekt in .env of secrets.")
        return
    
    # Telegram gebruikt Markdown voor dikgedrukte tekst (*)
    bericht = f"🌟 *Nieuwe Match in Apeldoorn!*\n\n🏠 {adres}\n⭐ Score: {score}/10\n\n💡 {motivatie}\n\n🔗 {url}"
    
    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": bericht,
        "parse_mode": "Markdown"
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
async def cascade_run(agent_factory, prompt):
    last_error = None
    for model_name in CASCADE_MODELS:
        model = GoogleModel(model_name, provider=provider)
        agent = agent_factory(model)
        retries, max_retries, wachttijd = 0, 2, 2
        
        print(f"🤖 Poging met model: {model_name}...")
        while retries <= max_retries:
            try:
                return await agent.run(prompt)
            except Exception as e:
                err = str(e).lower()
                if any(msg in err for msg in ["503", "high demand", "unavailable"]):
                    retries += 1
                    await asyncio.sleep(wachttijd)
                    wachttijd *= 2
                    continue
                elif "429" in err or "quota" in err:
                    print(f"   🚫 Quota bereikt voor {model_name}. Volgende...")
                    break 
                else: raise e
        last_error = f"Laatste model {model_name} faalde."
    raise Exception(f"Model Cascade volledig uitgeput. {last_error}")

# --- AGENT FACTORIES ---
def get_verkenner(model):
    return Agent(model, output_type=WoningLijst, system_prompt=VERKENNER_SYSTEM_PROMPT)

def get_taxateur(model):
    return Agent(model, output_type=Woning, system_prompt=TAXATEUR_SYSTEM_PROMPT)

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
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            text, links = "", []
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

            if not is_detail:
                for a in soup.find_all('a', href=True):
                    href = a['href'].strip()
                    if not href or any(n in href.lower() for n in ['facebook', 'linkedin', 'instagram', 'funda.nl', 'google']): 
                        continue

                    is_internal = any(x in href for x in ['/wonen/aanbod/', '/woningen/', '/aanbod/', '/woning/', '/woningaanbod/', '/koopwoningen/'])
                    is_external = href.startswith('http') and base_url.split('//')[-1].split('/')[0] not in href
                    
                    if is_internal or is_external:
                        full_url = href if href.startswith('http') else f"{base_url.rstrip('/')}/{href.lstrip('/')}"
                        if full_url not in links: links.append(full_url)

            print(f"   📊 Eindresultaat: {len(text)} tekens en {len(links)} links.")
            await browser.close()
            return text, links

        except Exception as e:
            print(f"⚠️ Fout bij {url}: {e}")
            await browser.close()
            return "", []

# --- MAIN LOOP ---
async def main():
    geheugen = load_memory()
    eind_resultaat = []
    nieuwe_scans = False

    for m in MAKELAARS:
        print(f"\n--- SCAN START: {m['naam']} ---")
        ruwe_tekst, gevonden_links = await scrape_url(m['url'], m['base'])
        
        if len(ruwe_tekst) < 500:
            print(f"❌ Content bleef te summier voor {m['naam']}. Mogelijk sterke blokkade.")
            continue

        try:
            res_verkenner = await cascade_run(
                get_verkenner, 
                f"Analyseer aanbod van {m['naam']}.\nTekst: {ruwe_tekst[:25000]}\nURLs: {gevonden_links}"
            )
            
            print(f"   ✅ Verkenner vond {len(res_verkenner.output.woningen)} woningen.")
            
            for woning in res_verkenner.output.woningen:
                if not woning.url or woning.url in geheugen:
                    if woning.url in geheugen: print(f"⏩ Bekend: {woning.adres}")
                    continue

                print(f"🔎 Deep Scan: {woning.adres}")
                details, _ = await scrape_url(woning.url, m['base'], is_detail=True)
                
                if len(details) > 1000:
                    try:
                        check = await cascade_run(get_taxateur, f"Beoordeel deze woning: {details[:30000]}")
                        woning_data = check.output
                        woning_data.url = woning.url 
                        
                        geheugen[woning.url] = {
                            "adres": woning_data.adres, "score": woning_data.match_score,
                            "motivatie": woning_data.motivatie, "buurt": woning_data.buurt,
                            "prijs": woning_data.prijs, "datum": datetime.now().strftime("%Y-%m-%d %H:%M")
                        }
                        nieuwe_scans = True
                        eind_resultaat.append(woning_data)

                        # --- TELEGRAM TRIGGER ---
                        if woning_data.match_score >= 8:
                            # Stuur Telegram
                            stuur_telegram_notificatie(
                                woning_data.adres, 
                                woning_data.match_score, 
                                woning_data.motivatie, 
                                woning_data.url
                            )

                        await asyncio.sleep(1) # API beleefdheidspauze
                    except Exception as e:
                        print(f"❌ Analyse mislukt voor {woning.adres}: {e}")
                else:
                    print(f"⚠️ Detailpagina van {woning.adres} kon niet gelezen worden.")
        except Exception as e:
            print(f"❌ Fout bij verwerken lijst {m['naam']}: {e}")

    if nieuwe_scans:
        save_memory(geheugen)
        print("--- Geheugen bijgewerkt met nieuwe resultaten. ---")

    print("\n" + "="*50 + "\nNIEUWE RESULTATEN VANDAAG\n" + "="*50)
    
    unieke_matches = {res.url: res for res in eind_resultaat}.values()
    
    if not unieke_matches:
        print("Geen nieuwe woningen gevonden die aan je Woon-DNA voldoen.")
    else:
        for res in sorted(unieke_matches, key=lambda x: x.match_score, reverse=True):
            print(f"🌟 {res.adres} - SCORE: {res.match_score}/10")
            print(f"   💡 {res.motivatie}")
            print(f"   🔗 {res.url}\n")

if __name__ == "__main__":
    asyncio.run(main())