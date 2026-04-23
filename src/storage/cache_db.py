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

class AsyncTursoConn:
    """Wrapper pour rendre la connexion Turso (libsql) compatible avec async/await."""
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await asyncio.to_thread(self.conn.close)

    async def execute(self, sql, parameters=()):
        # Exécute la requête dans un thread pour ne pas bloquer l'event loop
        return await asyncio.to_thread(self._execute_sync, sql, parameters)

    def _execute_sync(self, sql, parameters):
        # Cette méthode tourne dans un thread
        cursor = self.conn.execute(sql, parameters)
        # On injecte des méthodes async sur le curseur pour la compatibilité
        return AsyncCursorWrapper(cursor)

    async def commit(self):
        await asyncio.to_thread(self.conn.commit)

class AsyncCursorWrapper:
    """Wrapper pour les résultats du curseur."""
    def __init__(self, cursor):
        self.cursor = cursor
    
    async def fetchone(self):
        return await asyncio.to_thread(self.cursor.fetchone)
    
    async def fetchall(self):
        return await asyncio.to_thread(self.cursor.fetchall)
    
    def __aiter__(self):
        return self

    async def __anext__(self):
        row = await self.fetchone()
        if row is None:
            raise StopAsyncIteration
        return row

    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass 

def get_async_conn():
    """
    Retourne une connexion asynchrone.
    Bascule sur Turso si configuré (via un wrapper async), sinon utilise aiosqlite local.
    """
    if USE_TURSO:
        logger.info(f"🌐 Connexion à Turso (Cloud): {TURSO_DATABASE_URL[:25]}...")
        # libsql.connect est synchrone, on le wrap pour l'asynchrone
        try:
            conn = libsql.connect(TURSO_DATABASE_URL, auth_token=TURSO_AUTH_TOKEN)
            return AsyncTursoConn(conn)
        except Exception as e:
            logger.error(f"❌ Erreur connexion Turso: {e}. Fallback local.")
            return aiosqlite.connect(DB_FILE)
    else:
        # aiosqlite est déjà asynchrone
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
                    linkedin_url TEXT,
                    facebook_url TEXT,
                    website_url TEXT,
                    date_enregistrement TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Migration : Ajouter les nouvelles colonnes si elles manquent
            for col in ['linkedin_url', 'facebook_url', 'website_url']:
                try:
                    await db.execute(f'ALTER TABLE offres_permanentes ADD COLUMN {col} TEXT')
                    await db.commit()
                except: pass

            await db.execute('CREATE INDEX IF NOT EXISTS idx_offres_date ON offres_permanentes(date_enregistrement DESC)')

            # Table profil matching (extrait du CV)
            await db.execute('''
                CREATE TABLE IF NOT EXISTS profil_matching (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    competences TEXT,       -- JSON array
                    annees_exp INTEGER,     -- 5
                    postes TEXT,           -- JSON array
                    niveau_etudes TEXT,    -- "Bac+5"
                    extrait_important TEXT, -- résumé du CV
                    date_extraction TEXT
                )
            ''')
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
        cursor = await db.execute('''
            SELECT titre, entreprise, date_publication, url, details, timestamp
            FROM offres WHERE cache_key = ?
        ''', (cache_key,))
        async with cursor:
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
        cursor = await db.execute('SELECT nom, email, telephone, portfolio, cv_text, date_mise_a_jour FROM cv_utilisateur WHERE id = 1')
        async with cursor:
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

async def sauvegarder_profil_matching_async(profil_data):
    """Sauvegarde le profil extrait du CV pour matching."""
    import json
    async with _db_lock:
        async with get_async_conn() as db:
            date_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            await db.execute('''
                INSERT OR REPLACE INTO profil_matching
                (id, competences, annees_exp, postes, niveau_etudes, extrait_important, date_extraction)
                VALUES (1, ?, ?, ?, ?, ?, ?)
            ''', (
                json.dumps(profil_data.get('competences', [])),
                profil_data.get('annees_exp', 0),
                json.dumps(profil_data.get('postes', [])),
                profil_data.get('niveau_etudes', ''),
                profil_data.get('extrait_important', ''),
                date_now
            ))
            await db.commit()

