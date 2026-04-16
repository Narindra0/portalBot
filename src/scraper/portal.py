"""
Scraper PortalJob Madagascar - Secteur Informatique/Web.
Refactorisé pour asyncio et async_playwright.
"""
import asyncio
import os
import re
from datetime import datetime, timedelta
from playwright.async_api import async_playwright

from ..config import HEADLESS as HEADLESS_MODE
from ..storage.cache_db import (
    sauvegarder_offre_permanente_async, 
    offre_existe_async, 
    compter_offres_async
)
from ..telegram.bot import envoyer_offre_async
from ..utils.logger import logger

# Liste des mots-clés pour filtrer uniquement les jobs de dev
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
    """Supprime les références et formate le texte."""
    if not titre: return ""
    # Nettoyer les espaces bizarres
    titre = ' '.join(titre.split())
    # Supprimer les références (ex: -réf:SC-WBM/2026)
    titre = re.sub(r'\s*-réf:.*$', '', titre, flags=re.IGNORECASE).strip()
    # Si tout est en majuscule, mettre en Title Case
    if titre.isupper():
        titre = titre.title()
    return titre

def convertir_date_relative(date_texte):
    date_texte = date_texte.strip().lower()
    aujourdhui = datetime.now()
    if date_texte == "aujourd'hui":
        return aujourdhui.strftime("%d/%m/%Y")
    elif date_texte == "hier":
        return (aujourdhui - timedelta(days=1)).strftime("%d/%m/%Y")
    return date_texte

def est_date_recente(date_str, max_jours=2):
    """Vérifie si la date est dans l'intervalle des derniers jours."""
    try:
        # Si c'est aujourd'hui ou hier (cas courants sur PortalJob)
        aujourdhui = datetime.now().date()
        hier = aujourdhui - timedelta(days=1)
        
        # On essaie de parser la date formatée par convertir_date_relative
        d = datetime.strptime(date_str, "%d/%m/%Y").date()
        
        difference = (aujourdhui - d).days
        return 0 <= difference < max_jours
    except:
        # En cas de format inconnu, on ne prend pas de risque (ou on pourrait accepter)
        return False

async def extraire_offres_du_dom(page):
    """Extrait les offres de base du listing."""
    offres = []
    articles = await page.locator('article').all()
    
    for article in articles[:30]:
        try:
            h3 = article.locator('h3').first
            titre_brut = (await h3.inner_text()).strip()
            if not titre_brut or len(titre_brut) < 5: continue
            
            # Nettoyage selon demande utilisateur
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
            
            offres.append({
                'titre': titre, 'entreprise': entreprise, 'url': url_offre, 'date': date_pub
            })
        except:
            continue
    return offres

async def extraire_details(page, url):
    """Extrait les détails d'une offre."""
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
    except Exception as e:
        return f"Détails non disponibles ({str(e)[:50]})."

async def surveiller_portal(telegram_bot=None):
    """Tâche principale de surveillance."""
    url_secteur = "https://www.portaljob-madagascar.com/emploi/liste/secteur/informatique-web"
    
    total_offres = await compter_offres_async()
    logger.info(f"🚀 Déclenchement du scraper... ({total_offres} offres en base)")

    async with async_playwright() as p:
        # Configuration Browser Stealth
        browser = await p.chromium.launch(headless=HEADLESS_MODE)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        try:
            logger.info("🔍 Chargement de PortalJob...")
            await page.goto(url_secteur, wait_until="networkidle", timeout=60000)
            
            # Scroll pour lazy load
            for _ in range(3):
                await page.evaluate("window.scrollBy(0, 800)")
                await asyncio.sleep(1)
            
            offres_dom = await extraire_offres_du_dom(page)
            logger.info(f"📊 {len(offres_dom)} offres potentielles trouvées.")
            
            for offre in offres_dom:
                if await offre_existe_async(offre['url']):
                    continue
                
                # Filtrer par date (ne prendre que les 2 derniers jours)
                if not est_date_recente(offre['date'], max_jours=2):
                    continue
                
                logger.info(f"🎯 Nouvelle offre: {offre['titre'][:50]}")
                details = await extraire_details(page, offre['url'])
                
                offre_data = {
                    **offre,
                    "details": details,
                    "date_publication": offre['date'],
                    "date_decouverte": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
                if await sauvegarder_offre_permanente_async(offre_data):
                    if telegram_bot:
                        await envoyer_offre_async(telegram_bot, offre_data)
                    else:
                        logger.warning("Bot Telegram non fourni au scraper. Envoi ignoré.")
                
            logger.info("✅ Surveillance terminée.")
            
        except Exception as e:
            logger.error(f"Erreur fatale scraper: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(surveiller_portal())
