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
    offre_existe_doublon_async
)

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
            await self.scrape()
            logger.info(f"✅ {self.name} terminé. ({self.new_offers} nouvelles offres)")
        except Exception as e:
            logger.error(f"❌ Erreur critique dans {self.name}: {e}")

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
