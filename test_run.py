import os
import asyncio
from dotenv import load_dotenv

from memory import laad_profielen
from scraper import scrape_url
from agents import cascade_run, get_taxateur
from services import stuur_telegram_notificatie, evalueer_en_selecteer_locatie
from prompts import genereer_taxateur_prompt

load_dotenv()

async def draai_test():
    profielen = laad_profielen()
    if not profielen:
        print("❌ Geen profielen gevonden.")
        return

    # Definieer een handige test-URL per regio/profiel om snel te testen
    test_cases = {
        "apeldoorn": "https://www.tenhag.nl/huis/gunninglaan-43-apeldoorn",
        "harderwijk_ermelo": "https://randmeermakelaars.nl/aanbod-detail/woningaanbod/harderwijk/24747-israelstraat-3/" # Vervang dit even door een actieve test-URL uit de regio Harderwijk/Ermelo
    }

    for profiel in profielen:
        profiel_id = profiel['id']
        test_url = test_cases.get(profiel_id)
        
        if not test_url or "funda.nl" in test_url and "Vervang" in test_url:
            print(f"⚠️ Geen geldige test-URL geconfigureerd voor {profiel['naam']} ({profiel_id}). Sla over.")
            continue

        print(f"\n" + "="*50)
        print(f"🧪 START TEST VOOR: {profiel['naam']} ({profiel['regio']})")
        print(f"🔗 Test-URL: {test_url}")
        print("="*50)

        # 1. Scrape de details van de testwoning
        print("📥 Bezig met ophalen van woningdetails...")
        details, _, _ = await scrape_url(test_url, "", is_detail=True)
        
        if len(details) < 500:
            print(f"❌ Scrape mislukt of te weinig content voor {test_url}.")
            continue

        # 2. Genereer de juiste prompt op basis van het profiel
        taxateur_sys_prompt = genereer_taxateur_prompt(profiel)

        # 3. Laat de taxateur-agent los op de tekst
        print("🤖 Taxateur-agent aan het werk zetten...")
        try:
            check = await cascade_run(
                get_taxateur, 
                taxateur_sys_prompt, 
                f"Beoordeel deze woning: {details[:30000]}"
            )
            woning_data = check.output
            woning_data.url = test_url

            # 4. Voer de Google Maps locatie-check uit
            locatie_info_telegram = ""
            if os.getenv("GOOGLE_MAPS_API_KEY"):
                print(f"📍 Locatie verifiëren via Google Maps voor: {woning_data.adres}...")
                is_valid, afstand_centrum, afstand_supermarkt, locatie_info_telegram = evalueer_en_selecteer_locatie(woning_data.adres, profiel['id'])
                
                if not is_valid:
                    print(f" 🛑 Waarschuwing: Woning valt buiten de ingestelde straal volgens de Maps check.")
                else:
                    print(f" ✅ Locatie goedgekeurd. Centrum: {afstand_centrum:.1f} km | Supermarkt: {afstand_supermarkt:.1f} km")

            # 5. Print het resultaat in de console
            print("\n" + "-"*30 + " TEST RESULTAAT " + "-"*30)
            print(f"Adres : {woning_data.adres}")
            print(f"Score : {woning_data.match_score}/10")
            print(f"Prijs : {woning_data.prijs}")
            print(f"Motivatie:\n{woning_data.motivatie}")
            print("-" * 76)

            # 6. Optioneel: Stuur direct een test-Telegrambericht om dat ook te verifiëren
            stuur_telegram = input("📲 Wil je hiervan een test-Telegramnotificatie sturen? (j/n): ").strip().lower()
            if stuur_telegram == 'j':
                stuur_telegram_notificatie(
                    woning_data.adres, 
                    woning_data.match_score, 
                    woning_data.motivatie, 
                    woning_data.url,
                    profiel['regio'],
                    profiel.get('telegram_chat_id'),
                    locatie_info=locatie_info_telegram
                )
                print("🚀 Telegram-notificatie verzonden!")

        except Exception as e:
            print(f"❌ Fout tijdens testanalyse: {e}")

if __name__ == "__main__":
    asyncio.run(draai_test())