"""
Module de connexion à l'API Hugging Face pour génération de lettres de motivation.
Support Async avec gestion d'erreurs, retry exponentiel et compatibilité URL globale.
"""
import httpx
import asyncio
import json
import re
from ..config import HF_API_KEY
from ..utils.logger import logger

# Modèle recommandé (Extrêmement puissant et supporté par le Router)
HF_MODEL = "deepseek-ai/DeepSeek-R1"

async def generer_lettre_motivation_async(cv_text, offre_titre, offre_entreprise, offre_details, portfolio=""):
    """Génère une lettre de motivation via l'API Hugging Face (Chat Completion)."""
    if not HF_API_KEY:
        logger.error("HF_API_KEY manquante dans la configuration.")
        return None

    # Point d'entrée pour la compatibilité OpenAI sur l'Inference API
    api_url = "https://router.huggingface.co/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {HF_API_KEY}",
        "Content-Type": "application/json"
    }
    
    context_portfolio = f"Voici mon portfolio pour appuyer ma candidature : {portfolio}" if portfolio else ""

    messages = [
        {
            "role": "system",
            "content": (
                "Tu es un expert en recrutement et en personal branding, spécialisé dans le marché malgache "
                "et les entreprises tech. Tu rédiges des lettres de motivation authentiques, percutantes et "
                "mémorables — pas des lettres génériques.\n\n"
                "Ton objectif : écrire une lettre qui sonne comme un vrai humain déterminé, pas comme un "
                "modèle téléchargé sur internet.\n\n"
                "RÈGLES ABSOLUES :\n"
                "1. Texte brut uniquement. Aucun markdown (pas de **, pas de ##, pas de ---, pas de tirets).\n"
                "2. Aucune réflexion interne, aucune note, aucun commentaire hors lettre.\n"
                "3. Répondre UNIQUEMENT avec le texte final de la lettre, rien d'autre.\n"
                "4. Longueur : 320 à 400 mots maximum. Concis = respectueux du temps du recruteur.\n"
                "5. Ne jamais inventer des expériences absentes du CV."
            )
        },
        {
            "role": "user",
            "content": (
                f"Rédige une lettre de motivation unique et authentique pour ce poste.\n\n"
                f"POSTE : {offre_titre}\n"
                f"ENTREPRISE : {offre_entreprise}\n"
                f"OFFRE : {offre_details}\n\n"
                f"MON CV :\n{cv_text}\n\n"
                f"{context_portfolio}\n\n"
                f"MISSION :\n"
                f"Analyse d'abord le CV et l'offre, puis identifie :\n"
                f"- L'expérience ou projet du candidat qui résonne le plus avec ce poste\n"
                f"- La valeur concrète qu'il peut apporter à cette entreprise spécifique\n"
                f"- Un angle d'accroche fort et personnel (pas 'je me permets de postuler')\n\n"
                f"STRUCTURE À RESPECTER :\n"
                f"- Coordonnées émetteur (nom, téléphone, email)\n"
                f"- Coordonnées destinataire (entreprise, ville)\n"
                f"- Date\n"
                f"- Objet : sobre et précis\n"
                f"- Corps : 3 paragraphes\n"
                f"    Paragraphe 1 — Accroche forte : pourquoi CE poste dans CETTE entreprise (1 fait concret)\n"
                f"    Paragraphe 2 — Valeur ajoutée : 1 ou 2 expériences clés du CV liées aux besoins de l'offre\n"
                f"    Paragraphe 3 — Projection : ce que tu vas apporter concrètement, appel à l'entretien\n"
                f"- Formule de politesse sobre\n"
                f"- Signature\n\n"
                f"TON : Déterminé, sobre, humain. Ni arrogant, ni trop modeste.\n"
                f"Langue : Français impeccable."
            )
        }
    ]

    payload = {
        "model": HF_MODEL,
        "messages": messages,
        "max_tokens": 1400,
        "temperature": 0.65
    }

    # Tentatives multiples (Retry) pour gérer le temps de chargement du modèle
    max_retries = 5
    for attempt in range(max_retries):
        try:
            logger.info(f"🤖 Tentative {attempt + 1}/{max_retries} : Génération avec {HF_MODEL}...")
            
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(api_url, headers=headers, json=payload)
                
                # Succès
                if resp.status_code == 200:
                    result = resp.json()
                    raw_text = result['choices'][0]['message']['content']
                    
                    # NETTOYAGE CRITIQUE : Supprimer les blocs <think>...</think>
                    clean_text = re.sub(r'<think>.*?</think>', '', raw_text, flags=re.DOTALL).strip()
                    
                    # Supprimer les restes de gras markdown ou séparateurs si l'IA en a mis malgré les consignes
                    clean_text = clean_text.replace('**', '').replace('---', '')
                    
                    # S'assurer qu'il n'y a pas de texte d'introduction/conclusion inutile
                    if "Voici la lettre" in clean_text[:50]:
                        clean_text = clean_text.split('\n', 1)[-1].strip()

                    logger.info("✅ Lettre générée et nettoyée avec succès.")
                    return clean_text
                
                # Modèle en cours de chargement sur les serveurs HF
                elif resp.status_code == 503:
                    wait_time = (2 ** attempt)
                    logger.warning(f"Modèle {HF_MODEL} en chargement... Attente {wait_time}s")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Erreur API HF: {resp.status_code} - {resp.text}")
                    break 
                    
        except Exception as e:
            logger.error(f"Exception (Tentative {attempt + 1}): {e}")
            await asyncio.sleep(2 ** attempt)
    
    return None

def generer_lettre_motivation(cv, t, e, d):
    """Wrapper synchrone pour la fonction async."""
    import asyncio
    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        return loop.run_until_complete(generer_lettre_motivation_async(cv, t, e, d))
    except Exception as e:
        logger.error(f"Erreur wrapper sync: {e}")
        return None