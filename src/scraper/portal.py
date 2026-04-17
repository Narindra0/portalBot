"""
Scraper PortalJob Madagascar - Version Class-based.
"""
import asyncio
import re
from datetime import datetime, timedelta
from playwright.async_api import async_playwright

from ..config import HEADLESS as HEADLESS_MODE
from .base import BaseScraper
from ..utils.logger import logger
from ..utils.intel import enrichir_offre_intel
from ..telegram.bot import envoyer_offre_async

# Utils (gardés pour compatibilité / simplicité)
MOTS_CLES_DEV = [
    "développeur", "developpeur", "developer", "fullstack", "full-stack",
    "backend", "frontend", "front-end", "back-end", "net", "python",
    "php", "java", "javascript", "angular", "react", "odoo", "logiciel", "web", "software", "dev"
]

def est_une_offre_dev(titre):
    if not titre: return False
    t = titre.lower()
    return any(mot in t for mot in MOTS_CLES_DEV)

def nettoyer_titre(titre):
    if not titre: return ""
    titre = ' '.join(titre.split())
    titre = re.sub(r'\s*-réf:.*$', '', titre, flags=re.IGNORECASE).strip()
    if titre.isupper(): titre = titre.title()
    return titre

def convertir_date_relative(date_texte):
    date_texte = date_texte.strip().lower()
    aujourdhui = datetime.now()
    if date_texte == "aujourd'hui": return aujourdhui.strftime("%d/%m/%Y")
    elif date_texte == "hier": return (aujourdhui - timedelta(days=1)).strftime("%d/%m/%Y")
    return date_texte

def est_date_recente(date_str, max_jours=2):
    try:
        aujourdhui = datetime.now().date()
        d = datetime.strptime(date_str, "%d/%m/%Y").date()
        difference = (aujourdhui - d).days
        return 0 <= difference < max_jours
    except: return False

class PortalScraper(BaseScraper):
    def __init__(self, telegram_bot=None):
        super().__init__("PortalJob", telegram_bot)
        self.url_secteur = "https://www.portaljob-madagascar.com/emploi/liste/secteur/informatique-web"

    async def scrape(self):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=HEADLESS_MODE)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            
            try:
                await page.goto(self.url_secteur, wait_until="networkidle", timeout=60000)
                # Scroll
                for _ in range(2):
                    await page.evaluate("window.scrollBy(0, 800)")
                    await asyncio.sleep(1)
                
                offres_dom = await self._extraire_liste(page)
                
                for offre in offres_dom:
                    if not est_date_recente(offre['date'], max_jours=2):
                        continue
                    
                    # Traitement de base (doublons)
                    if not await self.traiter_offre(offre):
                        continue

                    # Si nouvelle offre, extraire détails et enrichir
                    logger.info(f"🎯 [PortalJob] Nouvelle offre: {offre['titre'][:50]}")
                    details = await self._extraire_details(page, offre['url'])
                    
                    offre_data = {
                        **offre,
                        "details": details,
                        "date_publication": offre['date'],
                        "date_decouverte": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    
                    # Intelligence: Recherche réseaux sociaux
                    offre_data = await enrichir_offre_intel(offre_data)
                    
                    # Sauvegarde finale et envoi
                    await self.traiter_offre(offre_data) # Re-save with details and intel
                    if self.telegram_bot:
                        await envoyer_offre_async(self.telegram_bot, offre_data)

            finally:
                await browser.close()

    async def _extraire_liste(self, page):
        offres = []
        articles = await page.locator('article').all()
        for article in articles[:30]:
            try:
                h3 = article.locator('h3').first
                titre_brut = (await h3.inner_text()).strip()
                titre = nettoyer_titre(titre_brut)
                if not est_une_offre_dev(titre): continue
                
                lien_principal = article.locator('a').first
                href = await lien_principal.get_attribute('href')
                if not href or 'view' not in href: continue
                
                entreprise_el = article.locator('p.font-semibold').first
                entreprise = (await entreprise_el.inner_text()).strip() if await entreprise_el.count() > 0 else "Non spécifiée"
                
                spans = await article.locator('a span').all()
                date_texte = (await spans[3].inner_text()).strip() if len(spans) >= 4 else "Inconnue"
                date_pub = convertir_date_relative(date_texte)
                
                url_offre = f"https://www.portaljob-madagascar.com{href}" if href.startswith('/') else href
                offres.append({'titre': titre, 'entreprise': entreprise, 'url': url_offre, 'date': date_pub})
            except: continue
        return offres

    async def _extraire_details(self, page, url):
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            details = []
            sections = [("Activité de l'entreprise", "Activité entreprise:"), ("Missions", "Missions:"), ("Profil recherché", "Profil recherché:")]
            for titre_section, prefix in sections:
                try:
                    heading = page.locator(f'h2:has-text("{titre_section}")').first
                    if await heading.count() > 0:
                        parent = heading.locator('xpath=..').first
                        content_div = parent.locator('div.text-\\[16px\\]').first
                        if await content_div.count() > 0:
                            text = (await content_div.inner_text()).strip()
                            if text: details.append(f"**{prefix}**\n{text}")
                except: continue
            return '\n\n'.join(details) if details else "Détails non disponibles."
        except: return "Détails non disponibles."

# Compatibilité pour garder main.py fonctionnel pendant la transition
async def surveiller_portal(telegram_bot=None):
    scraper = PortalScraper(telegram_bot)
    await scraper.run()
