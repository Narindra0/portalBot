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

from ..config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, CV_PDF_PATH
from ..storage.cache_db import (
    recuperer_offre_async, sauvegarder_cv_async, 
    recuperer_cv_async, vider_cache,
    lister_offres_permanentes_async, compter_offres_async,
    ajouter_offre_async
)
from ..storage.pdf_extractor import traiter_fichier_cv
from ..llm.generator import creer_lettre_motivation, formater_lettre_pour_telegram
from .bot import formater_details_complets
from ..utils.logger import logger
from ..utils.intel import CompanyIntel
from ..automation.apply import postuler_offre_portal
from ..automation.mailer import envoyer_candidature_email, extraire_email_depuis_texte
import html as html_module

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
        "/job - Voir les dernières offres en base\n"
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
        "/job : Lister les offres enregistrées\n"
        "/configurer_cv : Créer ou modifier ton profil\n"
        "/voir_cv : Afficher tes infos enregistrées\n"
        "/supprimer_cv : Effacer tes données"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)

async def afficher_liste_jobs(update, context, offset=0, edit=False):
    chat_id = update.effective_chat.id
    limit = 5
    offres = await lister_offres_permanentes_async(limit=limit, offset=offset)
    total = await compter_offres_async()

    if not offres:
        msg_text = "📭 Aucune offre trouvée dans la base."
        if edit:
            await update.callback_query.edit_message_text(text=msg_text)
        else:
            await context.bot.send_message(chat_id=chat_id, text=msg_text)
        return

    msg = f"📋 <b>Offres d'emploi ({offset + 1} à {min(offset + limit, total)} sur {total})</b>\n\n"
    
    keyboard = []
    for i, offre in enumerate(offres):
        cache_key = await ajouter_offre_async(offre)
        msg += f"{i+1}. <b>{html_module.escape(offre['titre'])}</b>\n"
        msg += f"🏢 <i>{html_module.escape(offre['entreprise'])}</i>\n\n"
        keyboard.append([InlineKeyboardButton(f"📄 Voir : {html_module.escape(offre['titre'][:30])}", callback_data=cache_key)])

    nav_buttons = []
    if offset > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Précédent", callback_data=f"jobspage_{max(0, offset - limit)}"))
    if offset + limit < total:
        nav_buttons.append(InlineKeyboardButton("Suivant ➡️", callback_data=f"jobspage_{offset + limit}"))
        
    if nav_buttons:
        keyboard.append(nav_buttons)

    reply_markup = InlineKeyboardMarkup(keyboard)

    if edit:
        await update.callback_query.edit_message_text(
            text=msg,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text=msg,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )

