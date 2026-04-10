"""
db.py — SQLite persistence layer.
Stores user language preferences + live-update subscriber list.
SQLite is free, file-based, and works perfectly on Render's ephemeral disk
(subscribers survive restarts within the same deploy).
"""
import sqlite3
import logging
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "data" / "culers_hub.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

_local = threading.local()


def _conn() -> sqlite3.Connection:
    if not hasattr(_local, "conn"):
        _local.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
    return _local.conn


def init_db() -> None:
    c = _conn()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            chat_id     INTEGER PRIMARY KEY,
            lang        TEXT    NOT NULL DEFAULT 'en',
            username    TEXT,
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS subscribers (
            chat_id     INTEGER PRIMARY KEY,
            active      INTEGER NOT NULL DEFAULT 1,
            updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
    c.commit()
    logger.info("Database initialised at %s", DB_PATH)


# ── User helpers ──────────────────────────────────────────

def upsert_user(chat_id: int, username: str = "", lang: str = "en") -> None:
    _conn().execute(
        """INSERT INTO users (chat_id, username, lang)
           VALUES (?, ?, ?)
           ON CONFLICT(chat_id) DO UPDATE SET username=excluded.username""",
        (chat_id, username, lang),
    )
    _conn().commit()


def get_user_lang(chat_id: int) -> str:
    row = _conn().execute(
        "SELECT lang FROM users WHERE chat_id = ?", (chat_id,)
    ).fetchone()
    return row["lang"] if row else "en"


def set_user_lang(chat_id: int, lang: str) -> None:
    _conn().execute(
        "UPDATE users SET lang = ? WHERE chat_id = ?", (lang, chat_id)
    )
    _conn().commit()


# ── Subscriber helpers ────────────────────────────────────

def subscribe(chat_id: int) -> bool:
    """Returns True if newly subscribed, False if already active."""
    row = _conn().execute(
        "SELECT active FROM subscribers WHERE chat_id = ?", (chat_id,)
    ).fetchone()
    if row and row["active"]:
        return False
    _conn().execute(
        """INSERT INTO subscribers (chat_id, active)
           VALUES (?, 1)
           ON CONFLICT(chat_id) DO UPDATE SET active=1,
           updated_at=CURRENT_TIMESTAMP""",
        (chat_id,),
    )
    _conn().commit()
    return True


def unsubscribe(chat_id: int) -> bool:
    """Returns True if successfully unsubscribed."""
    row = _conn().execute(
        "SELECT active FROM subscribers WHERE chat_id = ?", (chat_id,)
    ).fetchone()
    if not row or not row["active"]:
        return False
    _conn().execute(
        "UPDATE subscribers SET active=0, updated_at=CURRENT_TIMESTAMP WHERE chat_id=?",
        (chat_id,),
    )
    _conn().commit()
    return True


def get_all_subscribers() -> list[int]:
    rows = _conn().execute(
        "SELECT chat_id FROM subscribers WHERE active = 1"
    ).fetchall()
    return [r["chat_id"] for r in rows]
