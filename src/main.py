#!/usr/bin/env python3
"""
PortalJob Scraper - Point d'entrée principal

Ce script coordonne le scraping des offres d'emploi sur PortalJob Madagascar
et leur envoi sur Telegram avec possibilité de générer des lettres de motivation.

Usage:
    python -m src.main scraper    # Lance le scraper
    python -m src.main telegram   # Lance le gestionnaire de callbacks Telegram
    python -m src.main all      # Lance les deux (par défaut)

Structure du projet:
    src/
    ├── scraper/        # Module de scraping PortalJob
    ├── telegram/       # Module Telegram (bot + callback handler)
    ├── llm/            # Génération de lettres de motivation
    ├── storage/        # Cache SQLite et extraction PDF
    ├── main.py         # Point d'entrée
    config/
    ├── .env            # Configuration (token, clés API)
    data/
    └── offres_emplois.json  # Base de données des offres
"""
import sys
import threading
import time
from .scraper import surveiller_portal
from .telegram import poll_callbacks


def run_scraper():
    """Exécute le scraper en boucle."""
    print("🔄 Scraper en mode continu (toutes les 30 minutes)")
    while True:
        try:
            surveiller_portal()
        except Exception as e:
            print(f"❌ Erreur scraper: {e}")
        print("\n⏳ Attente 30 minutes avant la prochaine vérification...")
        time.sleep(1800)  # 30 minutes


def run_telegram():
    """Exécute le gestionnaire de callbacks Telegram."""
    print("🤖 Démarrage du gestionnaire Telegram...")
    poll_callbacks()


def main():
    """Point d'entrée principal."""
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
    else:
        command = "scraper"  # Par défaut: lancer le scraper seul

    if command == "scraper":
        run_scraper()
    elif command == "telegram":
        run_telegram()
    elif command == "all":
        # Lancer les deux en parallèle
        print("🚀 Démarrage complet (scraper + telegram)...")
        scraper_thread = threading.Thread(target=run_scraper, daemon=True)
        telegram_thread = threading.Thread(target=run_telegram, daemon=True)
        
        scraper_thread.start()
        telegram_thread.start()
        
        # Garder le main thread vivant
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n👋 Arrêt demandé")
    else:
        print(f"❌ Commande inconnue: {command}")
        print("Usage: python -m src.main [scraper|telegram|all]")
        sys.exit(1)


if __name__ == "__main__":
    main()
