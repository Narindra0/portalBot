"""
Gestionnaire de callbacks Telegram pour afficher les détails sur demande.
À exécuter en parallèle du scraper pour répondre aux boutons "Voir plus".
"""
import os
import time
import json
import requests
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config', '.env'))

from ..storage import recuperer_offre, sauvegarder_cv, vider_cache
from ..llm import creer_lettre_motivation, formater_lettre_pour_telegram
from ..storage import traiter_fichier_cv

# Sessions de configuration CV (en mémoire)
cv_sessions = {}
cv_file_sessions = {}  # Pour stocker les fichiers PDF/image en attente de nom/email
processed_callbacks = set()  # Pour éviter les doublons de callbacks

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"


def formater_details_complets(offre_data):
    """Formate les détails complets pour Telegram."""
    titre = offre_data.get('titre', 'Sans titre')
    entreprise = offre_data.get('entreprise', 'Non spécifiée')
    url = offre_data.get('url', '')
    details = offre_data.get('details', '')

    detail_sections = []

    if "**Activité entreprise:**" in details:
        activite = details.split("**Activité entreprise:**")[1].split("**Missions:**")[0] if "**Missions:**" in details else details.split("**Activité entreprise:**")[1]
        activite_clean = activite.strip()
        if activite_clean:
            detail_sections.append(f"💼 *ACTIVITÉ ENTREPRISE*\n{activite_clean[:500]}")

    if "**Missions:**" in details:
        missions = details.split("**Missions:**")[1].split("**Profil recherché:**")[0] if "**Profil recherché:**" in details else details.split("**Missions:**")[1]
        missions_clean = missions.strip()
        if missions_clean:
            missions_formatted = missions_clean.replace("- ", "▫️ ").replace("• ", "▫️ ")
            detail_sections.append(f"📋 *MISSIONS*\n{missions_formatted[:600]}")

    if "**Profil recherché:**" in details:
        profil = details.split("**Profil recherché:**")[1].split("**")[0] if "**" in details.split("**Profil recherché:**")[1] else details.split("**Profil recherché:**")[1]
        profil_clean = profil.strip()
        if profil_clean:
            profil_formatted = profil_clean.replace("- ", "▫️ ").replace("• ", "▫️ ")
            detail_sections.append(f"👤 *PROFIL RECHERCHÉ*\n{profil_formatted[:500]}")

    if detail_sections:
        message = f"📌 *{titre}*\n🏢 {entreprise}\n\n"
        message += "\n\n".join(detail_sections)
        message += f"\n\n[🚀 Postuler]({url})"
        return message
    return None


def envoyer_details_par_callback(callback_query_id, cache_key):
    """Envoie les détails en réponse à un callback."""
    # Récupérer l'offre depuis le cache partagé (SQLite)
    offre_data = recuperer_offre(cache_key)

    if offre_data is None:
        # Répondre au callback avec une erreur
        requests.post(
            f"{TELEGRAM_API_URL}/answerCallbackQuery",
            json={
                "callback_query_id": callback_query_id,
                "text": "❌ Détails non disponibles (expirés)\n\nRe-lance le scraper pour rafraîchir.",
                "show_alert": True
            }
        )
        return False

    details_message = formater_details_complets(offre_data)

    if not details_message:
        requests.post(
            f"{TELEGRAM_API_URL}/answerCallbackQuery",
            json={
                "callback_query_id": callback_query_id,
                "text": "❌ Aucun détail disponible",
                "show_alert": True
            }
        )
        return False

    # Ajouter le bouton "Créer LM" aux détails
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "📝 Créer Lettre de Motivation", "callback_data": f"lm_{cache_key}"}
            ]
        ]
    }

    # Envoyer les détails avec le bouton
    response = requests.post(
        f"{TELEGRAM_API_URL}/sendMessage",
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": details_message,
            "parse_mode": "Markdown",
            "reply_markup": keyboard,
            "disable_web_page_preview": True
        }
    )

    if response.status_code == 200:
        # Accuser réception du callback
        requests.post(
            f"{TELEGRAM_API_URL}/answerCallbackQuery",
            json={
                "callback_query_id": callback_query_id,
                "text": "✅ Détails affichés !"
            }
        )
        return True
    return False


