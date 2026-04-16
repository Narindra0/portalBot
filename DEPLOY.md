# 🚀 Guide de Déploiement : GitHub Actions + Turso

Ce guide explique comment faire tourner ton scraper gratuitement 24h/24 sans laisser ton PC allumé.

## 1. Créer une base de données Turso (Persistence)

Comme GitHub Actions réinitialise les fichiers à chaque run, ton fichier `telegram_cache.db` sera perdu. Pour garder l'historique des offres et tes configurations :

1. Crée un compte sur [Turso.tech](https://turso.tech) (Gratuit).
2. Installe la CLI Turso ou utilise le dashboard web pour créer une database nommée `portal-db`.
3. Récupère ton **URL** (`libsql://...`) et ton **Auth Token**.

## 2. Configurer GitHub Secrets

1. Upload ton code sur un repo GitHub (Privé de préférence).
2. Va dans **Settings** → **Secrets and variables** → **Actions**.
3. Ajoute les **Repository secrets** suivants :

| Secret | Description |
|--------|-------------|
| `TELEGRAM_TOKEN` | Ton token d'API Bot (@BotFather) |
| `TELEGRAM_CHAT_ID` | Ton ID Chat (@userinfobot) |
| `HF_API_KEY` | Ta clé d'API Hugging Face |
| `TURSO_DATABASE_URL` | L'URL obtenue à l'étape 1 |
| `TURSO_AUTH_TOKEN` | Le token obtenu à l'étape 1 |

## 3. Utilisation

### Le Scraper (GitHub Actions)
- Le scraper tourne automatiquement **toutes les 2 heures**.
- Tu peux le lancer manuellement dans l'onglet **Actions** → **PortalJob Scraper** → **Run workflow**.

### Le Bot (Local ou VPS)
Le bot (qui gère les boutons et les CV) doit rester "allumé" en permanence. 
- Tu peux continuer à le lancer sur ton PC via `python -m src.main bot`.
- Il partagera la même base de données que le scraper grâce à Turso !

## 🛠️ Commandes Locales Utiles

- `python -m src.main scraper` : Lance un scan immédiat (une seule fois).
- `python -m src.main bot` : Lance uniquement le gestionnaire Telegram.
- `python -m src.main all` : Lance tout (scraper planifié + bot).
