import asyncio
import re
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

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

            if is_detail:
                meta_image = soup.find('meta', property='og:image')
                if meta_image and meta_image.get('content'):
                    hoofd_foto_url = meta_image['content']
                    if hoofd_foto_url.startswith('/'):
                        hoofd_foto_url = base_url.rstrip('/') + hoofd_foto_url

            if not is_detail:
                for a in soup.find_all('a', href=True):
                    href = a['href'].strip()
                    if not href or any(n in href.lower() for n in ['facebook', 'linkedin', 'instagram', 'funda.nl', 'google', '.pdf', '.jpg']): 
                        continue

                    is_internal = any(x in href for x in ['/wonen/aanbod/', '/woningen/', '/aanbod/', '/woning/', '/woningaanbod/', '/koopwoningen/'])
                    is_external = href.startswith('http') and base_url.split('//')[-1].split('/')[0] not in href
                    
                    if is_internal or is_external:
                        full_url = href if href.startswith('http') else f"{base_url.rstrip('/')}/{href.lstrip('/')}"
                        if full_url not in links: links.append(full_url)

            print(f"   📊 Eindresultaat: {len(text)} tekens. Foto gevonden: {'Ja' if hoofd_foto_url else 'Nee'}")
            await browser.close()
            return text, links, hoofd_foto_url

        except Exception as e:
            print(f"⚠️ Fout bij {url}: {e}")
            await browser.close()
            return "", [], None