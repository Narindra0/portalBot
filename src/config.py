"""
Configuration centralisée du projet PortalJob Scraper.
Charge les variables d'environnement depuis config/.env
"""
import os
from dotenv import load_dotenv

# Déterminer le chemin de base du projet
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Charger les variables d'environnement
env_path = os.path.join(BASE_DIR, 'config', '.env')
load_dotenv(env_path)

# === Telegram ===
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# === Hugging Face ===
HF_API_KEY = os.getenv('HF_API_KEY')

# === Mode d'exécution ===
HEADLESS = os.getenv('HEADLESS', 'false').lower() == 'true'

# === Firecrawl (optionnel) ===
FIRECRAWL_API_KEY = os.getenv('FIRECRAWL_API_KEY')

# === Turso (optionnel) ===
TURSO_DATABASE_URL = os.getenv('TURSO_DATABASE_URL')
TURSO_AUTH_TOKEN = os.getenv('TURSO_AUTH_TOKEN')


def verifier_configuration():
    """Vérifie que les variables essentielles sont configurées."""
    erreurs = []
    
    if not TELEGRAM_TOKEN:
        erreurs.append("TELEGRAM_TOKEN manquant")
    if not TELEGRAM_CHAT_ID or TELEGRAM_CHAT_ID == 'votre_chat_id_ici':
        erreurs.append("TELEGRAM_CHAT_ID non configuré")
    if not HF_API_KEY or HF_API_KEY == 'votre_cle_hf_ici':
        erreurs.append("HF_API_KEY manquante (nécessaire pour les lettres de motivation)")
    
    return erreurs


def est_configuration_valide():
    """Retourne True si la configuration minimale est présente."""
    return bool(TELEGRAM_TOKEN and TELEGRAM_CHAT_ID and TELEGRAM_CHAT_ID != 'votre_chat_id_ici')
