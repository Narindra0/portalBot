"""
Gestionnaire de cache avec support Turso (SQLite cloud) + fallback SQLite local.
Turso est utilisé en priorité si les variables d'environnement sont présentes.
"""
import sqlite3
import json
import time
import os
from datetime import datetime, timedelta

# Configuration Turso (cloud)
TURSO_DATABASE_URL = os.getenv('TURSO_DATABASE_URL')
TURSO_AUTH_TOKEN = os.getenv('TURSO_AUTH_TOKEN')
USE_TURSO = TURSO_DATABASE_URL and TURSO_AUTH_TOKEN

# Fallback SQLite local
DB_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "telegram_cache.db")
MAX_AGE_HOURS = 24

# Client Turso (initialisé à la première utilisation)
_turso_conn = None

def _get_turso_conn():
    """Retourne la connexion Turso (crée si nécessaire)."""
    global _turso_conn
    if _turso_conn is None:
        try:
            import libsql_experimental as libsql
            _turso_conn = libsql.connect(
                database=TURSO_DATABASE_URL.replace('libsql://', 'https://'),
                auth_token=TURSO_AUTH_TOKEN
            )
            print("☁️  Connecté à Turso (SQLite cloud)")
        except Exception as e:
            print(f"⚠️ Erreur connexion Turso: {e}")
            raise
    return _turso_conn


def _get_conn():
    """Retourne la connexion appropriée (Turso ou SQLite local)."""
    if USE_TURSO:
        return _get_turso_conn()
    else:
        return sqlite3.connect(DB_FILE)

def init_db():
    conn = _get_conn()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS offres (
            cache_key TEXT PRIMARY KEY,
            titre TEXT,
            entreprise TEXT,
            date_publication TEXT,
            url TEXT,
            details TEXT,
            timestamp REAL,
            date_decouverte TEXT
        )
    ''')

    conn.commit()
    if not USE_TURSO:
        conn.close()


def ajouter_offre(offre_data):
    init_db()

    url = offre_data.get('url', '')
    cache_key = f"offre_{hash(url) & 0x7FFFFFFF}"

    conn = _get_conn()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT OR REPLACE INTO offres
        (cache_key, titre, entreprise, date_publication, url, details, timestamp, date_decouverte)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        cache_key,
        offre_data.get('titre', ''),
        offre_data.get('entreprise', ''),
        offre_data.get('date_publication', ''),
        url,
        offre_data.get('details', ''),
        time.time(),
        offre_data.get('date_decouverte', '')
    ))

    conn.commit()
    if not USE_TURSO:
        conn.close()

    # Nettoyer les vieilles entrées
    nettoyer_vieilles_offres()

    return cache_key


def recuperer_offre(cache_key):
    """Récupère une offre par sa clé."""
    if not USE_TURSO and not os.path.exists(DB_FILE):
        return None

    conn = _get_conn()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT titre, entreprise, date_publication, url, details, timestamp
        FROM offres WHERE cache_key = ?
    ''', (cache_key,))

    row = cursor.fetchone()
    if not USE_TURSO:
        conn.close()

    if row is None:
        return None

    titre, entreprise, date_publication, url, details, timestamp = row

    # Vérifier l'âge
    age_hours = (time.time() - timestamp) / 3600
    if age_hours > MAX_AGE_HOURS:
        return None

    return {
        'titre': titre,
        'entreprise': entreprise,
        'date_publication': date_publication,
        'url': url,
        'details': details
    }


def nettoyer_vieilles_offres():
    """Supprime les offres trop vieilles."""
    if not USE_TURSO and not os.path.exists(DB_FILE):
        return

    cutoff_time = time.time() - (MAX_AGE_HOURS * 3600)

    conn = _get_conn()
    cursor = conn.cursor()

    cursor.execute('DELETE FROM offres WHERE timestamp < ?', (cutoff_time,))

    # Garder seulement les 20 plus récentes
    cursor.execute('''
        DELETE FROM offres
        WHERE cache_key NOT IN (
            SELECT cache_key FROM offres
            ORDER BY timestamp DESC
            LIMIT 20
        )
    ''')

    conn.commit()
    if not USE_TURSO:
        conn.close()


def vider_cache():
    """Vide complètement la base."""
    if USE_TURSO:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM offres')
        cursor.execute('DELETE FROM offres_permanentes')
        cursor.execute('DELETE FROM cv_utilisateur')
        conn.commit()
    elif os.path.exists(DB_FILE):
        os.remove(DB_FILE)


# ========== GESTION DU CV UTILISATEUR ==========

