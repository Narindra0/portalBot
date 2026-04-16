# 🤖 PortalJob Scraper

Scraper automatisé pour PortalJob Madagascar avec notifications Telegram et génération de lettres de motivation via IA.

## ✨ Fonctionnalités

- 🔍 **Scraping automatique** des offres d'emploi du secteur Informatique/Web
- 📱 **Notifications Telegram** avec cards interactives
- 🤖 **Génération de lettres de motivation** personnalisées via Hugging Face
- 📄 **Extraction de CV** depuis PDF ou photos (OCR)
- 💾 **Cache SQLite** pour éviter les doublons
- 🔄 **Workflow complet** : Offre → Détails → Lettre de motivation

## 📁 Structure du projet

```
portal-job-scraper/
├── config/
│   └── .env                    # Configuration (token, clés API)
├── data/                       # Dossier données (optionnel)
├── src/                        # Code source
│   ├── __init__.py
│   ├── main.py                 # Point d'entrée principal
│   ├── scraper/
│   │   └── portal.py           # Scraper PortalJob
│   ├── telegram/
│   │   ├── __init__.py
│   │   ├── bot.py              # Envoi Telegram
│   │   └── callback_handler.py # Gestion des boutons
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── generator.py        # Génération lettres
│   │   └── huggingface_api.py  # API Hugging Face
│   └── storage/
│       ├── __init__.py
│       ├── cache_db.py         # Base SQLite (offres + CV)
│       └── pdf_extractor.py    # Extraction PDF/OCR
├── session/                    # Session Playwright
├── .env.example                # Template configuration
├── requirements.txt            # Dépendances Python
├── start.bat / start.ps1       # Lanceurs Windows
└── README.md
```

## 🚀 Démarrage rapide

### 1. Installation des dépendances

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Configuration

Copie le fichier d'exemple et remplace les valeurs :

```bash
copy .env.example config\.env
```

Modifie `config\.env` avec tes clés :

```env
TELEGRAM_TOKEN=ton_token_bot
TELEGRAM_CHAT_ID=ton_chat_id
HF_API_KEY=ta_cle_huggingface
```

**Obtenir les clés :**
- **Telegram Token** : @BotFather sur Telegram → `/newbot`
- **Chat ID** : Envoie un message à @userinfobot
- **HF API Key** : https://huggingface.co/settings/tokens (gratuit)

### 3. Lancement

#### Mode scraper (recherche d'offres)
```bash
python -m src.main scraper
```

#### Mode Telegram (gestion des callbacks)
```bash
python -m src.main telegram
```

#### Mode complet (les deux en parallèle)
```bash
python -m src.main all
```

## 📱 Utilisation Telegram

### Commandes disponibles

- `/configurer_cv` - Configurer ton CV (texte ou fichier PDF/photo)
- `/voir_cv` - Voir ton CV actuel
- `/supprimer_cv` - Supprimer ton CV
- `/aide` - Afficher l'aide

### Workflow

1. **Le scraper détecte une nouvelle offre** → Card envoyée sur Telegram
   ```
   💼 DEVELOPPEUR PYTHON
   🏢 Tech Solutions  •  📅 15/04/2026
   
   📋 Django | API REST
   👤 3 ans d'expérience Python
   
   [📄 Voir plus] [🔗 Postuler]
   ```

2. **Cliquer "Voir plus"** → Détails complets de l'offre
   ```
   📌 DEVELOPPEUR PYTHON
   🏢 Tech Solutions
   
   💼 ACTIVITÉ ENTREPRISE
   ▫️ Startup innovante dans le fintech...
   
   📋 MISSIONS
   ▫️ Développement backend Python
   ▫️ Conception API REST
   
   👤 PROFIL RECHERCHÉ
   ▫️ Maîtrise de Django
   ▫️ 3+ ans d'expérience
   
   [📝 Créer Lettre de Motivation]
   ```

3. **Cliquer "Créer Lettre de Motivation"** → Lettre générée par IA
   - Analyse automatique de ton CV
   - Lettre personnalisée pour l'offre
   - Envoi en plusieurs messages si longue

## 🔧 Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Telegram Bot  │◄────│  Portal Scraper  │────►│  SQLite Cache   │
│   (UI/Boutons)  │     │  (scraper/)      │     │ (storage/)      │
└─────────────────┘     └──────────────────┘     └─────────────────┘
         │                                               │
         │  Clique "Créer LM"                            │
         ▼                                               ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│Callback Handler │────►│  LM Generator    │────►│  CV Storage     │
