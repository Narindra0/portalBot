"""
Module de génération de lettres de motivation.
Adapté pour l'asynchronisme.
"""
from ..storage.cache_db import recuperer_cv_async
from .gemini_api import generer_lettre_motivation_gemini_async as generer_lettre_motivation_async
from ..utils.logger import logger

async def creer_lettre_motivation(offre_data):
    """Crée une lettre de motivation personnalisée (Async)."""
    cv = await recuperer_cv_async()
    if not cv:
        return False, "❌ CV non configuré."

    titre = offre_data.get('titre', 'Poste non spécifié')
    entreprise = offre_data.get('entreprise', 'Entreprise non spécifiée')
    details = offre_data.get('details', '')

    logger.info(f"📝 Préparation de la lettre pour: {titre} @ {entreprise}")

    lettre = await generer_lettre_motivation_async(
        cv['cv_text'], 
        titre, 
        entreprise, 
        details,
        portfolio=cv.get('portfolio', '')
    )

    if lettre:
        return True, lettre
    return False, "❌ Échec de la génération (API Hugging Face)."

def formater_lettre_pour_telegram(lettre):
    """Découpe la lettre pour Telegram."""
    MAX_LENGTH = 3800
    if len(lettre) <= MAX_LENGTH:
        return [lettre]

    parts = []
    current = ""
    for line in lettre.split('\n'):
        if len(current) + len(line) + 1 > MAX_LENGTH:
            parts.append(current)
            current = line + '\n'
        else:
            current += line + '\n'
    if current:
        parts.append(current)
    return parts