def init_cv_table():
    """Initialise la table pour le CV utilisateur."""
    conn = _get_conn()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cv_utilisateur (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            nom TEXT,
            email TEXT,
            telephone TEXT,
            cv_text TEXT NOT NULL,
            date_mise_a_jour TEXT
        )
    ''')

    conn.commit()
    if not USE_TURSO:
        conn.close()


def sauvegarder_cv(nom, email, telephone, cv_text):
    """Sauvegarde ou met à jour le CV utilisateur."""
    init_cv_table()

    conn = _get_conn()
    cursor = conn.cursor()

    date_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute('''
        INSERT OR REPLACE INTO cv_utilisateur
        (id, nom, email, telephone, cv_text, date_mise_a_jour)
        VALUES (1, ?, ?, ?, ?, ?)
    ''', (nom, email, telephone, cv_text, date_now))

    conn.commit()
    if not USE_TURSO:
        conn.close()
    print(f"✅ CV sauvegardé pour {nom}")


def recuperer_cv():
    """Récupère le CV utilisateur."""
    if not USE_TURSO and not os.path.exists(DB_FILE):
        return None

    init_cv_table()

    conn = _get_conn()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT nom, email, telephone, cv_text, date_mise_a_jour
        FROM cv_utilisateur WHERE id = 1
    ''')

    row = cursor.fetchone()
    if not USE_TURSO:
        conn.close()

    if row is None:
        return None

    return {
        'nom': row[0],
        'email': row[1],
        'telephone': row[2],
        'cv_text': row[3],
        'date_mise_a_jour': row[4]
    }


def cv_existe():
    """Vérifie si un CV est déjà configuré."""
    return recuperer_cv() is not None


# ========== STOCKAGE PERMANENT DES OFFRES (remplace JSON) ==========

def init_offres_permanentes_table():
    """Initialise la table pour le stockage permanent des offres."""
    conn = _get_conn()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS offres_permanentes (
            url TEXT PRIMARY KEY,
            titre TEXT NOT NULL,
            entreprise TEXT,
            date_publication TEXT,
            details TEXT,
            date_decouverte TEXT,
            date_enregistrement TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Index pour recherche rapide
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_offres_date 
        ON offres_permanentes(date_enregistrement DESC)
    ''')

    conn.commit()
    if not USE_TURSO:
        conn.close()


def sauvegarder_offre_permanente(offre_data):
    """
    Sauvegarde une offre de manière permanente dans SQLite/Turso.
    """
    init_offres_permanentes_table()

    conn = _get_conn()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            INSERT OR REPLACE INTO offres_permanentes
            (url, titre, entreprise, date_publication, details, date_decouverte)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            offre_data.get('url', ''),
            offre_data.get('titre', ''),
            offre_data.get('entreprise', ''),
            offre_data.get('date_publication', ''),
            offre_data.get('details', ''),
            offre_data.get('date_decouverte', '')
        ))

        conn.commit()
        return True
    except Exception as e:
        print(f"⚠️ Erreur sauvegarde offre: {e}")
        return False
    finally:
        if not USE_TURSO:
            conn.close()


def charger_toutes_offres():
    """
    Charge toutes les offres depuis SQLite/Turso.
    Retourne un dictionnaire {url: offre_data} pour compatibilité.
    """
    init_offres_permanentes_table()

    if not USE_TURSO and not os.path.exists(DB_FILE):
        return {}

    conn = _get_conn()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            SELECT url, titre, entreprise, date_publication, details, date_decouverte
            FROM offres_permanentes
            ORDER BY date_enregistrement DESC
        ''')

        rows = cursor.fetchall()

        # Retourner au format dictionnaire pour compatibilité
        offres = {}
        for row in rows:
            url, titre, entreprise, date_publication, details, date_decouverte = row
            offres[url] = {
                'titre': titre,
                'entreprise': entreprise,
                'date_publication': date_publication,
                'url': url,
                'details': details,
                'date_decouverte': date_decouverte
            }

        return offres

    except Exception as e:
        print(f"⚠️ Erreur chargement offres: {e}")
        return {}
    finally:
        if not USE_TURSO:
            conn.close()


def offre_existe(url):
    """Vérifie si une offre existe déjà dans la base permanente."""
    init_offres_permanentes_table()

    conn = _get_conn()
    cursor = conn.cursor()

    cursor.execute('SELECT 1 FROM offres_permanentes WHERE url = ?', (url,))
    result = cursor.fetchone()

    if not USE_TURSO:
        conn.close()

    return result is not None


def compter_offres():
    """Retourne le nombre total d'offres enregistrées."""
    init_offres_permanentes_table()

    conn = _get_conn()
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM offres_permanentes')
    count = cursor.fetchone()[0]

    if not USE_TURSO:
        conn.close()

    return count


def exporter_vers_json(chemin_json):
    """Exporte les offres SQLite vers JSON (pour backup)."""
    offres = charger_toutes_offres()

    try:
        with open(chemin_json, 'w', encoding='utf-8') as f:
            json.dump(offres, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"⚠️ Erreur export JSON: {e}")
        return False


def importer_depuis_json(chemin_json):
    """Importe les offres depuis JSON vers SQLite."""
    if not os.path.exists(chemin_json):
        print(f"⚠️ Fichier JSON non trouvé: {chemin_json}")
        return False

    try:
        with open(chemin_json, 'r', encoding='utf-8') as f:
            offres = json.load(f)

        count = 0
        for url, offre_data in offres.items():
            # S'assurer que l'URL est dans l'offre
            offre_data['url'] = url
            if sauvegarder_offre_permanente(offre_data):
                count += 1

        print(f"✅ {count} offres importées depuis JSON")
        return True

    except Exception as e:
        print(f"⚠️ Erreur import JSON: {e}")
        return False
