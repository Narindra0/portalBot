"""
Scraper Mission-Madagascar.mg - Offres freelance en développement.
Basé sur httpx + BeautifulSoup (comme Asako).
URL: https://mission-madagascar.mg/missions/domaines/developpement
"""
import asyncio
import httpx
import re
from bs4 import BeautifulSoup
from datetime import datetime
from .base import BaseScraper
from .portal import est_une_offre_it, nettoyer_titre, est_date_recente
from ..utils.logger import logger
from ..utils.intel import enrichir_offre_intel
from ..telegram.bot import envoyer_offre_async


class MissionMadaScraper(BaseScraper):
    def __init__(self, telegram_bot=None):
        super().__init__("Mission-Madagascar", telegram_bot)
        self.url_base = "https://mission-madagascar.mg"
        self.url_list = f"{self.url_base}/missions/domaines/developpement"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    def convertir_date_mission(self, date_texte):
        """Convertit les dates du format 'Publiée le DD/MM/YYYY'"""
        date_texte = date_texte.strip().lower()
        aujourdhui = datetime.now()

        # Format: "publiée le 15/04/2026"
        match = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', date_texte)
        if match:
            jour, mois, annee = match.groups()
            try:
                date_obj = datetime(int(annee), int(mois), int(jour))
                return date_obj.strftime("%d/%m/%Y")
            except:
                pass

        # Fallback
        if "aujourd'hui" in date_texte:
            return aujourdhui.strftime("%d/%m/%Y")
        elif "hier" in date_texte:
            return (aujourdhui - __import__('datetime').timedelta(days=1)).strftime("%d/%m/%Y")

        return date_texte

    async def scrape(self):
        async with httpx.AsyncClient(headers=self.headers, timeout=30.0, follow_redirects=True) as client:
            try:
                response = await client.get(self.url_list)
                if response.status_code != 200:
                    logger.error(f"Erreur Mission-Mada: Status {response.status_code}")
                    return

                soup = BeautifulSoup(response.text, 'html.parser')

                # Les offres sont dans des sections avec h3
                # Chaque h3 contient un lien vers la mission
                items = soup.find_all('h3')

                logger.info(f"📊 Mission-Mada: {len(items)} offres potentielles.")

                for h3 in items:
                    link_el = h3.find('a')
                    if not link_el:
                        continue

                    href = link_el.get('href', '')
                    # Filtrer uniquement les liens de description de missions
                    if '/missions/description/' not in href:
                        continue

                    titre = nettoyer_titre(link_el.get_text().strip())

                    # Vérifier si c'est une offre IT
                    if not est_une_offre_it(titre):
                        continue

                    url_offre = f"{self.url_base}{href}" if href.startswith('/') else href

                    # Traitement de base (doublons)
                    if not await self.traiter_offre({'url': url_offre, 'titre': titre, 'entreprise': ''}):
                        continue

                    # Extraire la date et description depuis la page de liste
                    # La date est souvent dans un texte après le titre ou dans un parent
                    date_text = "aujourd'hui"
                    parent = h3.find_parent()
                    if parent:
                        # Chercher la date dans le texte du parent
                        parent_text = parent.get_text()
                        date_match = re.search(r'Publiée le (\d{1,2}/\d{1,2}/\d{4})', parent_text)
                        if date_match:
                            date_text = date_match.group(0)

                    date_pub = self.convertir_date_mission(date_text)

                    if not est_date_recente(date_pub, max_jours=7):  # 7 jours pour missions freelance
                        continue

                    logger.info(f"🎯 [Mission-Mada] Nouvelle offre: {titre[:50]}")

                    # Extraire détails et entreprise depuis la page de détail
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
                logger.error(f"Erreur fatale Mission-Mada: {e}")

    async def _extraire_details_et_entreprise(self, client, url):
        """
        Extrait les détails de la mission et le nom de l'entreprise/client.
        """
        try:
            resp = await client.get(url)
            if resp.status_code != 200:
                logger.warning(f"⚠️ Status {resp.status_code} pour {url}")
                return "Détails non disponibles.", "Non spécifiée"

            soup = BeautifulSoup(resp.text, 'html.parser')

            # --- 1. Extraction du nom de l'entreprise/client ---
            entreprise = "Non spécifiée"

            # Méthode 1: Depuis le titre de la page
            title_tag = soup.find('title')
            if title_tag:
                title_text = title_tag.get_text()
                # Essayer d'extraire des infos du titre
                # Format possible: "Titre | Mission Madagascar" ou juste "Titre"
                if '|' in title_text:
                    parts = title_text.split('|')
                    if len(parts) >= 2:
                        entreprise = parts[-2].strip()

            # Méthode 2: Chercher des mentions d'entreprise dans le contenu
            if entreprise == "Non spécifiée":
                # Chercher des patterns comme "chez", "pour", "société", "entreprise"
                content_text = soup.get_text()
                patterns = [
                    r'(?:chez|pour|société|entreprise|client)\s*[:\s]\s*([A-Z][A-Za-z0-9\s&]+)',
                    r'agence\s+([A-Z][A-Za-z0-9\s&]+)',
                    r'startup\s+([A-Z][A-Za-z0-9\s&]+)'
                ]
                for pattern in patterns:
                    match = re.search(pattern, content_text, re.IGNORECASE)
                    if match:
                        entreprise = match.group(1).strip()
                        break

            # Méthode 3: Depuis des classes spécifiques
            if entreprise == "Non spécifiée":
                company_selectors = ['.client', '.entreprise', '.company', '[class*="client"]', '[class*="entreprise"]']
                for selector in company_selectors:
                    company_el = soup.select_one(selector)
                    if company_el:
                        entreprise = company_el.get_text().strip()
                        break

            if entreprise and entreprise != "Non spécifiée":
                logger.info(f"🏢 Client/Entreprise extraite: {entreprise}")

            # --- 2. Extraction des détails de la mission ---
            details = "Détails non disponibles."

            # Méthode 1: Chercher la section contenu principale
            content_selectors = [
                '.mission-content',
                '.description',
                '.content',
                '.mission-description',
                'article',
                '.details',
                '[class*="description"]',
                '[class*="content"]'
            ]

            content_div = None
            for selector in content_selectors:
                content_div = soup.select_one(selector)
                if content_div:
                    logger.debug(f"✅ Sélecteur Mission-Mada trouvé: {selector}")
                    break

            # Méthode 2: Extraire depuis les sections h3 (les titres sont dans des h3 sur cette page)
            if not content_div:
                sections = []
                # Chercher les titres h4 ou h3 suivis de contenu
                for heading in soup.find_all(['h3', 'h4']):
                    section_title = heading.get_text().strip()
                    # Ignorer les titres de navigation
                    if section_title in ['Missions disponible', 'Liste de projet freelances Madagascar', 'travail en ligne à Madagascar']:
                        continue

                    # Le contenu est souvent dans les éléments suivants
                    next_els = []
                    current = heading.find_next_sibling()
                    for _ in range(3):  # Chercher les 3 éléments suivants
                        if current and current.name in ['p', 'div', 'ul']:
                            next_els.append(current)
                        current = current.find_next_sibling() if current else None

                    if next_els:
                        section_content = '\n'.join([el.get_text(strip=True) for el in next_els])
                        if section_content:
                            sections.append(f"**{section_title}:**\n{section_content}")

                if sections:
                    details = "\n\n".join(sections)

            # Méthode 3: Fallback sur un div de contenu général
            if details == "Détails non disponibles." and content_div:
                text = content_div.get_text(separator='\n').strip()
                lines = [line.strip() for line in text.split('\n') if line.strip()]
                details = '\n'.join(lines)

            # Si toujours vide, prendre tout le body (fallback extrême)
            if details == "Détails non disponibles.":
                body = soup.find('body')
                if body:
                    text = body.get_text(separator='\n').strip()
                    # Nettoyer
                    lines = [line.strip() for line in text.split('\n') if line.strip() and len(line.strip()) > 20]
                    details = '\n'.join(lines[:50])  # Limiter à 50 lignes

            # Limiter la taille pour Telegram
            if len(details) > 4000:
                details = details[:4000] + "...\n\n[Détails tronqués, voir lien complet]"

            return details, entreprise

        except Exception as e:
            logger.error(f"❌ Erreur extraction détails/entreprise Mission-Mada ({url}): {e}")
            return "Détails non disponibles.", "Non spécifiée"


# Compatibilité
async def surveiller_mission_mada(telegram_bot=None):
    scraper = MissionMadaScraper(telegram_bot)
    await scraper.run()
