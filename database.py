import sqlite3
import json
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# Connessione globale al database
conn = sqlite3.connect('trendduel.db', check_same_thread=False)
c = conn.cursor()

# Tabella utenti esistente
c.execute('''CREATE TABLE IF NOT EXISTS users
             (user_id INTEGER PRIMARY KEY, points INTEGER DEFAULT 0, reputation INTEGER DEFAULT 0,
              participations INTEGER DEFAULT 0, badges TEXT DEFAULT '')''')

# Tabella reazioni esistente con schema corretto
c.execute('''CREATE TABLE IF NOT EXISTS reactions
             (message_id INTEGER, user_id INTEGER, participant_id INTEGER,
              emoji TEXT, points_given INTEGER DEFAULT 0, reputation_given INTEGER DEFAULT 0,
              PRIMARY KEY (message_id, user_id))''')

# Tabella per tracking eventi settimanali
c.execute('''CREATE TABLE IF NOT EXISTS weekly_events
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL,
              event_type TEXT NOT NULL,
              points_earned INTEGER DEFAULT 0,
              reputation_earned INTEGER DEFAULT 0,
              timestamp TEXT NOT NULL,
              week_start TEXT NOT NULL,
              archived BOOLEAN DEFAULT 0,
              message_id INTEGER)''')

# Tabella per archivio classifiche settimanali
c.execute('''CREATE TABLE IF NOT EXISTS weekly_archives
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              week_start TEXT NOT NULL,
              week_end TEXT NOT NULL,
              embed_data TEXT NOT NULL,
              participants_count INTEGER DEFAULT 0,
              archived_at TEXT NOT NULL,
              hall_of_fame_message_id INTEGER)''')

# Nuova tabella per tracciare i repost in spotlight
c.execute('''CREATE TABLE IF NOT EXISTS spotlight_reposts
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              original_message_id INTEGER NOT NULL,
              spotlight_message_id INTEGER NOT NULL,
              user_id INTEGER NOT NULL,
              week_start TEXT NOT NULL,
              timestamp TEXT NOT NULL)''')

# --- gestione link inviati (per controllo duplicati) ---
c.execute('''
CREATE TABLE IF NOT EXISTS submitted_links (
    normalized_link TEXT PRIMARY KEY,
    raw_link TEXT,
    user_id INTEGER,
    message_id INTEGER,
    timestamp TEXT
)
''')

# indice per performance (opzionale ma consigliato)
c.execute('CREATE INDEX IF NOT EXISTS idx_submitted_links_time ON submitted_links (timestamp)')

def link_exists(normalized_link):
    """Ritorna True se normalized_link Ã¨ giÃ  presente nel DB."""
    try:
        c.execute('SELECT 1 FROM submitted_links WHERE normalized_link = ? LIMIT 1', (normalized_link,))
        return c.fetchone() is not None
    except Exception as e:
        logger.error(f"Errore link_exists: {e}")
        return False

def add_submitted_link(normalized_link, raw_link, user_id, message_id, timestamp):
    """Inserisce un link normalizzato nel DB (INSERT OR IGNORE)."""
    try:
        c.execute('INSERT OR IGNORE INTO submitted_links (normalized_link, raw_link, user_id, message_id, timestamp) VALUES (?,?,?,?,?)',
                  (normalized_link, raw_link, user_id, message_id, timestamp))
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Errore add_submitted_link: {e}")
        return False

# Migrazione: aggiungi colonne mancanti se non esistono
try:
    c.execute('ALTER TABLE reactions ADD COLUMN emoji TEXT')
    c.execute('ALTER TABLE reactions ADD COLUMN points_given INTEGER DEFAULT 0')
    c.execute('ALTER TABLE reactions ADD COLUMN reputation_given INTEGER DEFAULT 0')
    conn.commit()
    print("Database migrato con successo")
except sqlite3.OperationalError:
    print("Database giÃ  aggiornato o errore nella migrazione")

conn.commit()

def record_weekly_event(user_id, event_type, points=0, reputation=0, message_id=None):
    """
    Registra un evento settimanale per il tracking della classifica
    """
    try:
        from config import ITALY_TZ
        from utils import get_week_boundaries
        now = datetime.now(ITALY_TZ)
        week_start, week_end = get_week_boundaries(now)

        c.execute('''INSERT INTO weekly_events 
                     (user_id, event_type, points_earned, reputation_earned, timestamp, week_start, message_id)
                     VALUES (?, ?, ?, ?, ?, ?, ?)''',
                 (user_id, event_type, points, reputation, now.isoformat(), week_start.isoformat(), message_id))
        conn.commit()

        logger.info(f"Evento settimanale registrato: {event_type} per utente {user_id} (+{points}pts, +{reputation}rep)")
    except Exception as e:
        logger.error(f"Errore nella registrazione evento settimanale: {e}")

def count_weekly_event_type(user_id, event_type):
    """
    Ritorna il numero di eventi 'event_type' registrati per l'utente nella settimana corrente (non archiviati).
    """
    try:
        from config import ITALY_TZ
        from utils import get_week_boundaries
        now = datetime.now(ITALY_TZ)
        week_start, week_end = get_week_boundaries(now)
        week_start_str = week_start.isoformat()
        week_end_str = week_end.isoformat()

        c.execute('''
            SELECT COUNT(*) FROM weekly_events
            WHERE user_id = ? AND event_type = ? AND timestamp >= ? AND timestamp < ? AND archived = 0
        ''', (user_id, event_type, week_start_str, week_end_str))
        row = c.fetchone()
        return row[0] if row else 0
    except Exception as e:
        logger.error(f"Errore count_weekly_event_type: {e}")
        return 0


def get_weekly_leaderboard(week_start=None, week_end=None):
    """
    Calcola la classifica settimanale basata sugli eventi registrati
    """
    from utils import get_week_boundaries
    if week_start is None or week_end is None:
        week_start, week_end = get_week_boundaries()

    # Converte in string se necessario
    if isinstance(week_start, datetime):
        week_start_str = week_start.isoformat()
    else:
        week_start_str = week_start

    if isinstance(week_end, datetime):
        week_end_str = week_end.isoformat()
    else:
        week_end_str = week_end

    # Query per ottenere la classifica settimanale
    c.execute('''
        SELECT 
            we.user_id,
            SUM(we.points_earned) as weekly_points,
            SUM(we.reputation_earned) as weekly_reputation,
            COUNT(DISTINCT we.message_id) as weekly_participations,
            MIN(we.timestamp) as first_participation,
            u.reputation as total_reputation
        FROM weekly_events we
        LEFT JOIN users u ON we.user_id = u.user_id
        WHERE we.timestamp >= ? AND we.timestamp < ? AND we.archived = 0
        GROUP BY we.user_id
        ORDER BY weekly_points DESC, total_reputation DESC, first_participation ASC
        LIMIT 10
    ''', (week_start_str, week_end_str))

    return c.fetchall()

def reset_weekly_metrics(week_start, week_end):
    """
    Marca gli eventi della settimana come archiviati
    """
    try:
        week_start_str = week_start.isoformat()
        week_end_str = week_end.isoformat()

        c.execute('''UPDATE weekly_events 
                     SET archived = 1 
                     WHERE timestamp >= ? AND timestamp < ? AND archived = 0''',
                 (week_start_str, week_end_str))

        affected_rows = c.rowcount
        conn.commit()

        logger.info(f"Reset settimanale completato: {affected_rows} eventi archiviati")
        return affected_rows

    except Exception as e:
        logger.error(f"Errore nel reset settimanale: {e}")
        return 0