"""
BaseScraper - Classe de base pour tous les scrapers du projet.
Définit le contrat et les utilités partagées.
"""
import asyncio
from abc import ABC, abstractmethod
from ..utils.logger import logger
from ..storage.cache_db import (
    sauvegarder_offre_permanente_async,
    offre_existe_async,
    offre_existe_doublon_async,
    recuperer_cv_async,
    recuperer_profil_matching_async,
    sauvegarder_profil_matching_async
)
from ..utils.cv_parser import parser_cv_complet

class BaseScraper(ABC):
    def __init__(self, name, telegram_bot=None):
        self.name = name
        self.telegram_bot = telegram_bot
        self.total_scraped = 0
        self.new_offers = 0

    @abstractmethod
    async def scrape(self):
        """Méthode principale à implémenter par chaque scraper."""
        pass

    async def run(self):
        """Lance le scraping avec gestion d'erreurs global."""
        logger.info(f"🔍 Démarrage du scraper: {self.name}")
        try:
            # Initialiser le profil de matching depuis le CV si nécessaire
            await self._initialiser_profil_matching()
            await self.scrape()
            logger.info(f"✅ {self.name} terminé. ({self.new_offers} nouvelles offres)")
        except Exception as e:
            logger.error(f"❌ Erreur critique dans {self.name}: {e}")

    async def _initialiser_profil_matching(self):
        """Extrait et sauvegarde le profil depuis le CV pour le matching."""
        try:
            # Vérifier si un profil existe déjà
            profil_existant = await recuperer_profil_matching_async()
            if profil_existant:
                logger.debug("Profil matching déjà existant")
                return

            # Récupérer le CV
            cv = await recuperer_cv_async()
            if not cv or not cv.get('cv_text'):
                logger.warning("CV non trouvé - le matching sera désactivé")
                return

            # Parser le CV
            logger.info("🔄 Extraction du profil depuis le CV pour matching...")
            profil = parser_cv_complet(cv['cv_text'])

            # Sauvegarder le profil
            await sauvegarder_profil_matching_async(profil)
            logger.info(f"✅ Profil extrait: {len(profil.get('competences', []))} compétences, {profil.get('annees_exp', 0)} ans d'expérience")

        except Exception as e:
            logger.error(f"Erreur initialisation profil matching: {e}")

    async def traiter_offre(self, offre_data):
        """Logique commune pour filtrer, enrichir et sauvegarder une offre."""
        url = offre_data.get('url', '')
        titre = offre_data.get('titre', '')
        entreprise = offre_data.get('entreprise', 'Non spécifiée')

        # 1. Vérifier doublon URL
        if await offre_existe_async(url):
            return False

        # 2. Vérifier doublon Titre + Entreprise
        if await offre_existe_doublon_async(titre, entreprise):
            # logger.info(f"⏭️ Doublon détecté pour: {titre}")
            return False

        self.total_scraped += 1
        
        # 3. Sauvegarde permanente
        if await sauvegarder_offre_permanente_async(offre_data):
            self.new_offers += 1
            return True
        return False
