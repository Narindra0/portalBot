"""
Module de bot Telegram pour envoi des offres PortalJob.
"""
import os
import requests
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config', '.env'))

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# Import du gestionnaire de cache SQLite
from ..storage import ajouter_offre as sauvegarder_offre_cache


def formater_card_compacte(offre_data):
    """
    Formate une offre en card compacte (aperçu rapide).
    """
    titre = offre_data.get('titre', 'Sans titre')
    entreprise = offre_data.get('entreprise', 'Non spécifiée')
    date_pub = offre_data.get('date_publication', 'Date inconnue')

    # Extraire un résumé des missions (3 premières lignes)
    details = offre_data.get('details', '')
    resume_missions = ""

    if "**Missions:**" in details:
        missions_part = details.split("**Missions:**")[1].split("**")[0] if "**" in details.split("**Missions:**")[1] else details.split("**Missions:**")[1]
        missions_lines = [line.strip() for line in missions_part.split('\n') if line.strip() and not line.startswith('**')][:2]
        if missions_lines:
            resume_missions = "\n".join([f"▫️ {line[:80]}" for line in missions_lines])

    message = f"""💼 *{titre}*

🏢 {entreprise}  •  📅 {date_pub}"""

    if resume_missions:
        message += f"\n\n{resume_missions}"

    return message


def formater_details_complets(offre_data):
    """
    Formate les détails complets de l'offre.
    """
    titre = offre_data.get('titre', 'Sans titre')
    entreprise = offre_data.get('entreprise', 'Non spécifiée')
    date_pub = offre_data.get('date_publication', 'Date inconnue')
    details = offre_data.get('details', '')

    # Construire le message complet
    sections = []

    # Activité entreprise
    if "**Activité entreprise:**" in details:
        activite = details.split("**Activité entreprise:**")[1].split("**")[0] if "**" in details.split("**Activité entreprise:**")[1] else details.split("**Activité entreprise:**")[1][:300]
        sections.append(f"💼 *Activité entreprise :*\n{activite.strip()[:250]}")

    # Missions
    if "**Missions:**" in details:
        missions = details.split("**Missions:**")[1].split("**")[0] if "**" in details.split("**Missions:**")[1] else details.split("**Missions:**")[1][:400]
        missions_clean = missions.strip()
        # Limiter à 5 lignes
        missions_lines = [line.strip() for line in missions_clean.split('\n') if line.strip() and not line.startswith('**')][:5]
        if missions_lines:
            sections.append(f"📋 *Missions :*\n" + "\n".join(missions_lines))

    # Profil
    if "**Profil recherché:**" in details:
        profil = details.split("**Profil recherché:**")[1].split("**")[0] if "**" in details.split("**Profil recherché:**")[1] else details.split("**Profil recherché:**")[1][:400]
        profil_clean = profil.strip()
        profil_lines = [line.strip() for line in profil_clean.split('\n') if line.strip() and not line.startswith('**')][:4]
        if profil_lines:
            sections.append(f"👤 *Profil recherché :*\n" + "\n".join(profil_lines))

    message = f"📌 *{titre}*\n🏢 {entreprise}  •  📅 {date_pub}\n"

    if sections:
        message += "\n\n" + "\n\n".join(sections)

    return message


def envoyer_offre(offre_data):
    """
    Envoie une offre sur Telegram sous forme de card compacte.
    Les détails complets sont affichés uniquement sur clic du bouton "Voir plus".
    """
    if not TELEGRAM_TOKEN or TELEGRAM_CHAT_ID == 'votre_chat_id_ici':
        print("⚠️  Configuration Telegram manquante (vérifie .env)")
        return False

    try:
        titre = offre_data.get('titre', 'Sans titre')
        entreprise = offre_data.get('entreprise', 'Non spécifiée')
        date_pub = offre_data.get('date_publication', 'Date inconnue')
        url = offre_data.get('url', '')
        details = offre_data.get('details', '')

        # Sauvegarder dans le cache partagé (SQLite)
        cache_key = sauvegarder_offre_cache(offre_data)

        # Résumé compact
        resume_sections = []

        # Résumé missions (2 lignes max)
        if "**Missions:**" in details:
            missions = details.split("**Missions:**")[1].split("**")[0] if "**" in details.split("**Missions:**")[1] else details.split("**Missions:**")[1]
            missions_lines = [line.strip() for line in missions.split('\n') if line.strip() and not line.startswith('•') and not line.startswith('-') and not line.startswith('▪')][:2]
            if missions_lines:
                resume_sections.append("📋 " + " | ".join([line[:50] for line in missions_lines]))

        # Résumé profil (1 ligne)
        if "**Profil recherché:**" in details:
            profil = details.split("**Profil recherché:**")[1].split("**")[0] if "**" in details.split("**Profil recherché:**")[1] else details.split("**Profil recherché:**")[1]
            profil_lines = [line.strip() for line in profil.split('\n') if line.strip() and not line.startswith('•') and not line.startswith('-') and not line.startswith('▪')][:1]
            if profil_lines:
                resume_sections.append(f"👤 {profil_lines[0][:60]}")

        # Construire le message compact
        card_message = f"""💼 *{titre}*

🏢 {entreprise}  •  📅 {date_pub}"""

        if resume_sections:
            card_message += "\n\n" + "\n".join(resume_sections)

        # Boutons: Voir plus (callback) + Postuler (URL)
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "📄 Voir plus", "callback_data": cache_key},
                    {"text": "🔗 Postuler", "url": url}
                ]
            ]
        }

        # Envoyer la card
        response = requests.post(
            f"{TELEGRAM_API_URL}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": card_message,
                "parse_mode": "Markdown",
                "reply_markup": keyboard,
                "disable_web_page_preview": True
            },
            timeout=30
        )

        if response.status_code == 200:
            print(f"  📤 Card envoyée : {titre[:40]}...")
            print(f"     (Clique 'Voir plus' pour les détails)")
            return True
        else:
            print(f"  ⚠️  Erreur Telegram ({response.status_code}): {response.text[:100]}")
            return False

    except Exception as e:
        print(f"  ⚠️  Échec envoi Telegram: {e}")
        return False


def envoyer_message_simple(message):
    """Envoie un message texte simple sur Telegram."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return False

    try:
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }

        response = requests.post(
            f"{TELEGRAM_API_URL}/sendMessage",
            json=payload,
            timeout=30
        )

        return response.status_code == 200

    except:
        return False


def tester_configuration():
    """Teste la configuration Telegram en envoyant un message de test."""
    if not TELEGRAM_TOKEN or TELEGRAM_CHAT_ID == 'votre_chat_id_ici':
        print("❌ Configuration Telegram incomplète")
        print("   Modifie le fichier config/.env avec ton TOKEN et CHAT_ID")
        return False

    print("🧪 Test de la configuration Telegram...")
    success = envoyer_message_simple("✅ *Bot PortalJob activé !*\n\nJe vais t'envoyer les nouvelles offres dès qu'elles sont publiées.")

    if success:
        print("✅ Test réussi - Message envoyé sur Telegram !")
    else:
        print("❌ Test échoué - Vérifie ton TOKEN et CHAT_ID")

    return success


if __name__ == "__main__":
    tester_configuration()
