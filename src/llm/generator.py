"""
Module de génération de lettres de motivation.
Adapté pour l'asynchronisme.
Priorité: OpenRouter (gratuit) → Gemini → HuggingFace
"""
from ..storage.cache_db import recuperer_cv_async
from .openrouter_api import generer_lettre_motivation_openrouter_async
from .gemini_api import generer_lettre_motivation_gemini_async
from .huggingface_api import generer_lettre_motivation_async as generer_lettre_motivation_hf_async
from ..config import OPENROUTER_API_KEY, GEMINI_API_KEY, HF_API_KEY
from ..utils.logger import logger


async def creer_lettre_motivation(offre_data):
    """
    Crée une lettre de motivation personnalisée (Async).
    Essaye les APIs dans l'ordre: OpenRouter (gratuit) → Gemini → HuggingFace
    """
    cv = await recuperer_cv_async()
    if not cv:
        return False, "❌ CV non configuré."

    titre = offre_data.get('titre', 'Poste non spécifié')
    entreprise = offre_data.get('entreprise', 'Entreprise non spécifiée')
    details = offre_data.get('details', '')
    portfolio = cv.get('portfolio', '')

    logger.info(f"📝 Préparation de la lettre pour: {titre} @ {entreprise}")

    lettre = None

    # 1. Essayer OpenRouter (gratuit) - Prioritaire
    if OPENROUTER_API_KEY:
        logger.info("🔄 Tentative avec OpenRouter (gratuit)...")
        lettre = await generer_lettre_motivation_openrouter_async(
            cv['cv_text'], titre, entreprise, details, portfolio
        )
        if lettre:
            logger.info("✅ Lettre générée avec OpenRouter")
            return True, lettre

    # 2. Fallback sur Gemini
    if GEMINI_API_KEY:
        logger.info("🔄 Fallback sur Gemini...")
        lettre = await generer_lettre_motivation_gemini_async(
            cv['cv_text'], titre, entreprise, details, portfolio
        )
        if lettre:
            logger.info("✅ Lettre générée avec Gemini")
            return True, lettre

    # 3. Dernier recours: HuggingFace
    if HF_API_KEY:
        logger.info("🔄 Dernier recours: HuggingFace...")
        lettre = await generer_lettre_motivation_hf_async(
            cv['cv_text'], titre, entreprise, details, portfolio
        )
        if lettre:
            logger.info("✅ Lettre générée avec HuggingFace")
            return True, lettre

    return False, "❌ Échec de la génération (toutes les APIs sont indisponibles). Vérifiez vos clés API."

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
