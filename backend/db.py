import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from .config import DATABASE


def now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connect():
    db = sqlite3.connect(DATABASE, timeout=20)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db():
    with connect() as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.executescript("""
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS accounts (
            id TEXT PRIMARY KEY, provider TEXT NOT NULL, email TEXT NOT NULL,
            name TEXT NOT NULL, color TEXT NOT NULL DEFAULT '#6b8bcd',
            cursor TEXT, last_sync TEXT, error TEXT, demo INTEGER NOT NULL DEFAULT 0,
            UNIQUE(provider,email)
        );
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            remote_id TEXT NOT NULL, thread_id TEXT, sender TEXT NOT NULL,
            sender_email TEXT NOT NULL, subject TEXT NOT NULL, body TEXT NOT NULL,
            received_at TEXT NOT NULL, category TEXT NOT NULL, priority TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 0, signals TEXT NOT NULL DEFAULT '[]',
            unread INTEGER NOT NULL DEFAULT 1, starred INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'pending', snoozed_until TEXT,
            analysis TEXT, analysis_source TEXT, draft TEXT, analyzed_at TEXT,
            source_url TEXT, content_hash TEXT NOT NULL, corrected INTEGER NOT NULL DEFAULT 0,
            editorial INTEGER NOT NULL DEFAULT 0,
            scam INTEGER, scam_reason TEXT, scam_dismissed INTEGER NOT NULL DEFAULT 0,
            UNIQUE(account_id,remote_id)
        );
        CREATE INDEX IF NOT EXISTS messages_received ON messages(received_at DESC);
        CREATE INDEX IF NOT EXISTS messages_account ON messages(account_id);
        CREATE TABLE IF NOT EXISTS feedback (
            message_id TEXT PRIMARY KEY REFERENCES messages(id) ON DELETE CASCADE,
            text TEXT NOT NULL, category TEXT NOT NULL, priority TEXT NOT NULL,
            group_id TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS samples (
            id TEXT PRIMARY KEY, text TEXT NOT NULL, category TEXT NOT NULL,
            priority TEXT NOT NULL, group_id TEXT NOT NULL, source TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, kind TEXT NOT NULL, target TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued', error TEXT, result TEXT,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE UNIQUE INDEX IF NOT EXISTS jobs_active ON jobs(kind,target)
            WHERE status IN ('queued','running');
        CREATE TABLE IF NOT EXISTS qev_cache (
            key TEXT NOT NULL, model TEXT NOT NULL, probs TEXT NOT NULL, created_at TEXT NOT NULL,
            PRIMARY KEY(key, model)
        );
        """)
        db.execute("UPDATE jobs SET status='queued' WHERE status='running'")
        # editorial=1: rótulos e resumo escritos à mão na demonstração; os modelos não os alteram.
        # Bancos anteriores só tinham mensagens editoriais nas contas de demonstração.
        columns = {row[1] for row in db.execute("PRAGMA table_info(messages)")}
        if "editorial" not in columns:
            db.execute("ALTER TABLE messages ADD COLUMN editorial INTEGER NOT NULL DEFAULT 0")
            db.execute("UPDATE messages SET editorial=1 WHERE account_id IN (SELECT id FROM accounts WHERE demo=1)")
        # Alerta de golpe: scam NULL = ainda não verificado, 1 = suspeito, 0 = sem sinais, -1 = falha na verificação.
        for column, ddl in (("scam", "INTEGER"), ("scam_reason", "TEXT"), ("scam_dismissed", "INTEGER NOT NULL DEFAULT 0")):
            if column not in columns:
                db.execute(f"ALTER TABLE messages ADD COLUMN {column} {ddl}")


def get_setting(key, default=None):
    with connect() as db:
        row = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return json.loads(row[0]) if row else default


def set_setting(key, value):
    with connect() as db:
        db.execute("INSERT OR REPLACE INTO settings(key,value) VALUES (?,?)", (key, json.dumps(value)))


def rows(query, params=()):
    with connect() as db:
        return [dict(row) for row in db.execute(query, params).fetchall()]
