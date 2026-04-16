"""
Gestionnaire de cache avec support Turso (SQLite cloud) + fallback SQLite local.
Support Asynchrone ajouté pour la stabilité.
"""
import sqlite3
import aiosqlite
import json
import time
import os
import asyncio
from datetime import datetime, timedelta
from ..config import TURSO_DATABASE_URL, TURSO_AUTH_TOKEN
from ..utils.logger import logger

# Vérifier si libsql est disponible
try:
    import libsql_experimental as libsql
    _LIBSQL_AVAILABLE = True
except ImportError:
    _LIBSQL_AVAILABLE = False

USE_TURSO = TURSO_DATABASE_URL and TURSO_AUTH_TOKEN and _LIBSQL_AVAILABLE

# Fallback SQLite local
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_FILE = os.path.join(BASE_DIR, "telegram_cache.db")
MAX_AGE_HOURS = 24

# Verrou pour éviter les accès concurrents sur SQLite local en async
_db_lock = asyncio.Lock()

def get_async_conn():
    """
    Retourne une connexion asynchrone.
    Bascule sur Turso si configuré, sinon utilise SQLite local.
    """
    if USE_TURSO:
        logger.info(f"🌐 Connexion à Turso (Cloud): {TURSO_DATABASE_URL[:20]}...")
        # libsql-experimental supporte l'async
        return libsql.connect(TURSO_DATABASE_URL, auth_token=TURSO_AUTH_TOKEN)
    else:
        # aiosqlite pour le local
        return aiosqlite.connect(DB_FILE)

async def init_db_async():
    """Initialise les tables de manière asynchrone."""
    async with _db_lock:
        async with get_async_conn() as db:
            # Table des offres temporaires (cache Telegram)
            await db.execute('''
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
            
            # Table CV
            await db.execute('''
                CREATE TABLE IF NOT EXISTS cv_utilisateur (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    nom TEXT,
                    email TEXT,
                    telephone TEXT,
                    portfolio TEXT,
                    cv_text TEXT NOT NULL,
                    date_mise_a_jour TEXT
                )
            ''')
            
            # Migration : Ajouter portfolio si absent
            try:
                await db.execute('ALTER TABLE cv_utilisateur ADD COLUMN portfolio TEXT')
                await db.commit()
            except:
                pass # Déjà présent
            
            # Table offres permanentes
            await db.execute('''
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
            
            await db.execute('CREATE INDEX IF NOT EXISTS idx_offres_date ON offres_permanentes(date_enregistrement DESC)')
            await db.commit()

async def ajouter_offre_async(offre_data):
    """Sert de cache temporaire pour les boutons Telegram (callback data)."""
    url = offre_data.get('url', '')
    cache_key = f"offre_{hash(url) & 0x7FFFFFFF}"
    
    async with _db_lock:
        async with get_async_conn() as db:
            await db.execute('''
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
            await db.commit()
    
    await nettoyer_vieilles_offres_async()
    return cache_key

async def recuperer_offre_async(cache_key):
    """Récupère une offre depuis le cache temporaire."""
    async with get_async_conn() as db:
        async with db.execute('''
            SELECT titre, entreprise, date_publication, url, details, timestamp
            FROM offres WHERE cache_key = ?
        ''', (cache_key,)) as cursor:
            row = await cursor.fetchone()
            
    if row is None:
        return None

    titre, entreprise, date_pub, url, details, timestamp = row
    if (time.time() - timestamp) / 3600 > MAX_AGE_HOURS:
        return None

    return {
        'titre': titre, 'entreprise': entreprise, 'date_publication': date_pub,
        'url': url, 'details': details
    }

async def nettoyer_vieilles_offres_async():
    """Supprime les vieilles offres du cache temporaire."""
    cutoff = time.time() - (MAX_AGE_HOURS * 3600)
    async with _db_lock:
        async with get_async_conn() as db:
            await db.execute('DELETE FROM offres WHERE timestamp < ?', (cutoff,))
            # Garder un maximum de 50 entrées récentes
            await db.execute('''
                DELETE FROM offres WHERE cache_key NOT IN (
                    SELECT cache_key FROM offres ORDER BY timestamp DESC LIMIT 50
                )
            ''')
            await db.commit()

async def sauvegarder_cv_async(nom, email, telephone, portfolio, cv_text):
    async with _db_lock:
        async with get_async_conn() as db:
            date_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            await db.execute('''
                INSERT OR REPLACE INTO cv_utilisateur
                (id, nom, email, telephone, portfolio, cv_text, date_mise_a_jour)
                VALUES (1, ?, ?, ?, ?, ?, ?)
            ''', (nom, email, telephone, portfolio, cv_text, date_now))
            await db.commit()

async def recuperer_cv_async():
    async with get_async_conn() as db:
        async with db.execute('SELECT nom, email, telephone, portfolio, cv_text, date_mise_a_jour FROM cv_utilisateur WHERE id = 1') as cursor:
            row = await cursor.fetchone()
    if not row: return None
    return {
        'nom': row[0], 
        'email': row[1], 
        'telephone': row[2], 
        'portfolio': row[3], 
        'cv_text': row[4], 
        'date_mise_a_jour': row[5]
    }

async def offre_existe_async(url):
    """Vérifie si l'offre a déjà été traitée (stockage permanent)."""
    async with get_async_conn() as db:
        async with db.execute('SELECT 1 FROM offres_permanentes WHERE url = ?', (url,)) as cursor:
            return await cursor.fetchone() is not None

async def sauvegarder_offre_permanente_async(offre_data):
    """Stockage permanent pour éviter les doublons au prochain scraping."""
    async with _db_lock:
        async with get_async_conn() as db:
            try:
                await db.execute('''
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
                await db.commit()
                return True
            except Exception as e:
                logger.error(f"Erreur sauvegarde permanente: {e}")
                return False

async def compter_offres_async():
    async with get_async_conn() as db:
        async with db.execute('SELECT COUNT(*) FROM offres_permanentes') as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

# --- Compatibilité Synchrone (Wrapper autour de l'async) ---
def _run_async(coro):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

def init_db(): _run_async(init_db_async())
def ajouter_offre(d): return _run_async(ajouter_offre_async(d))
def recuperer_offre(k): return _run_async(recuperer_offre_async(k))
def offre_existe(u): return _run_async(offre_existe_async(u))
def sauvegarder_offre_permanente(d): return _run_async(sauvegarder_offre_permanente_async(d))
def compter_offres(): return _run_async(compter_offres_async())
def recuperer_cv(): return _run_async(recuperer_cv_async())
def sauvegarder_cv(n, e, t, p, c): return _run_async(sauvegarder_cv_async(n, e, t, p, c))
def vider_cache():
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