def generer_lm_par_callback(callback_query_id, cache_key):
    """Génère et envoie une lettre de motivation."""
    # Récupérer l'offre
    offre_data = recuperer_offre(cache_key)

    if offre_data is None:
        requests.post(
            f"{TELEGRAM_API_URL}/answerCallbackQuery",
            json={
                "callback_query_id": callback_query_id,
                "text": "❌ Offre non disponible (expirée)",
                "show_alert": True
            }
        )
        return False

    # Informer l'utilisateur que la génération commence
    requests.post(
        f"{TELEGRAM_API_URL}/answerCallbackQuery",
        json={
            "callback_query_id": callback_query_id,
            "text": "🤖 Génération de la lettre en cours..."
        }
    )

    print(f"📝 Génération LM pour: {offre_data.get('titre', 'Unknown')}")

    # Générer la lettre
    success, result = creer_lettre_motivation(offre_data)

    if not success:
        # Envoyer le message d'erreur
        requests.post(
            f"{TELEGRAM_API_URL}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": result,
                "parse_mode": "Markdown"
            }
        )
        return False

    # Formater et envoyer la lettre
    lettre = result
    parties = formater_lettre_pour_telegram(lettre)

    # Envoyer l'en-tête
    titre = offre_data.get('titre', 'Poste')
    entreprise = offre_data.get('entreprise', 'Entreprise')

    header = f"✉️ *LETTRE DE MOTIVATION*\n📌 {titre}\n🏢 {entreprise}\n\n"
    header += "```\n" + "═" * 40 + "\n```"

    requests.post(
        f"{TELEGRAM_API_URL}/sendMessage",
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": header,
            "parse_mode": "Markdown"
        }
    )

    # Envoyer la lettre (potentiellement en plusieurs parties)
    for i, partie in enumerate(parties):
        requests.post(
            f"{TELEGRAM_API_URL}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": partie,
                "parse_mode": "Markdown"
            }
        )

    # Envoyer le footer
    footer = "```\n" + "═" * 40 + "\n```\n"
    footer += "✅ *Lettre prête à l'emploi !*\n"
    footer += "💡 _Tu peux copier/coller cette lettre dans ton email ou PortalJob_"

    requests.post(
        f"{TELEGRAM_API_URL}/sendMessage",
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": footer,
            "parse_mode": "Markdown"
        }
    )

    print(f"✅ Lettre envoyée ({len(lettre)} caractères)")
    return True


def envoyer_message(chat_id, text, parse_mode="Markdown"):
    """Helper pour envoyer un message."""
    requests.post(
        f"{TELEGRAM_API_URL}/sendMessage",
        json={"chat_id": chat_id, "text": text, "parse_mode": parse_mode},
        timeout=10
    )


