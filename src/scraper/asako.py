"""
Scraper Asako.mg - Version Class-based et Optimisée (HTTpx + BeautifulSoup).
Plus rapide et moins gourmand en ressources.
"""
import asyncio
import httpx
import re
from bs4 import BeautifulSoup
from datetime import datetime
from .base import BaseScraper
from .portal import est_une_offre_it, nettoyer_titre, convertir_date_relative, est_date_recente
from ..utils.logger import logger
from ..telegram.bot import envoyer_offre_async

class AsakoScraper(BaseScraper):
    def __init__(self, telegram_bot=None):
        super().__init__("Asako", telegram_bot)
        self.url_base = "https://www.asako.mg"
        self.url_list = f"{self.url_base}/emploi" # URL plus générale pour capturer tout l'IT
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
                # Chaque annonce commence par un h3 avec un lien
                items = soup.select('h3')
                
                logger.info(f"📊 Asako: {len(items)} offres potentielles.")

                for h3 in items:
                    link_el = h3.find('a')
                    if not link_el or '/annonces/' not in link_el.get('href', ''):
                        continue
                        
                    titre = nettoyer_titre(link_el.get_text().strip())
                    
                    if not est_une_offre_it(titre):
                        continue
                    
                    href = link_el.get('href')
                    url_offre = f"{self.url_base}{href}" if href.startswith('/') else href
                    
                    # Traitement de base (doublons)
                    if not await self.traiter_offre({'url': url_offre, 'titre': titre, 'entreprise': ''}):
                        continue

                    # Extraire infos restantes (souvent dans l'élément p/div suivant)
                    meta_el = h3.find_next(['p', 'div', 'span'])
                    meta_text = meta_el.get_text().strip() if meta_el else "aujourd'hui"
                    
                    # Format type: "Il y a 4 jours | CDI - Secteur"
                    parts = [p.strip() for p in meta_text.split('|')]
                    date_text = parts[0] if parts else "aujourd'hui"
                    date_pub = convertir_date_relative(date_text)
                    
                    if not est_date_recente(date_pub, max_jours=4):
                        continue

                    logger.info(f"🎯 [Asako] Nouvelle offre: {titre[:50]}")

                    # Extraire détails ET entreprise depuis la page de détail
                    details, entreprise = await self._extraire_details_et_entreprise(client, url_offre)
                    
                    offre_data = {
                        'titre': titre,
                        'entreprise': entreprise,
                        'url': url_offre,
                        'date': date_pub,
                        'details': details,
                        'date_publication': date_pub,
                        'date_decouverte': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    
                    # Sauvegarde finale et envoi
                    await self.traiter_offre(offre_data)
                    if self.telegram_bot:
                        await envoyer_offre_async(self.telegram_bot, offre_data)

            except Exception as e:
                logger.error(f"Erreur fatale Asako: {e}")

    async def _extraire_details_et_entreprise(self, client, url):
        """
        Extrait les détails de l'offre ET le nom de l'entreprise depuis la page de détail.
        L'entreprise est généralement dans le titre de la page: "... | ENTREPRISE | Asako.mg"
        """
        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                logger.warning(f"⚠️ Status {resp.status_code} pour {url}")
                return "Détails non disponibles.", "Non spécifiée"

            soup = BeautifulSoup(resp.text, 'html.parser')

            # --- 1. Extraction du nom de l'entreprise ---
            entreprise = "Non spécifiée"

            # Méthode 1: Depuis le titre de la page (format: "... | ENTREPRISE | Asako.mg")
            title_tag = soup.find('title')
            if title_tag:
                title_text = title_tag.get_text()
                # Format: "Offre d'emploi : Titre | ENTREPRISE | Asako.mg"
                parts = title_text.split('|')
                if len(parts) >= 2:
                    entreprise = parts[-2].strip()  # L'avant-dernier élément est l'entreprise
                    # Nettoyer si c'est "Asako.mg" (dernier élément)
                    if "asako" in entreprise.lower() and len(parts) >= 3:
                        entreprise = parts[-3].strip()

            # Méthode 2: Depuis les meta tags (og:site_name ou twitter:site)
            if entreprise == "Non spécifiée":
                meta_site = soup.find('meta', property='og:site_name') or soup.find('meta', attrs={'name': 'twitter:site'})
                if meta_site:
                    entreprise = meta_site.get('content', 'Non spécifiée')

            # Méthode 3: Depuis un élément spécifique sur la page
            if entreprise == "Non spécifiée":
                # Chercher dans des classes courantes pour l'entreprise
                company_selectors = ['.entreprise', '.company', '.recruteur', '.employeur', '[class*="entreprise"]', '[class*="company"]']
                for selector in company_selectors:
                    company_el = soup.select_one(selector)
                    if company_el:
                        entreprise = company_el.get_text().strip()
                        break

            # Nettoyer l'entreprise
            if entreprise and entreprise != "Non spécifiée":
                # Enlever "Asako.mg" si présent par erreur
                entreprise = entreprise.replace('| Asako.mg', '').replace('|Asako.mg', '').strip()
                logger.info(f"🏢 Entreprise extraite: {entreprise}")

            # --- 2. Extraction des détails de l'offre ---
            details = "Détails non disponibles."

            # Collecter toutes les sections trouvées
            all_sections = []

            # Méthode 1: Chercher les offer-section (Missions, Profil, etc.)
            offer_sections = soup.find_all('div', class_='offer-section')
            for section in offer_sections:
                # Chercher le titre h2 ou h3 dans cette section
                heading = section.find(['h2', 'h3'])
                if not heading:
                    continue

                heading_text = heading.get_text().strip()
                if any(x in heading_text.lower() for x in ['ces offres', 'pourraient vous intéresser']):
                    continue

                # Extraire le contenu de cette section
                content_parts = []
                for elem in section.find_all(['p', 'ul', 'ol', 'div'], recursive=True):
                    if elem.name == 'p':
                        text = elem.get_text(strip=True)
                        if text and len(text) > 3:
                            content_parts.append(text)
                    elif elem.name in ['ul', 'ol']:
                        for li in elem.find_all('li'):
                            text = li.get_text(strip=True)
                            if text:
                                content_parts.append(f"- {text}")
                    elif elem.name == 'div':
                        # Éviter les divs imbriqués avec d'autres sections
                        if not elem.find(['h2', 'h3', 'section']):
                            text = elem.get_text(separator='\n', strip=True)
                            if text and len(text) > 10:
                                content_parts.append(text)

                if content_parts:
                    section_content = '\n'.join(content_parts)
                    all_sections.append(f"**{heading_text}:**\n{section_content}")

            # Méthode 2: Chercher le conteneur offer-description (Description de l'offre)
            offer_desc = soup.find('div', class_='offer-description')
            if offer_desc:
                heading = offer_desc.find(['h2', 'h3'])
                heading_text = heading.get_text().strip() if heading else "Description de l'offre"

                content_parts = []
                for elem in offer_desc.find_all(['p', 'ul', 'ol'], recursive=True):
                    if elem.name == 'p':
                        text = elem.get_text(strip=True)
                        if text and len(text) > 3:
                            content_parts.append(text)
                    elif elem.name in ['ul', 'ol']:
                        for li in elem.find_all('li'):
                            text = li.get_text(strip=True)
                            if text:
                                content_parts.append(f"- {text}")

                if content_parts:
                    section_content = '\n'.join(content_parts)
                    all_sections.insert(0, f"**{heading_text}:**\n{section_content}")  # Mettre en premier

            # Assembler toutes les sections
            if all_sections:
                details = "\n\n".join(all_sections)
            else:
                # Fallback final: prendre tout le contenu texte pertinent
                main_content = soup.find('div', class_='conditions') or soup.find('main') or soup.find('article')
                if main_content:
                    text = main_content.get_text(separator='\n', strip=True)
                    lines = [line.strip() for line in text.split('\n') if line.strip() and len(line.strip()) > 3]
                    # Filtrer les lignes non pertinentes
                    filtered = [l for l in lines if not any(x in l.lower() for x in ['se connecter', 'inscrivez-vous', 'modal'])]
                    details = '\n'.join(filtered[:100])  # Limiter le nombre de lignes

            # Nettoyer et limiter la taille pour Telegram
            if len(details) > 6000:
                details = details[:6000] + "\n\n... [Détails tronqués, voir lien complet]"

            return details, entreprise

        except Exception as e:
            logger.error(f"❌ Erreur extraction détails/entreprise ({url}): {e}")
            return "Détails non disponibles.", "Non spécifiée"

# Compatibilité
async def surveiller_asako(telegram_bot=None):
    scraper = AsakoScraper(telegram_bot)
    await scraper.run()
