"""
Intel Module - Recherche d'informations sur les entreprises via Google Search.
"""
import asyncio
from googlesearch import search
from tenacity import retry, stop_after_attempt, wait_exponential
from ..utils.logger import logger

class CompanyIntel:
    @staticmethod
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def search_company_info(company_name):
        """
        Recherche les liens LinkedIn, Facebook et Site Web d'une entreprise.
        """
        if not company_name or company_name.lower() == "non spécifiée":
            return None

        results = {
            "linkedin": None,
            "facebook": None,
            "website": None
        }

        query = f"{company_name} Madagascar"
        
        try:
            # On lance la recherche de manière asynchrone pour ne pas bloquer
            # googlesearch-python est synchrone, on utilise to_thread
            search_results = await asyncio.to_thread(
                lambda: list(search(query, num_results=10, lang="fr"))
            )

            for url in search_results:
                if "linkedin.com/company" in url and not results["linkedin"]:
                    results["linkedin"] = url
                elif "facebook.com" in url and not results["facebook"]:
                    # Éviter les liens de partage ou profils personnels si possible
                    if "/groups/" not in url and "/sharer/" not in url:
                        results["facebook"] = url
                elif not results["website"] and not any(x in url for x in ["linkedin", "facebook", "twitter", "youtube", "portaljob", "asako"]):
                    # On prend le premier lien "propre" comme site web
                    results["website"] = url

            return results
        except Exception as e:
            logger.error(f"⚠️ Erreur Intel pour {company_name}: {e}")
            return None

async def enrichir_offre_intel(offre_data):
    """Enrichit une offre avec les données sociales de l'entreprise."""
    company = offre_data.get('entreprise')
    if company:
        intel = await CompanyIntel.search_company_info(company)
        if intel:
            offre_data['linkedin_url'] = intel['linkedin']
            offre_data['facebook_url'] = intel['facebook']
            offre_data['website_url'] = intel['website']
    return offre_data
