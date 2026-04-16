#!/usr/bin/env python3
"""
PortalJob Scraper - Point d'entrée principal (Async)
"""
import asyncio
import sys
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .scraper.portal import surveiller_portal
from .telegram.callback_handler import setup_application
from .storage.cache_db import init_db_async
from .utils.logger import logger

async def run_scraper_task(bot):
    """Encapsulation de la tâche scraper pour le scheduler."""
    try:
        await surveiller_portal(telegram_bot=bot)
    except Exception as e:
        logger.error(f"Erreur durant la tâche planifiée : {e}")

async def main():
    """Point d'entrée principal asynchrone."""
    # Analyse des arguments
    mode = "all"
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()

    logger.info(f"🚀 Initialisation du système (Mode: {mode})...")
    
    # 1. Initialisation Base de données
    await init_db_async()
    
    # 2. Configuration du Bot
    app = setup_application()
    if not app:
        logger.error("❌ Impossible de configurer le bot Telegram. Vérifie config/.env")
        return

    # Initialiser l'application bot
    await app.initialize()
    
    # --- Mode SCRAPER (exécution unique) ---
    if mode == "scraper":
        logger.info("🔍 Lancement du scan ponctuel...")
        try:
            await surveiller_portal(telegram_bot=app.bot)
            logger.info("✅ Scan terminé avec succès.")
        except Exception as e:
            logger.error(f"❌ Erreur durant le scan : {e}")
        finally:
            await app.shutdown()
        return

    # --- Modes permanents (BOT ou ALL) ---
    await app.start()
    
    scheduler = None
    if mode in ["all", "combined"]:
        # 3. Configuration du Scheduler (Toutes les 2 heures de 08h à 18h)
        scheduler = AsyncIOScheduler()
        scheduler.add_job(run_scraper_task, 'cron', hour='8,10,12,14,16,18', minute=0, args=[app.bot])
        scheduler.start()
        logger.info("📅 Scheduler démarré (08h00 - 18h00, toutes les 2h)")
        
        # Lancement d'un scan immédiat
        asyncio.create_task(run_scraper_task(app.bot))

    # Lancement du Bot en mode polling
    logger.info("🤖 Bot en ligne et prêt !")
    try:
        # On utilise l'updater pour le polling
        await app.updater.start_polling(drop_pending_updates=True)
        
        # Garder le programme en vie
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        logger.info("👋 Arrêt du système...")
    except Exception as e:
        if "Conflict" in str(e):
             logger.error("❌ Conflit détecté : Vérifie qu'aucune autre instance du bot ne tourne !")
        else:
             logger.error(f"❌ Erreur inattendue : {e}")
    finally:
        # Arrêt propre
        logger.info("⏳ Fermeture des services...")
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        if scheduler:
            scheduler.shutdown()
        
        pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        if pending:
            await asyncio.wait(pending, timeout=5.0)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