async def recuperer_profil_matching_async():
    """Récupère le profil pour matching."""
    import json
    async with get_async_conn() as db:
        cursor = await db.execute('''
            SELECT competences, annees_exp, postes, niveau_etudes, extrait_important, date_extraction
            FROM profil_matching WHERE id = 1
        ''')
        async with cursor:
            row = await cursor.fetchone()

    if not row:
        return None

    return {
        'competences': json.loads(row[0]) if row[0] else [],
        'annees_exp': row[1] or 0,
        'postes': json.loads(row[2]) if row[2] else [],
        'niveau_etudes': row[3] or '',
        'extrait_important': row[4] or '',
        'date_extraction': row[5] or ''
    }

async def offre_existe_async(url):
    """Vérifie si l'offre a déjà été traitée (stockage permanent) via son URL."""
    async with get_async_conn() as db:
        cursor = await db.execute('SELECT 1 FROM offres_permanentes WHERE url = ?', (url,))
        async with cursor:
            return await cursor.fetchone() is not None

async def offre_existe_doublon_async(titre, entreprise):
    """
    Vérifie si une offre similaire existe déjà (même titre et entreprise).
    Utile pour éviter les doublons entre différentes sources (PortalJob / Asako).
    """
    if not titre or not entreprise: return False
    async with get_async_conn() as db:
        # On utilise une recherche insensible à la casse et flexible
        cursor = await db.execute('''
            SELECT 1 FROM offres_permanentes 
            WHERE LOWER(titre) = LOWER(?) AND LOWER(entreprise) = LOWER(?)
        ''', (titre, entreprise))
        async with cursor:
            return await cursor.fetchone() is not None

async def sauvegarder_offre_permanente_async(offre_data):
    """Stockage permanent pour éviter les doublons au prochain scraping."""
    async with _db_lock:
        async with get_async_conn() as db:
            try:
                await db.execute('''
                    INSERT OR REPLACE INTO offres_permanentes
                    (url, titre, entreprise, date_publication, details, date_decouverte, 
                     linkedin_url, facebook_url, website_url)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    offre_data.get('url', ''),
                    offre_data.get('titre', ''),
                    offre_data.get('entreprise', ''),
                    offre_data.get('date_publication', ''),
                    offre_data.get('details', ''),
                    offre_data.get('date_decouverte', ''),
                    offre_data.get('linkedin_url'),
                    offre_data.get('facebook_url'),
                    offre_data.get('website_url')
                ))
                await db.commit()
                return True
            except Exception as e:
                logger.error(f"Erreur sauvegarde permanente: {e}")
                return False

async def compter_offres_async():
    async with get_async_conn() as db:
        cursor = await db.execute('SELECT COUNT(*) FROM offres_permanentes')
        async with cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

async def lister_offres_permanentes_async(limit=10, offset=0):
    async with get_async_conn() as db:
        cursor = await db.execute('''
            SELECT url, titre, entreprise, date_publication, details, linkedin_url, facebook_url, website_url 
            FROM offres_permanentes 
            ORDER BY date_enregistrement DESC 
            LIMIT ? OFFSET ?
        ''', (limit, offset))
        
        offres = []
        async with cursor:
            rows = await cursor.fetchall()
            for row in rows:
                offres.append({
                    'url': row[0],
                    'titre': row[1],
                    'entreprise': row[2],
                    'date_publication': row[3],
                    'details': row[4],
                    'linkedin_url': row[5],
                    'facebook_url': row[6],
                    'website_url': row[7]
                })
        return offres

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
def sauvegarder_profil_matching(d): return _run_async(sauvegarder_profil_matching_async(d))
def recuperer_profil_matching(): return _run_async(recuperer_profil_matching_async())
def vider_cache():
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
