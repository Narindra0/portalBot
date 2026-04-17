"""
Intel Module - Recherche d'informations sur les entreprises.
Version Hybride : tente Google (via Playwright) et bascule sur DuckDuckGo (robuste) si échec.
"""
import asyncio
import urllib.parse
import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from tenacity import retry, stop_after_attempt, wait_exponential
from ..utils.logger import logger

class CompanyIntel:
    @staticmethod
    async def search_company_info(company_name):
        """Tente Google, puis DuckDuckGo en cas d'échec."""
        # 1. Tentative Google (Playwright)
        res = await CompanyIntel._search_google(company_name)
        if res and any(res.values()):
            return res
            
        # 2. Fallback DuckDuckGo (HTTpx - très rapide et fiable)
        logger.info(f"🔄 Basculement sur DuckDuckGo pour {company_name}...")
        return await CompanyIntel._search_duckduckgo(company_name)

    @staticmethod
    @retry(stop=stop_after_attempt(1), wait=wait_exponential(multiplier=1, min=2, max=5))
    async def _search_google(company_name):
        query = f"{company_name} Madagascar"
        search_url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            try:
                await page.goto(search_url, wait_until="domcontentloaded", timeout=15000)
                
                # Check Consent
                consent = page.locator('button:has-text("Tout accepter"), button:has-text("Accept all")').first
                if await consent.count() > 0:
                    await consent.click()
                    await page.wait_for_timeout(1000)

                # Extraction large des liens
                links = await page.locator('a').evaluate_all("(elements) => elements.map(el => el.href)")
                return CompanyIntel._filter_links(links)
            except Exception as e:
                logger.warning(f"⚠️ Échec Google pour {company_name}: {str(e)[:50]}")
                return None
            finally:
                await browser.close()

    @staticmethod
    async def _search_duckduckgo(company_name):
        """Recherche DuckDuckGo (Sans JS, très rapide)."""
        query = f"{company_name} Madagascar"
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}
        
        try:
            async with httpx.AsyncClient(headers=headers, timeout=10.0) as client:
                resp = await client.get(url)
                if resp.status_code != 200: return None
                
                soup = BeautifulSoup(resp.text, 'html.parser')
                links = [a.get('href') for a in soup.find_all('a', class_='result__url')]
                # DuckDuckGo HTML links can be wrapped in redirects
                clean_links = []
                for link in links:
                    if link and 'uddg=' in link:
                        clean_links.append(urllib.parse.unquote(link.split('uddg=')[1].split('&')[0]))
                    else:
                        clean_links.append(link)
                
                return CompanyIntel._filter_links(clean_links)
        except Exception as e:
            logger.error(f"❌ Échec DuckDuckGo pour {company_name}: {e}")
            return None

    @staticmethod
    def _filter_links(links):
        results = {"linkedin": None, "facebook": None, "website": None}
        seen = set()
        for url in links:
            if not url or url in seen or any(x in url for x in ["google.com", "duckduckgo.com", "bing.com"]):
                continue
            seen.add(url)
            
            if "linkedin.com/company" in url and not results["linkedin"]:
                results["linkedin"] = url
            elif "facebook.com" in url and not results["facebook"]:
                if all(x not in url for x in ["/groups/", "/sharer/", "/public/"]):
                    results["facebook"] = url
            elif not results["website"]:
                if not any(x in url for x in ["linkedin", "facebook", "twitter", "portaljob", "asako", "instagram", "youtube"]):
                     results["website"] = url
        return results

async def enrichir_offre_intel(offre_data):
    company = offre_data.get('entreprise')
    if company:
        intel = await CompanyIntel.search_company_info(company)
        if intel:
            offre_data['linkedin_url'] = intel['linkedin']
            offre_data['facebook_url'] = intel['facebook']
            offre_data['website_url'] = intel['website']
    return offre_data
