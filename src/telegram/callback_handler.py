"""
Gestionnaire Telegram (Bot complet) pour PortalJob.
Utilise python-telegram-bot v20+ pour une stabilité maximale.
Gère les commandes, les callbacks et la configuration du CV.
"""
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ContextTypes, ConversationHandler
)
from telegram.constants import ParseMode

from ..config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
from ..storage.cache_db import (
    recuperer_offre_async, sauvegarder_cv_async, 
    recuperer_cv_async, vider_cache
)
from ..storage.pdf_extractor import traiter_fichier_cv
from ..llm.generator import creer_lettre_motivation, formater_lettre_pour_telegram
from .bot import formater_details_complets
from ..utils.logger import logger
from ..utils.intel import CompanyIntel

# États de la conversation pour la configuration du CV
CHOOSING, TYPING_NAME, TYPING_EMAIL, TYPING_PHONE, TYPING_PORTFOLIO, TYPING_CV = range(6)
FILE_TYPING_NAME, FILE_TYPING_EMAIL, FILE_TYPING_PHONE, FILE_TYPING_PORTFOLIO = range(6, 10)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /start."""
    if str(update.effective_chat.id) != str(TELEGRAM_CHAT_ID):
        return
        
    msg = (
        "👋 <b>Bienvenue sur PortalJob Scraper !</b>\n\n"
        "Je suis configuré pour t'envoyer les dernières offres de développement à Madagascar.\n\n"
        "🏠 <b>Commandes disponibles :</b>\n"
        "/configurer_cv - Configurer ton profil pour les lettres de motivation\n"
        "/voir_cv - Voir ton profil actuel\n"
        "/aide - Afficher l'aide"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

async def aide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /aide."""
    msg = (
        "📚 <b>Aide PortalJob</b>\n\n"
        "• <b>Scraping</b> : Je vérifie PortalJob toutes les 30 minutes.\n"
        "• <b>Lettres de Motivation</b> : Une fois ton CV configuré, tu peux cliquer sur 'Créer Lettre' sous n'importe quelle offre.\n\n"
        "⚙️ <b>Commandes :</b>\n"
        "/configurer_cv : Créer ou modifier ton profil\n"
        "/voir_cv : Afficher tes infos enregistrées\n"
        "/supprimer_cv : Effacer tes données"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gère tous les clics de boutons."""
    query = update.callback_query
    data = query.data
    await query.answer()

    if data.startswith("offre_"):
        # Afficher les détails complets
        offre = await recuperer_offre_async(data)
        if not offre:
            await query.edit_message_text("❌ Détails non disponibles ou expirés.")
            return

        text = formater_details_complets(offre)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 Créer Lettre de Motivation", callback_data=f"lm_{data}")],
            [InlineKeyboardButton("🔍 Profil Société", callback_data=f"intel_{data}")]
        ])
        
        # On envoie un nouveau message pour les détails (plus lisible)
        await context.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )

    elif data.startswith("lm_"):
        # Générer une lettre de motivation
        cache_key = data[3:]
        offre = await recuperer_offre_async(cache_key)
        if not offre:
            await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text="❌ Offre expirée.")
            return

        cv = await recuperer_cv_async()
        if not cv:
            await context.bot.send_message(
                chat_id=TELEGRAM_CHAT_ID, 
                text="⚠️ Tu n'as pas encore configuré ton CV. Utilise /configurer_cv."
            )
            return

        status_msg = await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text="🤖 Génération de la lettre en cours...")
        
        # Appel au LLM (bloquant mais on peut le rendre async si besoin, generator.py le gère)
        success, result = await creer_lettre_motivation(offre)
        
        await status_msg.delete()
        
        if success:
            parties = formater_lettre_pour_telegram(result)
            header = f"✉️ <b>LETTRE DE MOTIVATION</b>\n📌 {offre['titre']}\n🏢 {offre['entreprise']}\n"
            await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=header, parse_mode=ParseMode.HTML)
            
            for p in parties:
                await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=p)
                
            footer = "✅ <b>Lettre prête !</b>"
            await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=footer, parse_mode=ParseMode.HTML)
        else:
            await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f"❌ Erreur génération: {result}")

    elif data.startswith("intel_"):
         # Recherche d'intelligence société auto
         cache_key = data[6:]
         offre = await recuperer_offre_async(cache_key)
         if not offre:
             await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text="❌ Offre expirée.")
             return
         
         nom = offre.get('entreprise')
         msg_wait = await context.bot.send_message(
             chat_id=TELEGRAM_CHAT_ID, 
             text=f"🔍 Recherche d'infos sur <b>{nom}</b>...", 
             parse_mode=ParseMode.HTML
         )
         
         intel = await CompanyIntel.search_company_info(nom)
         await msg_wait.delete()
         
         if not intel or not any(intel.values()):
             await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f"❌ Aucune info trouvée pour <b>{nom}</b>.", parse_mode=ParseMode.HTML)
             return
             
         res = f"📊 <b>Intelligence Entreprise : {nom}</b>\n\n"
         if intel['website']: res += f"🌐 <b>Site</b> : {intel['website']}\n"
         if intel['linkedin']: res += f"🟦 <b>LinkedIn</b> : {intel['linkedin']}\n"
         if intel['facebook']: res += f"🟦 <b>Facebook</b> : {intel['facebook']}\n"
         
         boutons = []
         if intel['linkedin']: boutons.append(InlineKeyboardButton("LinkedIn", url=intel['linkedin']))
         if intel['facebook']: boutons.append(InlineKeyboardButton("Facebook", url=intel['facebook']))
         if intel['website']: boutons.append(InlineKeyboardButton("Site Web", url=intel['website']))
         
         keyboard = InlineKeyboardMarkup([boutons]) if boutons else None
         await context.bot.send_message(
             chat_id=TELEGRAM_CHAT_ID, 
             text=res, 
             parse_mode=ParseMode.HTML, 
             reply_markup=keyboard, 
             disable_web_page_preview=True
         )

# --- CONFIGURATION CV (CONVERSATION) ---

async def voir_cv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /voir_cv."""
    cv = await recuperer_cv_async()
    if not cv:
        await update.message.reply_text("⚠️ Aucun profil configuré. Utilise /configurer_cv.")
        return

    msg = (
        "👤 <b>Ton Profil Actuel</b>\n\n"
        f"📛 <b>Nom</b> : {cv['nom']}\n"
        f"📧 <b>Email</b> : {cv['email']}\n"
        f"📱 <b>Tel</b> : {cv['telephone'] or 'Non spécifié'}\n"
        f"🌐 <b>Portfolio</b> : {cv['portfolio'] or 'Non spécifié'}\n\n"
        "📄 <b>Résumé du CV</b> :\n"
        f"<code>{cv['cv_text'][:500]}...</code>"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

async def config_cv_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cv = await recuperer_cv_async()
    prefix = "🔄 <b>Mise à jour de ton profil</b>\n\n" if cv else "📝 <b>Configuration du CV</b>\n\n"
    
    msg = (
        f"{prefix}"
        "Comment souhaites-tu fournir tes informations ?\n\n"
        "📄 <b>Option 1</b> : Envoie un PDF ou une Photo (OCR)\n"
        "✏️ <b>Option 2</b> : Tape 'texte' pour saisir manuellement"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
    return CHOOSING

async def search_company_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /search <nom_entreprise>."""
    if not context.args:
        await update.message.reply_text("🔎 Utilisation : <code>/search Nom de l'entreprise</code>", parse_mode=ParseMode.HTML)
        return

    nom = " ".join(context.args)
    msg_wait = await update.message.reply_text(f"🔍 Recherche d'infos sur <b>{nom}</b>...", parse_mode=ParseMode.HTML)
    
    intel = await CompanyIntel.search_company_info(nom)
    
    if not intel or not any(intel.values()):
        await msg_wait.edit_text(f"❌ Désolé, aucune information trouvée pour <b>{nom}</b>.", parse_mode=ParseMode.HTML)
        return

    res = f"📊 <b>Résultats pour {nom}</b> :\n\n"
    if intel['website']: res += f"🌐 <b>Site</b> : {intel['website']}\n"
    if intel['linkedin']: res += f"🟦 <b>LinkedIn</b> : {intel['linkedin']}\n"
    if intel['facebook']: res += f"🟦 <b>Facebook</b> : {intel['facebook']}\n"
    
    boutons = []
    if intel['linkedin']: boutons.append(InlineKeyboardButton("LinkedIn", url=intel['linkedin']))
    if intel['facebook']: boutons.append(InlineKeyboardButton("Facebook", url=intel['facebook']))
    if intel['website']: boutons.append(InlineKeyboardButton("Site Web", url=intel['website']))
    
    keyboard = InlineKeyboardMarkup([boutons]) if boutons else None
    await msg_wait.delete()
    await update.message.reply_text(res, parse_mode=ParseMode.HTML, reply_markup=keyboard, disable_web_page_preview=True)

async def config_cv_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if text == "texte":
        await update.message.reply_text("✏️ Quel est ton <b>nom complet</b> ?", parse_mode=ParseMode.HTML)
        return TYPING_NAME
    return CHOOSING

async def config_cv_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['nom'] = update.message.text
    await update.message.reply_text("📧 Quel est ton <b>email</b> ?", parse_mode=ParseMode.HTML)
    return TYPING_EMAIL

async def config_cv_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['email'] = update.message.text
    await update.message.reply_text("📱 Quel est ton <b>téléphone</b> ? (ou tape 'skip')", parse_mode=ParseMode.HTML)
    return TYPING_PHONE

async def config_cv_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['phone'] = "" if update.message.text.lower() == "skip" else update.message.text
    await update.message.reply_text("🌐 As-tu un <b>blog ou portfolio</b> ? (ou tape 'skip')", parse_mode=ParseMode.HTML)
    return TYPING_PORTFOLIO

async def config_cv_portfolio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['portfolio'] = "" if update.message.text.lower() == "skip" else update.message.text
    await update.message.reply_text("📄 <b>Colle ton CV complet ici</b> (Expériences, Compétences...) :", parse_mode=ParseMode.HTML)
    return TYPING_CV

async def config_cv_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cv_text = update.message.text
    portfolio = context.user_data.get('portfolio', '')
    await sauvegarder_cv_async(
        context.user_data['nom'],
        context.user_data['email'],
        context.user_data['phone'],
        portfolio,
        cv_text
    )
    await update.message.reply_text("✅ <b>CV enregistré avec succès !</b>", parse_mode=ParseMode.HTML)
    return ConversationHandler.END

async def config_cv_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gère la réception d'un fichier pendant la conversation."""
    file = update.message.document or update.message.photo[-1]
    context.user_data['file_id'] = file.file_id
    context.user_data['mime_type'] = update.message.document.mime_type if update.message.document else "image/jpeg"
    
    await update.message.reply_text("📄 Fichier reçu ! Quel est ton <b>nom complet</b> ?", parse_mode=ParseMode.HTML)
    return FILE_TYPING_NAME

async def config_cv_file_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['nom'] = update.message.text
    await update.message.reply_text("📧 Quel est ton <b>email</b> ?", parse_mode=ParseMode.HTML)
    return FILE_TYPING_EMAIL

async def config_cv_file_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['email'] = update.message.text
    await update.message.reply_text("📱 Quel est ton <b>téléphone</b> ? (ou 'skip')", parse_mode=ParseMode.HTML)
    return FILE_TYPING_PHONE

async def config_cv_file_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['phone'] = "" if update.message.text.lower() == "skip" else update.message.text
    await update.message.reply_text("🌐 As-tu un <b>blog ou portfolio</b> ? (ou 'skip')", parse_mode=ParseMode.HTML)
    return FILE_TYPING_PORTFOLIO

async def config_cv_file_portfolio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    portfolio = "" if update.message.text.lower() == "skip" else update.message.text
    status_msg = await update.message.reply_text("🔍 <b>Extraction en cours...</b>", parse_mode=ParseMode.HTML)
    
    # Extraction (peut être longue)
    success, result = await traiter_fichier_cv(context.user_data['file_id'], TELEGRAM_TOKEN, context.user_data['mime_type'])
    
    await status_msg.delete()
    
    if success:
        await sauvegarder_cv_async(
            context.user_data['nom'], 
            context.user_data['email'], 
            context.user_data['phone'], 
            portfolio,
            result
        )
        await update.message.reply_text(f"✅ <b>CV enregistré !</b>\nExtrait : <code>{result[:100]}...</code>", parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(f"❌ Erreur extraction : {result}")
        
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Annulé.")
    return ConversationHandler.END

# --- INITIALISATION ---

def setup_application():
    """Configure l'application Telegram."""
    if not TELEGRAM_TOKEN:
        return None
        
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Conversation Handler pour CV
    cv_handler = ConversationHandler(
        entry_points=[CommandHandler("configurer_cv", config_cv_start)],
        states={
            CHOOSING: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, config_cv_choice),
                MessageHandler(filters.Document.ALL | filters.PHOTO, config_cv_file)
            ],
            TYPING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, config_cv_name)],
            TYPING_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, config_cv_email)],
            TYPING_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, config_cv_phone)],
            TYPING_PORTFOLIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, config_cv_portfolio)],
            TYPING_CV: [MessageHandler(filters.TEXT & ~filters.COMMAND, config_cv_save)],
            FILE_TYPING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, config_cv_file_name)],
            FILE_TYPING_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, config_cv_file_email)],
            FILE_TYPING_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, config_cv_file_phone)],
            FILE_TYPING_PORTFOLIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, config_cv_file_portfolio)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("aide", aide))
    app.add_handler(CommandHandler("voir_cv", voir_cv))
    app.add_handler(CommandHandler("search", search_company_cmd))
    app.add_handler(cv_handler)
    app.add_handler(CallbackQueryHandler(handle_callback))
    
    return app

def run_bot():
    """Lance le bot en mode polling (pour usage indépendant)."""
    app = setup_application()
    if app:
        logger.info("Bot Telegram démarré (Polling)...")
        app.run_polling()