│  (telegram/)    │     │  (llm/)          │     │  (storage/)     │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                 │
                                 ▼
                        ┌──────────────────┐
                        │ HuggingFace API  │
                        │ Qwen 2.5 7B      │
                        └──────────────────┘
```

## 🛠️ Technologies utilisées

- **Scraping** : Playwright (Chromium)
- **Telegram** : Bot API (requests)
- **LLM** : Hugging Face Inference API (Qwen 2.5)
- **OCR** : Tesseract + PyPDF2
- **Stockage** : SQLite
- **Langage** : Python 3.10+

## ⚠️ Dépannage

| Problème | Solution |
|----------|----------|
| "CV non configuré" | Utilise `/configurer_cv` sur Telegram |
| "HF_API_KEY manquante" | Vérifie `config\.env` |
| "Détails non disponibles" | Relance le scraper pour rafraîchir |
| Bouton ne répond pas | Vérifie que le callback handler tourne |
| OCR ne fonctionne pas | Installe Tesseract-OCR sur Windows |

## 📄 Installation Tesseract OCR (Windows)

Pour l'extraction de texte depuis les images/PDF scannés :

1. Télécharge : https://github.com/UB-Mannheim/tesseract/wiki
2. Installe dans `C:\Program Files\Tesseract-OCR`
3. Le scraper détecte automatiquement l'installation

## � Déploiement Gratuit en Ligne

Le scraper peut tourner gratuitement 24/7 sans ton PC !

### Option recommandée : GitHub Actions (100% gratuit)

1. Upload le code sur GitHub
2. Configure 5 secrets dans Settings → Secrets:
   - `TELEGRAM_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `HF_API_KEY`
   - `TURSO_DATABASE_URL` (optionnel, voir [Turso](#-base-de-données-turso))
   - `TURSO_AUTH_TOKEN` (optionnel)
3. Le scraper tourne automatiquement toutes les 2 heures

Les workflows sont déjà configurés dans `.github/workflows/`.

**Autres options gratuites :**
- **PythonAnywhere** : Hébergement Python simple
- **Railway.app** : $5/mois de crédits (suffisant)
- **Oracle Cloud** : 2 VMs gratuites à vie
- **Render.com** : Alternative à Railway

👉 Voir [DEPLOY.md](DEPLOY.md) pour le guide complet !

## �📝 Notes

- **Stockage**: SQLite local par défaut, ou **Turso** (SQLite cloud) si configuré
- Le scraper vérifie toutes les 30 minutes (mode continu)
- Le cache temporaire pour Telegram expire après 24h (20 offres max)

## 🗄️ Base de données (Turso - Optionnel)

Pour une base persistante sur GitHub Actions, configure **Turso** (SQLite serverless gratuit) :

```bash
# 1. Installer Turso CLI
curl -sSfL https://get.tur.so/install.sh | bash

# 2. Créer une base
turso db create portaljob-scraper
turso db show portaljob-scraper  # Copie l'URL

# 3. Créer un token
turso db tokens create portaljob-scraper  # Copie le token
```

Ajoute les variables dans GitHub Secrets :
- `TURSO_DATABASE_URL` → `libsql://portaljob-USERNAME.turso.io`
- `TURSO_AUTH_TOKEN` → `eyJhbGciOiJF...`

**Sans Turso** : utilise SQLite local (fonctionne aussi sur GitHub Actions mais les données disparaissent entre les runs).
- Les offres non-développement sont filtrées automatiquement
- Pour exporter en JSON: utilise la fonction `exporter_vers_json()` du module storage

## 🔄 Mise à jour depuis l'ancienne version

Si tu viens de l'ancienne structure (fichiers à la racine) :

1. Déplace ton `.env` vers `config\.env`
2. Migre tes offres JSON vers SQLite :
   ```bash
   python migrate_to_sqlite.py
   ```
3. Supprime les anciens fichiers : `gemini_api.py`, `openrouter_api.py`, `ollama_api.py`, `cache_manager.py`, `setup_cv.py`
4. Utilise les nouvelles commandes : `python -m src.main ...`

**Note:** Le stockage JSON est remplacé par SQLite. Toutes les offres sont maintenant dans `telegram_cache.db`.

## 💡 Astuces

- Configure ton CV via Telegram avec `/configurer_cv`
- Tu peux envoyer un PDF ou une photo de ton CV
- Le mode `all` lance tout automatiquement

---

**Projet personnel** - Développé pour automatiser la recherche d'emploi tech à Madagascar 🇲🇬