def gerer_commande_cv(message):
    """Gère les commandes de configuration CV et fichiers."""
    chat_id = message['chat']['id']
    text = message.get('text', '').strip()
    user_id = message['from']['id']

    # Vérifier si c'est un fichier (PDF ou image)
    if 'document' in message:
        print(f"📄 Fichier détecté de {user_id}")
        return gerer_fichier_cv(message, chat_id, user_id)
    elif 'photo' in message:
        print(f"🖼️ Photo détectée de {user_id}")
        return gerer_fichier_cv(message, chat_id, user_id)

    # Commandes
    if text == '/configurer_cv' or text == '/start':
        # Démarrer la configuration avec option fichier
        cv_sessions[user_id] = {'etape': 'choix_format', 'data': {}}
        msg = """📝 *Configuration du CV*

Choisis comment fournir ton CV:

📄 *Option 1:* Envoie un **PDF** ou une **photo** de ton CV
✏️ *Option 2:* Tape `texte` pour saisir manuellement

💡 *Conseil:* L'option fichier est plus rapide et accepte les CV Canva en PDF ou photo !"""
        envoyer_message(chat_id, msg)
        return True

    elif text == '/voir_cv':
        cv = recuperer_cv()
        if cv:
            msg = f"📄 *Ton CV actuel*\n\n👤 {cv['nom']}\n📧 {cv['email']}\n📱 {cv['telephone'] or 'Non renseigné'}\n\n📝 *Contenu :*\n```\n{cv['cv_text'][:300]}...\n```\n\n_Mis à jour le : {cv['date_mise_a_jour']}_"
            envoyer_message(chat_id, msg)
        else:
            envoyer_message(chat_id, "❌ *Aucun CV configuré*\n\nUtilise `/configurer_cv` pour commencer.")
        return True

    elif text == '/supprimer_cv':
        vider_cache()
        envoyer_message(chat_id, "🗑️ *CV supprimé*\n\nUtilise `/configurer_cv` pour en créer un nouveau.")
        return True

    elif text == '/aide':
        aide = """📚 *Commandes disponibles :*

📝 `/configurer_cv` - Créer/modifier ton CV (texte ou fichier PDF/photo)
👁️ `/voir_cv` - Voir ton CV actuel
🗑️ `/supprimer_cv` - Supprimer ton CV
❓ `/aide` - Afficher cette aide

💡 *Tu peux envoyer un PDF ou une photo de ton CV !*"""
        envoyer_message(chat_id, aide)
        return True

    # Gestion des étapes de configuration
    if user_id in cv_sessions:
        session = cv_sessions[user_id]
        etape = session['etape']

        if etape == 'choix_format':
            if text.lower() == 'texte':
                session['etape'] = 'nom'
                envoyer_message(chat_id, "✏️ *Mode texte choisi*\n\nÉtape 1/4 : Quel est ton *nom complet* ?")
            else:
                envoyer_message(chat_id, "❓ Je n'ai pas compris. Tape `texte` pour saisir manuellement, ou envoie directement un PDF/photo.")
            return True

        elif etape == 'nom':
            session['data']['nom'] = text
            session['etape'] = 'email'
            envoyer_message(chat_id, "✅ Nom enregistré\n\nÉtape 2/4 : Quel est ton *email* ?")
            return True

        elif etape == 'email':
            session['data']['email'] = text
            session['etape'] = 'telephone'
            envoyer_message(chat_id, "✅ Email enregistré\n\nÉtape 3/4 : Quel est ton *téléphone* ? (ou 'skip')")
            return True

        elif etape == 'telephone':
            session['data']['telephone'] = text if text.lower() != 'skip' else ''
            session['etape'] = 'cv'
            envoyer_message(chat_id, "✅ Téléphone enregistré\n\nÉtape 4/4 : *Colle ton CV complet ici*\n\nInclue :\n• Compétences techniques\n• Expériences professionnelles\n• Formation\n• Projets réalisés")
            return True

        elif etape == 'cv':
            # Sauvegarder le CV manuel
            data = session['data']
            sauvegarder_cv(data['nom'], data['email'], data['telephone'], text)
            del cv_sessions[user_id]

            msg = f"✅ *CV sauvegardé avec succès !*\n\n👤 {data['nom']}\n📧 {data['email']}\n\nTu peux maintenant générer des lettres de motivation."
            envoyer_message(chat_id, msg)
            return True

        # Gestion fichier: file_processing (transition vers file_nom) ou file_nom
        elif etape in ['file_processing', 'file_nom']:
            session['data']['nom'] = text
            session['etape'] = 'file_email'
            envoyer_message(chat_id, "✅ Nom enregistré\n\nÉtape 2/3 : Quel est ton *email* ?")
            return True

        # Gestion fichier: email
        elif etape == 'file_email':
            session['data']['email'] = text
            session['etape'] = 'file_telephone'
            envoyer_message(chat_id, "✅ Email enregistré\n\nÉtape 3/3 : Quel est ton *téléphone* ? (ou 'skip')")
            return True

        # Gestion fichier: telephone -> extraction
        elif etape == 'file_telephone':
            session['data']['telephone'] = text if text.lower() != 'skip' else ''

            # Extraire le texte du fichier
            envoyer_message(chat_id, "🔍 *Extraction du texte en cours...*\n\nJe lis ton fichier PDF/image avec OCR, patience...")

            file_info = cv_file_sessions.get(user_id, {})
            file_id = file_info.get('file_id')
            mime_type = file_info.get('mime_type')

            if file_id:
                success, result = traiter_fichier_cv(file_id, TELEGRAM_TOKEN, mime_type)

                if success:
                    # Sauvegarder avec le texte extrait
                    data = session['data']
                    sauvegarder_cv(data['nom'], data['email'], data['telephone'], result)

                    # Cleanup
                    del cv_sessions[user_id]
                    if user_id in cv_file_sessions:
                        del cv_file_sessions[user_id]

                    preview = result[:200] + "..." if len(result) > 200 else result
                    msg = f"✅ *CV sauvegardé avec succès !*\n\n👤 {data['nom']}\n📧 {data['email']}\n\n📝 *Texte extrait ({len(result)} caractères):*\n```\n{preview}\n```\n\nTu peux maintenant générer des lettres de motivation !"
                    envoyer_message(chat_id, msg)
                else:
                    # Échec extraction
                    msg = f"❌ *Échec de l'extraction*\n\n{result}\n\nTu peux réessayer avec un autre fichier ou utiliser la méthode texte manuel avec `/configurer_cv` puis tape `texte`."
                    envoyer_message(chat_id, msg)
                    del cv_sessions[user_id]
                    if user_id in cv_file_sessions:
                        del cv_file_sessions[user_id]
            else:
                envoyer_message(chat_id, "❌ *Erreur: fichier non trouvé*\n\nMerci de recommencer avec `/configurer_cv`.")
                del cv_sessions[user_id]

            return True

    return False


