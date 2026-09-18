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
            
            # Wacht even op eventuele JavaScript rendering
            await asyncio.sleep(4)
            
           # Robuuste cookie- en overlay-afhandeling (klikt meerdere lagen weg)
            overlay_termen = [
                "accepteer", "akkoord", "alles akkoord", "toestaan", 
                "sluiten", "close", "opslaan", "verder", "begrepen"
            ]
            
            for term in overlay_termen:
                try:
                    # Zoek naar buttons of elementen met passende tekst/aria-labels
                    locator = page.locator(
                        f"button:has-text('{term}'), a:has-text('{term}'), [aria-label*='{term}' i]"
                    )
                    if await locator.count() > 0 and await locator.first.is_visible():
                        await locator.first.click(timeout=1500)
                        await asyncio.sleep(1)
                except Exception:
                    pass

            # Vangnet: verwijder eventuele hardnekkige backdrops/overlays uit de DOM
            try:
                await page.evaluate("""() => {
                    const selectors = [
                        '.modal-backdrop', '.fade.show', '.overlay', 
                        '[class*="cookie"]', '[id*="cookie"]', 
                        '[class*="popup"]', '[class*="modal"]'
                    ];
                    selectors.forEach(sel => {
                        document.querySelectorAll(sel).forEach(el => el.remove());
                    });
                    document.body.style.overflow = 'auto';
                    document.documentElement.style.overflow = 'auto';
                }""")
            except Exception:
                pass

            # Lichte scroll om eventuele lazy loading te triggeren
            await page.mouse.wheel(0, 1000)
            await asyncio.sleep(1)
            
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            target = soup.find('main') or soup.find('article') or soup.body
            text = target.get_text(separator=' ', strip=True) if target else ""

            links = []
            if not is_detail:
                domain = base_url.split('//')[-1].split('/')[0]
                for a in soup.find_all('a', href=True):
                    href = a['href'].strip()
                    if not href or any(n in href.lower() for n in ['facebook', 'linkedin', 'instagram', 'funda.nl', 'google', '.pdf', '.jpg', 'mailto:', 'tel:']): 
                        continue

                    full_url = href if href.startswith('http') else f"{base_url.rstrip('/')}/{href.lstrip('/')}"
                    clean_url = full_url.split('?')[0].rstrip('/')

                    # Alleen links van hetzelfde domein en geen paginatie
                    if domain in clean_url and 'page/' not in clean_url.lower():
                        path = clean_url.lower()
                        
                        # Breed filter zodat de Verkenner-agent alle typen object-links binnenkrijgt
                        is_woning_pad = any(x in path for x in ['woning', 'aanbod', 'koop', 'pand', 'object', 'details', 'huis', '/woningen/'])
                        
                        if is_woning_pad and clean_url != base_url.rstrip('/'):
                            if clean_url not in links: 
                                links.append(clean_url)

            await browser.close()
            return text, links, None

        except Exception as e:
            print(f"⚠️ Fout bij {url}: {e}")
            await browser.close()
            return "", [], None