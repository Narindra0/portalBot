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
MOTS_CLES_IT = [
    # Développement
    "développeur", "developpeur", "developer", "fullstack", "full-stack",
    "backend", "frontend", "front-end", "back-end", "python", "php", "java", 
    "javascript", "angular", "react", "odoo", "logiciel", "web", "software", "dev", ".net",
    
    # Infrastructure et Réseaux
    "administrateur", "réseau", "système", "network", "it", "infrastructure", 
    "technicien", "support", "sécurité", "cyber", "cloud", "devops",
    
    # Management et Produit
    "product", "manager", "chef", "projet", "project", "agile", "scrum", 
    "analyste", "consultant", "data", "scénariste", "rédacteur",
    
    # Design
    "ux", "ui", "design", "graphiste", "infographiste"
]

def est_une_offre_it(titre):
    if not titre: return False
    import re
    t = titre.lower()
    
    # Mots-clés qui nécessitent une correspondance exacte (mot entier)
    # pour éviter des faux positifs comme 'ui' dans 'cuisinier'
    MOTS_ENTIERS = ["it", "ui", "ux", "dev"]
    
    for mot in MOTS_CLES_IT:
        if mot in MOTS_ENTIERS:
            # Vérifie si le mot est entouré de limites de mots (\b)
            if re.search(rf"\b{re.escape(mot)}\b", t):
                return True
        elif mot in t:
            return True
            
    return False

def nettoyer_titre(titre):
    if not titre: return ""
    titre = ' '.join(titre.split())
    titre = re.sub(r'\s*-réf:.*$', '', titre, flags=re.IGNORECASE).strip()
    if titre.isupper(): titre = titre.title()
    return titre

def convertir_date_relative(date_texte):
    date_texte = date_texte.strip().lower()
    aujourdhui = datetime.now()
    if "aujourd'hui" in date_texte: return aujourdhui.strftime("%d/%m/%Y")
    elif "hier" in date_texte: return (aujourdhui - timedelta(days=1)).strftime("%d/%m/%Y")
    
    # Gestion de "Il y a X jours" (Asako)
    match = re.search(r"il y a (\d+) jours?", date_texte)
    if match:
        nb_jours = int(match.group(1))
        return (aujourdhui - timedelta(days=nb_jours)).strftime("%d/%m/%Y")
        
    return date_texte

def est_date_recente(date_str, max_jours=4):
    try:
        aujourdhui = datetime.now().date()
        # Gérer le format YYYY-MM-DD ou DD/MM/YYYY
        if '-' in date_str:
            d = datetime.strptime(date_str.split()[0], "%Y-%m-%d").date()
        else:
            d = datetime.strptime(date_str, "%d/%m/%Y").date()
            
        difference = (aujourdhui - d).days
        # On accepte jusqu'à max_jours d'ancienneté (inclus)
        return 0 <= difference <= max_jours
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
                    if not est_date_recente(offre['date'], max_jours=4):
                        logger.debug(f"⏳ Offre ignorée (trop ancienne): {offre['titre']} du {offre['date']}")
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
                if not est_une_offre_it(titre): continue
                
                lien_principal = article.locator('a').first
                href = await lien_principal.get_attribute('href')
                if not href or 'view' not in href: continue
                
                entreprise_el = article.locator('p.font-semibold').first
                entreprise = (await entreprise_el.inner_text()).strip() if await entreprise_el.count() > 0 else "Non spécifiée"
                
                # Extraction de la date plus robuste
                date_texte = "Inconnue"
                all_spans = await article.locator('span').all()
                for span in all_spans:
                    txt = (await span.inner_text()).strip().lower()
                    # Chercher format date DD/MM/YYYY ou mots-clés relatifs
                    if re.search(r'\d{1,2}/\d{1,2}/\d{4}', txt) or "aujourd'hui" in txt or "hier" in txt:
                        date_texte = txt
                        break
                
                date_pub = convertir_date_relative(date_texte)
                
                url_offre = f"https://www.portaljob-madagascar.com{href}" if href.startswith('/') else href
                offres.append({'titre': titre, 'entreprise': entreprise, 'url': url_offre, 'date': date_pub})
            except Exception as e:
                logger.debug(f"⚠️ Erreur extraction article: {e}")
                continue
        return offres

    async def _extraire_details(self, page, url):
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            details = []
            
            # Récupérer tous les titres H2 de la page
            sections = await page.locator('h2').all()
            for heading in sections:
                try:
                    titre = (await heading.inner_text()).strip()
                    if not titre: continue
                    
                    # Le contenu est généralement dans le div sibling ou parent-sibling avec class text-[16px]
                    # On cherche dans le même conteneur parent
                    parent = heading.locator('xpath=..').first
                    content_div = parent.locator('div.text-\\[16px\\]').first
                    
                    if await content_div.count() > 0:
                        text = (await content_div.inner_text()).strip()
                        if text:
                            # Formate avec le titre dynamique
                            details.append(f"**{titre}:**\n{text}")
                except: continue
            
            return "\n\n".join(details) if details else "Détails non disponibles."
        except Exception as e:
            logger.error(f"❌ Erreur détails PortalJob ({url}): {e}")
            return "Détails non disponibles."

# Compatibilité pour garder main.py fonctionnel pendant la transition
async def surveiller_portal(telegram_bot=None):
    scraper = PortalScraper(telegram_bot)
    await scraper.run()
