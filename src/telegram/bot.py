"""
Module de bot Telegram pour envoi des offres PortalJob.
Refactorisé pour utiliser python-telegram-bot (async) et HTML.
"""
import html
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from ..config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
from ..storage.cache_db import ajouter_offre_async
from ..utils.logger import logger

def escape_html(text):
    """Échappe les caractères HTML spéciaux."""
    if not text: return ""
    return html.escape(str(text))

def formater_card_compacte(offre_data):
    """Formate une offre en HTML compact."""
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

    return f"💼 <b>{titre}</b>\n\n🏢 {entreprise}  •  📅 {date_pub}{resume_missions}"

def formater_details_complets(offre_data):
    """Formate les détails complets en HTML."""
    titre = escape_html(offre_data.get('titre', 'Sans titre'))
    entreprise = escape_html(offre_data.get('entreprise', 'Non spécifiée'))
    url = offre_data.get('url', '')
    details = offre_data.get('details', '')

    msg = f"📌 <b>{titre}</b>\n🏢 {entreprise}\n\n"
    
    # Extraction plus robuste des sections basées sur les marqueurs **...**
    def extraire_section(texte, prefix):
        if prefix not in texte: return None
        # On découpe à partir du préfixe
        suite = texte.split(prefix)[1]
        # On s'arrête au prochain marqueur de section **
        if "**" in suite:
            return suite.split("**")[0].strip()
        return suite.strip()

    act = extraire_section(details, "**Activité entreprise:**")
    miss = extraire_section(details, "**Missions:**")
    prof = extraire_section(details, "**Profil recherché:**")

    sections_html = []
    # Augmentation des limites (max total ~4000 par message Telegram)
    if act:
        sections_html.append(f"💼 <b>ACTIVITÉ ENTREPRISE</b>\n{escape_html(act[:1000])}")
    if miss:
        sections_html.append(f"📋 <b>MISSIONS</b>\n{escape_html(miss[:2000])}")
    if prof:
        sections_html.append(f"👤 <b>PROFIL RECHERCHÉ</b>\n{escape_html(prof[:1000])}")

    if sections_html:
        msg += "\n\n".join(sections_html)
    else:
        # Fallback si aucun tag n'est trouvé
        msg += escape_html(details[:3500])

    # Liens Intelligence
    intel_links = []
    if offre_data.get('website_url'): intel_links.append(f'🌐 <a href="{offre_data["website_url"]}">Site Web</a>')
    if intel_links:
        msg += "\n\n" + " | ".join(intel_links)

    msg += f'\n\n🚀 <a href="{url}">Postuler sur la source</a>'
    return msg

async def envoyer_offre_async(bot, offre_data):
    """Envoie une offre sur Telegram."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Configuration Telegram manquante")
        return False

    try:
        # Sauvegarder dans le cache temporaire pour le callback "Voir plus"
        cache_key = await ajouter_offre_async(offre_data)
        
        text = formater_card_compacte(offre_data)
        
        # Construction dynamique du clavier
        boutons_principaux = [
            InlineKeyboardButton("📄 Voir plus", callback_data=cache_key),
            InlineKeyboardButton("🔗 Postuler", url=offre_data.get('url', ''))
        ]
        
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
