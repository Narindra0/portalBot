"""
Module de bot Telegram pour envoi des offres PortalJob.
Refactorisé pour utiliser python-telegram-bot (async) et HTML.
"""
import html
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from ..config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
from ..storage.cache_db import ajouter_offre_async, recuperer_profil_matching_async
from ..utils.matcher import analyser_offre
from ..utils.logger import logger

def escape_html(text):
    """Échappe les caractères HTML spéciaux."""
    if not text: return ""
    return html.escape(str(text))

def formater_card_compacte(offre_data, match_result=None):
    """Formate une offre en HTML compact avec score de matching optionnel."""
    titre = escape_html(offre_data.get('titre', 'Sans titre'))
    entreprise = escape_html(offre_data.get('entreprise', 'Non spécifiée'))
    date_pub = escape_html(offre_data.get('date_publication', 'Date inconnue'))

    # Résumé missions (2 premières lignes)
    details = offre_data.get('details', '')
    resume_missions = ""
    if "Missions:" in details:
        missions_part = details.split("Missions:")[1].split("**")[0] if "**" in details.split("Missions:")[1] else details.split("Missions:")[1]
        lines = [l.strip() for l in missions_part.split('\n') if l.strip()][:2]
        if lines:
            resume_missions = "\n" + "\n".join([f"▫️ {escape_html(l[:80])}" for l in lines])

    # Ajouter le score de matching si disponible
    score_html = ""
    if match_result:
        score = match_result.get('score', 0)
        if score >= 80:
            emoji_score = "🔥"
            appreciation = "Excellent match"
        elif score >= 60:
            emoji_score = "✅"
            appreciation = "Bon match"
        elif score >= 40:
            emoji_score = "⚠️"
            appreciation = "Match moyen"
        else:
            emoji_score = "❌"
            appreciation = "Match faible"

        score_html = f"\n\n📊 <b>Match: {score}%</b> {emoji_score} {appreciation}"

        # Ajouter un aperçu des compétences trouvées
        details_match = match_result.get('details', {})
        comp_trouvees = details_match.get('competences_trouvees', [])
        if comp_trouvees:
            comp_list = ", ".join(comp_trouvees[:4])
            if len(comp_trouvees) > 4:
                comp_list += f" +{len(comp_trouvees)-4}"
            score_html += f"\n✓ {len(comp_trouvees)} compétences: {escape_html(comp_list)}"

    return f"💼 <b>{titre}</b>{score_html}\n\n🏢 {entreprise}  •  📅 {date_pub}{resume_missions}"

def formater_details_complets(offre_data):
    """Formate les détails complets en HTML."""
    titre = escape_html(offre_data.get('titre', 'Sans titre'))
    entreprise = escape_html(offre_data.get('entreprise', 'Non spécifiée'))
    url = offre_data.get('url', '')
    details = offre_data.get('details', '')

    msg = f"📌 <b>{titre}</b>\n🏢 {entreprise}\n\n"
    
    import re
    # Extraction dynamique de toutes les sections délimitées par **Titre:**
    # On cherche le motif **Texte:** suivi du contenu jusqu'au prochain ** ou la fin
    sections = re.findall(r'\*\*(.*?):\*\*\n(.*?)(?=\n\n\*\*|\Z)', details, re.DOTALL)
    
    sections_html = []
    emojis_map = {
        "Missions": "📋",
        "Profil recherché": "👤",
        "Activité de l'entreprise": "💼",
        "Activité entreprise": "💼",
        "Atouts": "⭐",
        "Avantages": "🎁",
        "Conditions": "📝"
    }

    for titre, contenu in sections:
        titre_clean = titre.strip()
        emoji = emojis_map.get(titre_clean, "🔹")
        sections_html.append(f"{emoji} <b>{titre_clean.upper()}</b>\n{escape_html(contenu.strip()[:1500])}")

    if sections_html:
        msg += "\n\n".join(sections_html)
    else:
        # Fallback si le formatage **...** a échoué
        msg += escape_html(details[:3500])

    # Liens Intelligence
    intel_links = []
    if offre_data.get('website_url'): intel_links.append(f'🌐 <a href="{offre_data["website_url"]}">Site Web</a>')
    if intel_links:
        msg += "\n\n" + " | ".join(intel_links)

    msg += f'\n\n🚀 <a href="{url}">Postuler sur la source</a>'
    return msg

async def envoyer_offre_async(bot, offre_data):
    """Envoie une offre sur Telegram avec score de matching."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Configuration Telegram manquante")
        return False

    try:
        # Sauvegarder dans le cache temporaire pour le callback "Voir plus"
        cache_key = await ajouter_offre_async(offre_data)

        # Calculer le score de matching
        match_result = None
        try:
            profil = await recuperer_profil_matching_async()
            if profil:
                match_result = analyser_offre(offre_data, profil)
                logger.info(f"📊 Match score: {match_result.get('score', 0)}% pour {offre_data.get('titre', '')[:40]}")
        except Exception as e:
            logger.warning(f"Impossible de calculer le matching: {e}")

        text = formater_card_compacte(offre_data, match_result)

        # Construction dynamique du clavier
        boutons_principaux = [
            InlineKeyboardButton("📄 Voir plus", callback_data=cache_key),
            InlineKeyboardButton("🔗 Lien Original", url=offre_data.get('url', ''))
        ]

        # Ajouter bouton détail matching si disponible
        if match_result and match_result.get('score', 0) > 0:
            boutons_principaux.append(InlineKeyboardButton("📊 Pourquoi ce match ?", callback_data=f"match_{cache_key}"))

        boutons_intel = []
        if offre_data.get('linkedin_url'):
            boutons_intel.append(InlineKeyboardButton("🟦 LinkedIn", url=offre_data['linkedin_url']))
        if offre_data.get('facebook_url'):
            boutons_intel.append(InlineKeyboardButton("🟦 Facebook", url=offre_data['facebook_url']))

        layout = [boutons_principaux]
        if boutons_intel:
            layout.append(boutons_intel)

        keyboard = InlineKeyboardMarkup(layout)

        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
        logger.info(f"📤 Offre envoyée: {offre_data.get('titre', '')}")
        return True
    except Exception as e:
        logger.error(f"Erreur envoi Telegram: {e}")
        return False

# Fonction sync pour test rapide ou compatibilité
def envoyer_offre(offre_data):
    # Note: Dans le nouveau système async, cette fonction ne sera plus utilisée directement par le scraper.
    logger.warning("Appel à envoyer_offre (sync) - devrait être migré vers envoyer_offre_async")
    return True
