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
from ..llm.gemini_api import generer_resume_entreprise_gemini_async as generer_resume_entreprise_async

class CompanyIntel:
    @staticmethod
    async def search_company_info(company_name):
        """Tente Google, puis DuckDuckGo en cas d'échec, avec résumé IA."""
        # 1. Tentative Google (Playwright)
        res, context = await CompanyIntel._search_google(company_name)
        
        # 2. Fallback DuckDuckGo si Google échoue
        if not res or not any(res.values()):
            logger.info(f"🔄 Basculement sur DuckDuckGo pour {company_name}...")
            res, context = await CompanyIntel._search_duckduckgo(company_name)
        
        if res:
            # 3. Génération du résumé par l'IA basé sur le contexte trouvé
            logger.info(f"🤖 Génération du résumé IA pour {company_name}...")
            res['summary'] = await generer_resume_entreprise_async(company_name, contexte=context)
            
        return res

    @staticmethod
    @retry(stop=stop_after_attempt(1), wait=wait_exponential(multiplier=1, min=2, max=5))
    async def _search_google(company_name):
        query = f"{company_name} Madagascar"
        search_url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
        context_text = ""
        
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

                # Extraction des liens ET du texte pour le contexte IA
                links = await page.locator('a').evaluate_all("(elements) => elements.map(el => el.href)")
                # On récupère aussi un peu de texte visible pour l'IA
                context_text = await page.locator('div#search').inner_text() if await page.locator('div#search').count() > 0 else ""
                
                return CompanyIntel._filter_links(links), context_text[:1000]
            except Exception as e:
                logger.warning(f"⚠️ Échec Google pour {company_name}: {str(e)[:50]}")
                return None, ""
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
                if resp.status_code != 200: return None, ""
                
                soup = BeautifulSoup(resp.text, 'html.parser')
                # Contexte pour l'IA
                context_text = " ".join([r.get_text() for r in soup.find_all('a', class_='result__snippet')[:5]])
                
                links = [a.get('href') for a in soup.find_all('a', class_='result__url')]
                clean_links = []
                for link in links:
                    if link and 'uddg=' in link:
                        clean_links.append(urllib.parse.unquote(link.split('uddg=')[1].split('&')[0]))
                    else:
                        clean_links.append(link)
                
                return CompanyIntel._filter_links(clean_links), context_text
        except Exception as e:
            logger.error(f"❌ Échec DuckDuckGo pour {company_name}: {e}")
            return None, ""

    @staticmethod
    def _filter_links(links):
        results = {"linkedin": None, "facebook": None, "website": None, "summary": None}
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
            offre_data['entreprise_summary'] = intel.get('summary')
    return offre_data
