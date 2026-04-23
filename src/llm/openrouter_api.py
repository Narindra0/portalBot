"""
Module de connexion à l'API OpenRouter pour génération de lettres de motivation.
Entièrement gratuit avec le tier "free" (rate limité).
Documentation: https://openrouter.ai/docs
"""
import httpx
import asyncio
import re
from ..config import OPENROUTER_API_KEY
from ..utils.logger import logger

# Modèles gratuits disponibles sur OpenRouter (tier free)
# deepseek/deepseek-chat:free - Bon pour le texte, très généreux rate limits
# google/gemini-2.0-flash-exp:free - Alternative Google
OPENROUTER_MODEL = "deepseek/deepseek-chat:free"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def nettoyer_reponse_ai(text):
    """
    Nettoie les réponses de l'IA pour Telegram (HTML).
    Supprime les blocs <think> et les tags non supportés.
    """
    if not text:
        return ""

    # 1. Supprimer les blocs <think> complets (DeepSeek)
    text = re.sub(r"<(think|thinking)>.*?</\1>", "", text, flags=re.DOTALL | re.IGNORECASE)

    # 2. Supprimer un début de think orphelin
    text = re.sub(r"<(think|thinking)>.*$", "", text, flags=re.DOTALL | re.IGNORECASE)

    # 3. Supprimer tout tag HTML non supporté par Telegram (b, i, a, code, pre)
    text = re.sub(r"<(?!/?(b|i|a|code|pre)\b)[^>]+>", "", text, flags=re.IGNORECASE)

    # 4. Nettoyage résiduel markdown
    text = text.replace("**", "").replace("*", "").replace("---", "").replace("```", "").strip()

    return text


async def generer_lettre_motivation_openrouter_async(cv_text, offre_titre, offre_entreprise, offre_details, portfolio=""):
    """
    Génère une lettre de motivation via l'API OpenRouter (tier free).
    Utilise DeepSeek Chat qui est gratuit avec rate limits raisonnables.
    """
    if not OPENROUTER_API_KEY:
        logger.error("OPENROUTER_API_KEY manquante.")
        return None

    try:
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://portaljob-scraper.local",
            "X-Title": "PortalJob Scraper"
        }

        context_portfolio = f"Voici mon portfolio pour appuyer ma candidature : {portfolio}" if portfolio else ""

        messages = [
            {
                "role": "system",
                "content": "Tu es un expert en recrutement rédigeant des lettres de motivation percutantes, professionnelles et authentiques."
            },
            {
                "role": "user",
                "content": (
                    f"Rédige une lettre de motivation unique et humaine pour le poste suivant.\n\n"
                    f"POSTE : {offre_titre}\n"
                    f"ENTREPRISE : {offre_entreprise}\n"
                    f"DÉTAILS OFFRE : {offre_details}\n\n"
                    f"MON CV :\n{cv_text}\n\n"
                    f"{context_portfolio}\n\n"
                    f"RÈGLES CRITIQUES :\n"
                    "1. Texte brut uniquement. Pas de markdown (pas de **, pas de #, pas de ```).\n"
                    "2. Pas d'en-tête (adresse, date, objet).\n"
                    "3. Pas d'introduction type 'Voici votre lettre' ou 'Voici la lettre'.\n"
                    "4. Commence directement par 'Madame, Monsieur,' ou le nom du recruteur si connu.\n"
                    "5. Ton professionnel mais chaleureux et authentique.\n"
                    "6. Maximum 2500 caractères."
                )
            }
        ]

        payload = {
            "model": OPENROUTER_MODEL,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 800
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(OPENROUTER_URL, headers=headers, json=payload)

            if response.status_code == 200:
                data = response.json()
                if "choices" in data and len(data["choices"]) > 0:
                    raw_text = data["choices"][0]["message"]["content"]
                    clean_text = nettoyer_reponse_ai(raw_text)
                    logger.info("✅ Lettre générée (OpenRouter/DeepSeek) avec succès.")
                    return clean_text
                else:
                    logger.error(f"Réponse OpenRouter invalide: {data}")
            elif response.status_code == 429:
                logger.warning("⚠️ Rate limit OpenRouter atteint. Attente 10s puis retry...")
                await asyncio.sleep(10)
                return await generer_lettre_motivation_openrouter_async(cv_text, offre_titre, offre_entreprise, offre_details, portfolio)
            else:
                logger.error(f"Erreur OpenRouter HTTP {response.status_code}: {response.text}")

    except httpx.TimeoutException:
        logger.error("Timeout OpenRouter (60s). Le service est peut-être saturé.")
    except Exception as e:
        logger.error(f"Erreur OpenRouter (Lettre): {e}")

    return None


async def generer_resume_entreprise_openrouter_async(nom_entreprise, contexte=""):
    """
    Génère un résumé court d'une entreprise via OpenRouter (tier free).
    """
    if not OPENROUTER_API_KEY:
        return None

    try:
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://portaljob-scraper.local",
            "X-Title": "PortalJob Scraper"
        }

        messages = [
            {
                "role": "user",
                "content": (
                    f"Résume en une phrase l'activité de l'entreprise '{nom_entreprise}'.\n"
                    f"Contexte: {contexte}\n"
                    f"RÈGLE: Une seule phrase, directe, sans introduction, sans markdown."
                )
            }
        ]

        payload = {
            "model": OPENROUTER_MODEL,
            "messages": messages,
            "temperature": 0.4,
            "max_tokens": 100
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(OPENROUTER_URL, headers=headers, json=payload)

            if response.status_code == 200:
                data = response.json()
                if "choices" in data and len(data["choices"]) > 0:
                    return nettoyer_reponse_ai(data["choices"][0]["message"]["content"])
            elif response.status_code == 429:
                logger.warning("⚠️ Rate limit OpenRouter atteint (résumé).")
                await asyncio.sleep(5)
                return await generer_resume_entreprise_openrouter_async(nom_entreprise, contexte)

    except Exception as e:
        logger.error(f"Erreur OpenRouter (Résumé): {e}")

    return None


def tester_connexion_openrouter():
    """Teste la connexion à OpenRouter avec un appel simple."""
    import asyncio

    async def _test():
        if not OPENROUTER_API_KEY:
            print("❌ OPENROUTER_API_KEY non configurée")
            return False

        try:
            headers = {
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            }

            payload = {
                "model": OPENROUTER_MODEL,
                "messages": [{"role": "user", "content": "Dis 'OK' en un mot."}],
                "max_tokens": 10
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(OPENROUTER_URL, headers=headers, json=payload)

                if response.status_code == 200:
                    print("✅ Connexion OpenRouter OK (tier free)")
                    return True
                else:
                    print(f"❌ Erreur OpenRouter: {response.status_code} - {response.text}")
                    return False
        except Exception as e:
            print(f"❌ Exception: {e}")
            return False

    return asyncio.run(_test())


# Wrapper synchrone pour compatibilité
def generer_lettre_motivation_openrouter(cv, t, e, d, portfolio=""):
    """Wrapper synchrone pour la fonction async."""
    try:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(generer_lettre_motivation_openrouter_async(cv, t, e, d, portfolio))
    except Exception as e:
        logger.error(f"Erreur wrapper sync OpenRouter: {e}")
        return None