def gerer_fichier_cv(message, chat_id, user_id):
    """Gère la réception d'un fichier CV (PDF ou image)."""
    file_id = None
    mime_type = None
    file_name = None

    # Détecter le type de fichier
    if 'document' in message:
        doc = message['document']
        file_id = doc['file_id']
        mime_type = doc.get('mime_type', '')
        file_name = doc.get('file_name', 'document.pdf')
        print(f"📄 Document reçu: {file_name} ({mime_type})")

    elif 'photo' in message:
        # Prendre la plus grande résolution
        photos = message['photo']
        largest = photos[-1]  # Dernière = plus grande
        file_id = largest['file_id']
        mime_type = 'image/jpeg'
        print(f"🖼️ Photo reçue: {largest['width']}x{largest['height']}")

    if not file_id:
        envoyer_message(chat_id, "❌ *Fichier non reconnu*")
        return True

    # Vérifier si c'est une étape de configuration
    if user_id not in cv_sessions:
        # Démarrer automatiquement la config
        cv_sessions[user_id] = {'etape': 'file_processing', 'data': {}}
        cv_file_sessions[user_id] = {'file_id': file_id, 'mime_type': mime_type}
        envoyer_message(chat_id, "📝 *Configuration du CV par fichier*\n\nJ'ai bien reçu ton fichier !\n\nÉtape 1/3 : Quel est ton *nom complet* ?")
        return True

    session = cv_sessions[user_id]

    if session['etape'] == 'choix_format':
        # L'utilisateur a envoyé un fichier directement
        cv_file_sessions[user_id] = {'file_id': file_id, 'mime_type': mime_type}
        session['etape'] = 'file_nom'
        envoyer_message(chat_id, "📄 *Fichier reçu !*\n\nÉtape 1/3 : Quel est ton *nom complet* ?")
        return True

    if session['etape'] in ['file_processing', 'file_nom']:
        cv_file_sessions[user_id] = {'file_id': file_id, 'mime_type': mime_type}
        session['etape'] = 'file_nom'
        envoyer_message(chat_id, "📄 *Fichier mis à jour !*\n\nQuel est ton *nom complet* ?")
        return True

    return False


def poll_callbacks():
    """Poll les callbacks Telegram et répond aux boutons 'Voir plus'."""
    if not TELEGRAM_TOKEN or TELEGRAM_CHAT_ID == 'votre_chat_id_ici':
        print("⚠️  Configuration Telegram manquante")
        return

    print("🤖 Gestionnaire de callbacks Telegram démarré...")
    print("   Commandes CV: /configurer_cv, /voir_cv, /supprimer_cv, /aide")
    print("   Appuie sur Ctrl+C pour arrêter")
    print()

    offset = 0

    while True:
        try:
            # Récupérer les updates
            response = requests.get(
                f"{TELEGRAM_API_URL}/getUpdates",
                params={"offset": offset, "limit": 10},
                timeout=30
            )

            if response.status_code != 200:
                time.sleep(5)
                continue

            data = response.json()

            if not data.get('ok') or not data.get('result'):
                time.sleep(2)
                continue

            for update in data['result']:
                # Mettre à jour l'offset
                offset = update['update_id'] + 1

                # Vérifier si c'est un message (texte, document ou photo)
                if 'message' in update:
                    message = update['message']
                    chat_id = message['chat']['id']

                    # Vérifier si c'est une commande CV (texte ou fichier)
                    if chat_id == int(TELEGRAM_CHAT_ID):
                        if gerer_commande_cv(message):
                            continue

                # Vérifier si c'est un callback
                if 'callback_query' in update:
                    callback = update['callback_query']
                    callback_id = callback['id']
                    callback_data = callback.get('data', '')

                    # Éviter les doublons - vérifier si déjà traité
                    if callback_id in processed_callbacks:
                        continue
                    processed_callbacks.add(callback_id)

                    # Limiter la taille du set pour éviter la fuite mémoire
                    if len(processed_callbacks) > 1000:
                        processed_callbacks.clear()

                    # Vérifier le type de callback
                    if callback_data.startswith('offre_'):
                        cache_key = callback_data
                        print(f"📎 Callback 'Voir plus': {cache_key}")
                        envoyer_details_par_callback(callback_id, cache_key)

                    elif callback_data.startswith('lm_'):
                        # Extraire la clé de l'offre (enlever le préfixe 'lm_')
                        cache_key = callback_data[3:]
                        print(f"📝 Callback 'Créer LM': {cache_key}")
                        generer_lm_par_callback(callback_id, cache_key)

            time.sleep(1)

        except KeyboardInterrupt:
            print("\n👋 Gestionnaire arrêté")
            break
        except Exception as e:
            print(f"⚠️  Erreur polling: {e}")
            time.sleep(5)


if __name__ == "__main__":
    poll_callbacks()