async def job_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commande /job pour afficher la liste des offres."""
    await afficher_liste_jobs(update, context, offset=0, edit=False)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gère tous les clics de boutons."""
    query = update.callback_query
    data = query.data
    await query.answer()

    if data.startswith("jobspage_"):
        offset = int(data.split("_")[1])
        await afficher_liste_jobs(update, context, offset=offset, edit=True)
        return

    if data.startswith("offre_"):
        # Afficher les détails complets
        offre = await recuperer_offre_async(data)
        if not offre:
            await query.edit_message_text("❌ Détails non disponibles ou expirés.")
            return

        text = formater_details_complets(offre)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📝 Créer Lettre de Motivation", callback_data=f"lm_{data}")],
            [InlineKeyboardButton("🔍 Profil Société", callback_data=f"intel_{data}")],
            [InlineKeyboardButton("🤖 Postuler via AI", callback_data=f"apply_{data}")]
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
         
         if intel.get('summary'):
             summary_safe = html_module.escape(intel['summary'])
             res += f"✨ <b>Résumé IA</b> :\n<i>{summary_safe}</i>\n\n"
             
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

    elif data.startswith("apply_"):
        # Auto-candidature avec IA
        cache_key = data[6:]
        offre = await recuperer_offre_async(cache_key)
        
        if not offre:
            await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text="❌ Offre expirée dans le cache.")
            return
            
        cv = await recuperer_cv_async()
        if not cv:
            await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text="⚠️ Tu n'as pas encore configuré ton CV. Utilise /configurer_cv.")
            return
            
        url_offre = offre.get('url')
        if not url_offre or "portaljob-madagascar.com" not in url_offre:
            await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text="❌ L'auto-apply n'est actuellement supporté que sur PortalJob.")
            return

        status_msg = await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text="🤖 Génération de la lettre de motivation sur mesure...")
        
        # 1. Génération LM
        success_lm, result_lm = await creer_lettre_motivation(offre)
        if not success_lm:
            await status_msg.edit_text(f"❌ Erreur lors de la génération de la lettre :\n{result_lm}")
            return
            
        # Optional: Sending LM as proof
        parties = formater_lettre_pour_telegram(result_lm)
        for p in parties:
            await context.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=p)
            
        await status_msg.edit_text("⏳ Lancement du navigateur pour soumettre la candidature...")
        
        # 2. Lancement Playwright en background (ça peut prendre 5-15 secondes)
        success_apply, msg_apply = await postuler_offre_portal(url_offre, result_lm)
        
        if success_apply:
            await context.bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=f"✅ <b>SUCCÈS :</b>\n{msg_apply}",
                parse_mode=ParseMode.HTML
            )
        else:
            # Playwright a échoué — Tentative de fallback par email
            details_offre = offre.get('details', '')
            email_recruteur = extraire_email_depuis_texte(details_offre)
            
            raison_echec = html_module.escape(str(msg_apply))
            
            if email_recruteur:
                await context.bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID,
                    text=f"⚠️ <b>Plateforme inaccessible.</b>\nEmail détecté : <code>{email_recruteur}</code>\n⏳ Envoi direct en cours...",
                    parse_mode=ParseMode.HTML
                )
                # Utiliser le PDF s’il existe, sinon None
                import os
                pdf_path = CV_PDF_PATH if os.path.exists(CV_PDF_PATH) else None
                success_mail, msg_mail = await envoyer_candidature_email(
                    destinataire=email_recruteur,
                    offre_titre=offre.get('titre', 'Poste'),
                    offre_entreprise=offre.get('entreprise', 'Entreprise'),
                    lettre_motivation=result_lm,
                    cv_pdf_path=pdf_path
                )
                if success_mail:
                    await context.bot.send_message(
                        chat_id=TELEGRAM_CHAT_ID,
                        text=f"✅ <b>Email envoyé !</b>\n{html_module.escape(msg_mail)}",
                        parse_mode=ParseMode.HTML
                    )
                else:
                    await context.bot.send_message(
                        chat_id=TELEGRAM_CHAT_ID,
                        text=f"❌ <b>Échec de l'email :</b>\n{html_module.escape(msg_mail)}\n\n<i>Raison Playwright : {raison_echec}</i>",
                        parse_mode=ParseMode.HTML
                    )
            else:
                await context.bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID,
                    text=f"❌ <b>ÉCHEC (aucun email de secours trouvé) :</b>\n{raison_echec}",
                    parse_mode=ParseMode.HTML
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

    if intel.get('summary'):
        summary_safe = html_module.escape(intel['summary'])
        res += f"✨ <b>Résumé IA</b> :\n<i>{summary_safe}</i>\n\n"

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
    
    file_id = context.user_data['file_id']
    mime_type = context.user_data['mime_type']
    
    # Extraction du texte
    success, result = await traiter_fichier_cv(file_id, TELEGRAM_TOKEN, mime_type)
    
    await status_msg.delete()
    
    if success:
        await sauvegarder_cv_async(
            context.user_data['nom'], 
            context.user_data['email'], 
            context.user_data['phone'], 
            portfolio,
            result
        )
        
        # Sauvegarde du PDF brut sur disque pour les emails de fallback
        if 'pdf' in mime_type.lower():
            try:
                bot_file = await update.get_bot().get_file(file_id)
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(bot_file.file_path) as resp:
                        pdf_bytes = await resp.read()
                import os
                with open(CV_PDF_PATH, 'wb') as f:
                    f.write(pdf_bytes)
                await update.message.reply_text(f"✅ <b>CV enregistré + PDF sauvegardé !</b>\nExtrait : <code>{result[:100]}...</code>", parse_mode=ParseMode.HTML)
            except Exception as e:
                logger.warning(f"PDF non sauvegardé sur disque : {e}")
                await update.message.reply_text(f"✅ <b>CV enregistré !</b>\nExtrait : <code>{result[:100]}...</code>", parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(f"✅ <b>CV enregistré !</b>\nExtrait : <code>{result[:100]}...</code>", parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(f"❌ Erreur extraction : {result}")
        
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Annulé.")
    return ConversationHandler.END

# --- INITIALISATION ---

async def post_init(application: Application):
    from telegram import BotCommand
    commands = [
        BotCommand("start", "Démarrer le bot"),
        BotCommand("job", "Lister toutes les offres d'emploi"),
        BotCommand("configurer_cv", "Configurer ton profil pour les lettres"),
        BotCommand("voir_cv", "Voir ton profil actuel"),
        BotCommand("search", "Rechercher des infos sur une entreprise"),
        BotCommand("aide", "Afficher l'aide")
    ]
    await application.bot.set_my_commands(commands)

def setup_application():
    """Configure l'application Telegram."""
    if not TELEGRAM_TOKEN:
        return None
        
    app = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    
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
    app.add_handler(CommandHandler("job", job_cmd))
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
