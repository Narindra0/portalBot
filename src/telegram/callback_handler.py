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
            [InlineKeyboardButton("📝 Créer Lettre de Motivation", callback_data=f"lm_{data}")]
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
            header = f"✉️ <b>LETTRE DE MOTIVATION</b>\n📌 {offre['titre']}\n🏢 {offre['entreprise']}\n\n<code>{'═'*30}</code>"
            await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=header, parse_mode=ParseMode.HTML)
            
            for p in parties:
                await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=p)
                
            footer = f"<code>{'═'*30}</code>\n✅ <b>Lettre prête !</b>"
            await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=footer, parse_mode=ParseMode.HTML)
        else:
            await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f"❌ Erreur génération: {result}")

# --- CONFIGURATION CV (CONVERSATION) ---

async def config_cv_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📝 <b>Configuration du CV</b>\n\n"
        "Comment souhaites-tu fournir tes informations ?\n\n"
        "📄 <b>Option 1</b> : Envoie un PDF ou une Photo (OCR)\n"
        "✏️ <b>Option 2</b> : Tape 'texte' pour saisir manuellement"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
    return CHOOSING

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
    app.add_handler(cv_handler)
    app.add_handler(CallbackQueryHandler(handle_callback))
    
    return app

def run_bot():
    """Lance le bot en mode polling (pour usage indépendant)."""
    app = setup_application()
    if app:
        logger.info("Bot Telegram démarré (Polling)...")
        app.run_polling()
