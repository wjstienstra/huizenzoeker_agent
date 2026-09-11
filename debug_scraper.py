import asyncio
import re
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

async def debug_scrape(url, base_url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080}
        )
        page = await context.new_page()
        
        try:
            print(f"🔍 Navigating to: {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(4)
            
            # Screenshot opslaan voor visuele check
            await page.screenshot(path="debug_screenshot.png")
            print("📸 Screenshot saved as 'debug_screenshot.png'.")
            
            # Cookies proberen weg te klikken
            for selector_text in ["accepteer", "akkoord", "alles akkoord", "cookies", "toestaan"]:
                try:
                    cookie_btn = page.get_by_role("button", name=re.compile(selector_text, re.IGNORECASE))
                    if await cookie_btn.count() > 0 and await cookie_btn.first.is_visible():
                        await cookie_btn.first.click()
                        await asyncio.sleep(1.5)
                        break
                except:
                    pass

            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            target = soup.find('main') or soup.find('article') or soup.body
            text = target.get_text(separator=' ', strip=True) if target else ""
            print(f"📄 Page Title: {page.title()}")
            print(f"📏 Total HTML length: {len(content)} characters")

            # Links filteren logica
            domain = base_url.split('//')[-1].split('/')[0]
            links = []
            for a in soup.find_all('a', href=True):
                href = a['href'].strip()
                if not href or any(n in href.lower() for n in ['facebook', 'linkedin', 'instagram', 'funda.nl', 'google', '.pdf', '.jpg', 'mailto:', 'tel:', 'login', 'inschrijven']): 
                    continue

                full_url = href if href.startswith('http') else f"{base_url.rstrip('/')}/{href.lstrip('/')}"
                clean_url = full_url.split('?')[0].rstrip('/')

                if domain in clean_url and 'page/' not in clean_url.lower():
                    path = clean_url.lower()
                    is_woning_pad = any(x in path for x in ['woning', 'aanbod', 'koop', 'pand', 'object', 'details', 'huis', '/woningaanbod/koop/'])
                    is_menu_categorie = any(c in path for c in ['/consument', '/bedrijf', '/bestaand/', '/starterswoningen', '/huur', '/aankoop', '/verkoop', 'neem-contact-op'])
                    
                    if is_woning_pad and not is_menu_categorie and clean_url != base_url.rstrip('/'):
                        if clean_url not in links: 
                            links.append(clean_url)

            print(f"\n--- Gevonden schone object-links ({len(links)}) ---")
            for link in links:
                print(link)

            await browser.close()
        except Exception as e:
            print(f"⚠️ Fout bij debuggen: {e}")
            await browser.close()

if __name__ == "__main__":
    # Pas hier simpelweg de URL aan van de makelaar die je wilt testen
    test_url = "https://www.nijeborghmakelaardij.nl/woningaanbod/koop/"
    base_url = "https://www.nijeborghmakelaardij.nl/"
    asyncio.run(debug_scrape(test_url, base_url))