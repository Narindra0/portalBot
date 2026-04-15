# 🚀 Déploiement - Options Gratuites

Guide pour déployer le PortalJob Scraper gratuitement en ligne.

---

## Option 1: GitHub Actions (RECOMMANDÉ) ⭐

**Gratuit**, fiable, pas de serveur à gérer. Parfait pour un scraper.

### 1. Créer un repo GitHub

```bash
git init
git add .
git commit -m "Initial commit"
gh repo create portaljob-scraper --public --source=. --push
```

Ou utilise GitHub Desktop / l'interface web.

### 2. Configurer les Secrets

Dans ton repo GitHub → Settings → Secrets and variables → Actions:

| Secret | Valeur |
|--------|--------|
| `TELEGRAM_TOKEN` | Ton token Telegram |
| `TELEGRAM_CHAT_ID` | Ton chat ID |
| `HF_API_KEY` | Ta clé Hugging Face |

### 3. C'est tout ! 🎉

Les workflows sont déjà configurés dans `.github/workflows/`:

- **scraper.yml** : S'exécute toutes les 2 heures
- **telegram-bot.yml** : Gestion des callbacks (redémarrage toutes les 6h)

Tu peux aussi lancer manuellement depuis l'onglet "Actions" → "Run workflow".

---

## Option 2: PythonAnywhere

**Gratuit** (1 worker, limite de requêtes). Bon pour exécution persistante.

### 1. Créer un compte
- Va sur https://www.pythonanywhere.com/
- Crée un compte gratuit (Beginner Account)

### 2. Uploader le code

**Option A: Via Git**
```bash
cd ~
git clone https://github.com/TON-USER/portaljob-scraper.git
cd portaljob-scraper
```

**Option B: Via fichier ZIP**
- Compresse ton dossier local en ZIP
- Upload via l'interface Files → Upload a file
- Extrait avec : `unzip portaljob-scraper.zip`

### 3. Créer l'environnement virtuel

```bash
cd ~/portaljob-scraper
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### 4. Configurer les variables d'environnement

Dans Dashboard → Web (ou Console), clique sur "Environment variables" et ajoute :

```
TELEGRAM_TOKEN=ton_token
TELEGRAM_CHAT_ID=ton_chat_id
HF_API_KEY=ta_cle_hf
HEADLESS=true
```

### 5. Créer une tâche planifiée (Scheduled Task)

Dashboard → Tasks → Schedule a new task:

**Pour le scraper (toutes les 2h):**
```bash
cd /home/TON-USER/portaljob-scraper && source venv/bin/activate && python -c "from src.scraper import surveiller_portal; surveiller_portal()"
```

Régle la fréquence : `0 */2 * * *` (toutes les 2 heures)

**Pour le bot Telegram (constamment actif):**
Malheureusement, le compte gratuit ne permet qu'**une seule tâche persistante**.

---

## Option 3: Railway.app

**Gratuit** ($5/mois de crédits, suffisant pour ce projet).

### 1. Créer un compte
- Va sur https://railway.app/
- Connecte avec GitHub

### 2. Déployer depuis GitHub

- New Project → Deploy from GitHub repo
- Sélectionne ton repo
- Railway détecte automatiquement Python

### 3. Configurer les variables

Dans Variables, ajoute :

```
TELEGRAM_TOKEN=ton_token
TELEGRAM_CHAT_ID=ton_chat_id
HF_API_KEY=ta_cle_hf
HEADLESS=true
```

### 4. Créer un cron job

Ajoute un fichier `railway.json` à la racine:

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "cron": "0 */2 * * *",
    "startCommand": "python -c 'from src.scraper import surveiller_portal; surveiller_portal()'"
  }
}
```

---

## Option 4: Render.com

**Gratuit** (plan Starter suffisant).

Similaire à Railway :
- Connecte ton repo GitHub
- Déploie comme "Background Worker"
- Configure les env vars
- Active le cron job

---

## Option 5: Oracle Cloud (VM Gratuite)

**Toujours gratuit** (2 VMs gratuites à vie).

Parfait si tu veux un serveur persistant sans limites.

### 1. Créer un compte
- https://www.oracle.com/cloud/free/
- Valide ta carte (pas de débit)

### 2. Créer une VM
- Compute → Instances → Create Instance
- Choisir "VM.Standard.E2.1.Micro" (gratuit)
- Image : Ubuntu 22.04
- Télécharger la clé SSH

### 3. Se connecter et installer

```bash
ssh -i ma-cle-ssh ubuntu@IP-DE-TA-VM

# Installer Python et dépendances
sudo apt update
sudo apt install python3-pip python3-venv -y

# Cloner le repo
git clone https://github.com/TON-USER/portaljob-scraper.git
cd portaljob-scraper

# Environnement virtuel
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# Variables d'environnement
export TELEGRAM_TOKEN=ton_token
export TELEGRAM_CHAT_ID=ton_chat_id
export HF_API_KEY=ta_cle_hf
export HEADLESS=true

# Test
python -c "from src.scraper import surveiller_portal; surveiller_portal()"
```

### 4. Automatiser avec cron

```bash
# Éditer crontab
crontab -e

# Ajouter (toutes les 2 heures):
0 */2 * * * cd /home/ubuntu/portaljob-scraper && source venv/bin/activate && python -c "from src.scraper import surveiller_portal; surveiller_portal()"

# Pour le bot Telegram en continu, utilise systemd ou screen:
screen -S telegram
source venv/bin/activate && python -c "from src.telegram import poll_callbacks; poll_callbacks()"
# Ctrl+A puis D pour détacher
```

---

## Comparaison des options

| Option | Prix | Fiabilité | Facilité | Durée max |
|--------|------|-----------|----------|-----------|
| **GitHub Actions** | Gratuit | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 6h/run |
| **PythonAnywhere** | Gratuit | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 24h/jour |
| **Railway** | $5/mois | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Illimité |
| **Render** | Gratuit | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | Illimité |
| **Oracle Cloud** | Gratuit | ⭐⭐⭐⭐⭐ | ⭐⭐ | Illimité |

---

## 🎯 Recommandation

Pour débuter : **GitHub Actions** (vraiment gratuit, pas de carte bancaire)

Pour production : **Railway** ou **Oracle Cloud** (plus stable)

---

## 📁 Fichiers créés pour le déploiement

```
.github/
├── workflows/
│   ├── scraper.yml       # Workflow scraper (cron)
│   └── telegram-bot.yml  # Workflow callbacks
DEPLOY.md                 # Ce fichier
```

---

## ⚠️ Notes importantes

1. **Playwright sur le cloud** : Fonctionne en mode headless automatiquement
2. **SQLite** : Sur GitHub Actions, la base est persistée via cache
3. **Telegram** : Le callback handler doit tourner en continu pour les boutons
4. **Variables sensibles** : Jamais dans le code, toujours dans les secrets !

---

## 🆘 Dépannage

### "Executable doesn't exist" (Playwright)
```bash
playwright install chromium
```

### "No module named 'src'"
```bash
# Ajouter au PYTHONPATH
export PYTHONPATH=/chemin/vers/portaljob-scraper:$PYTHONPATH
```

### Timeouts sur GitHub Actions
- Normal pour les gros sites
- Augmente le timeout dans le workflow si nécessaire

---

Bonne chance ! 🚀
