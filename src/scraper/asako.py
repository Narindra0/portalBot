"""
Scraper Asako.mg - Version Class-based et Optimisée (HTTpx + BeautifulSoup).
Plus rapide et moins gourmand en ressources.
"""
import asyncio
import httpx
from bs4 import BeautifulSoup
from datetime import datetime
from .base import BaseScraper
from .portal import est_une_offre_it, nettoyer_titre, convertir_date_relative
from ..utils.logger import logger
from ..utils.intel import enrichir_offre_intel
from ..telegram.bot import envoyer_offre_async

class AsakoScraper(BaseScraper):
    def __init__(self, telegram_bot=None):
        super().__init__("Asako", telegram_bot)
        self.url_base = "https://www.asako.mg"
        self.url_list = f"{self.url_base}/emploi/m-developpeur"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    async def scrape(self):
        async with httpx.AsyncClient(headers=self.headers, timeout=30.0, follow_redirects=True) as client:
            try:
                response = await client.get(self.url_list)
                if response.status_code != 200:
                    logger.error(f"Erreur Asako: Status {response.status_code}")
                    return

                soup = BeautifulSoup(response.text, 'html.parser')
                items = soup.select('.box-annonce')
                
                logger.info(f"📊 Asako: {len(items)} offres potentielles.")

                for item in items:
                    h2 = item.find('h2')
                    if not h2: continue
                    titre = nettoyer_titre(h2.get_text().strip())
                    
                    if not est_une_offre_it(titre): continue
                    
                    link_el = item.find('a')
                    if not link_el: continue
                    href = link_el.get('href')
                    url_offre = f"{self.url_base}{href}" if href.startswith('/') else href
                    
                    # Traitement de base (doublons)
                    if not await self.traiter_offre({'url': url_offre, 'titre': titre, 'entreprise': ''}):
                        continue

                    # Extraire infos restantes
                    ent_el = item.select_one('.entreprise')
                    entreprise = ent_el.get_text().strip() if ent_el else "Non spécifiée"
                    
                    date_el = item.select_one('.date')
                    date_text = date_el.get_text().strip() if date_el else "aujourd'hui"
                    date_pub = convertir_date_relative(date_text)
                    
                    logger.info(f"🎯 [Asako] Nouvelle offre: {titre[:50]}")
                    details = await self._extraire_details(client, url_offre)
                    
                    offre_data = {
                        'titre': titre,
                        'entreprise': entreprise,
                        'url': url_offre,
                        'date': date_pub,
                        'details': details,
                        'date_publication': date_pub,
                        'date_decouverte': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    
                    # Intelligence
                    offre_data = await enrichir_offre_intel(offre_data)
                    
                    # Sauvegarde finale et envoi
                    await self.traiter_offre(offre_data)
                    if self.telegram_bot:
                        await envoyer_offre_async(self.telegram_bot, offre_data)

            except Exception as e:
                logger.error(f"Erreur fatale Asako: {e}")

    async def _extraire_details(self, client, url):
        try:
            resp = await client.get(url)
            if resp.status_code != 200: return "Détails non disponibles."
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            # Extraction par texte (comme sur PortalJob)
            content_div = soup.select_one('.description-offre, .content-annonce')
            if not content_div: return "Détails non disponibles."
            
            # Formatage sommaire
            text = content_div.get_text(separator='\n').strip()
            return text[:4000] # Limite Telegram
        except: return "Détails non disponibles."

# Compatibilité
async def surveiller_asako(telegram_bot=None):
    scraper = AsakoScraper(telegram_bot)
    await scraper.run()
