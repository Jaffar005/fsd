"""Database layer with MongoDB Atlas primary and automatic SQLite fallback.

If MongoDB is reachable (e.g. on Hotspot/Home Wi-Fi), it uses MongoDB.
If MongoDB is blocked (e.g. on College Wi-Fi where port 27017 is blocked),
it automatically falls back to a local SQLite database (chat_history.db)
so the application never fails or crashes.
"""
import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "conversational_rag")
SQLITE_DB_PATH = os.path.join(os.path.dirname(__file__), "chat_history.db")

use_sqlite = False
mongo_client = None
mongo_db = None
_sessions_col = None
_messages_col = None


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now_dt().isoformat()


def _get_sqlite_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_sqlite() -> None:
    with _get_sqlite_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT,
                title_generated INTEGER DEFAULT 0,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT,
                content TEXT,
                sources TEXT,
                created_at TEXT
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_msg_session ON messages(session_id, created_at)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sess_updated ON sessions(updated_at DESC)"
        )


class _SessionsProxy:
    """Provides compatibility if code calls db.sessions.delete_one."""

    def delete_one(self, query: Dict[str, Any]) -> None:
        if not use_sqlite and _sessions_col is not None:
            _sessions_col.delete_one(query)
        else:
            session_id = query.get("_id")
            if session_id:
                with _get_sqlite_conn() as conn:
                    conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
                    conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))


sessions = _SessionsProxy()


DB_BACKEND = os.getenv("DB_BACKEND", "auto").lower()


def init_db() -> None:
    """Verify MongoDB connection. If blocked, unavailable, or DB_BACKEND=sqlite, use SQLite."""
    global use_sqlite, mongo_client, mongo_db, _sessions_col, _messages_col

    if DB_BACKEND == "sqlite":
        use_sqlite = True
        print("[DB] Using local SQLite database (chat_history.db).")
        _init_sqlite()
        return

    from pymongo import ASCENDING, DESCENDING, MongoClient

    try:
        logger.info("Attempting to connect to MongoDB...")
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=1500)
        client.admin.command("ping")
        mongo_client = client
        mongo_db = client[DB_NAME]
        _sessions_col = mongo_db["sessions"]
        _messages_col = mongo_db["messages"]

        _messages_col.create_index([("session_id", ASCENDING), ("created_at", ASCENDING)])
        _sessions_col.create_index([("updated_at", DESCENDING)])
        use_sqlite = False
        print("[DB] Connected successfully to MongoDB Atlas!")
    except Exception as exc:
        use_sqlite = True
        print(f"[DB] MongoDB unavailable ({exc}). Using local SQLite fallback (chat_history.db).")
        _init_sqlite()


def _session_out(doc: Dict[str, Any]) -> Dict[str, Any]:
    updated_at = doc.get("updated_at")
    if isinstance(updated_at, datetime):
        updated_at = updated_at.isoformat()
    return {
        "session_id": doc.get("_id") or doc.get("id"),
        "title": doc.get("title") or "New chat",
        "title_generated": bool(doc.get("title_generated", False)),
        "updated_at": str(updated_at or _now_iso()),
    }


def create_session(title: str) -> str:
    session_id = str(uuid.uuid4())
    now_dt = _now_dt()
    if not use_sqlite and _sessions_col is not None:
        _sessions_col.insert_one(
            {
                "_id": session_id,
                "title": title,
                "title_generated": False,
                "created_at": now_dt,
                "updated_at": now_dt,
            }
        )
    else:
        iso = now_dt.isoformat()
        with _get_sqlite_conn() as conn:
            conn.execute(
                "INSERT INTO sessions (id, title, title_generated, created_at, updated_at) VALUES (?, ?, 0, ?, ?)",
                (session_id, title, iso, iso),
            )
    return session_id


def session_exists(session_id: str) -> bool:
    if not use_sqlite and _sessions_col is not None:
        return _sessions_col.count_documents({"_id": session_id}, limit=1) > 0
    with _get_sqlite_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM sessions WHERE id = ? LIMIT 1", (session_id,)
        ).fetchone()
        return row is not None


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    if not use_sqlite and _sessions_col is not None:
        doc = _sessions_col.find_one({"_id": session_id})
        return _session_out(doc) if doc else None
    with _get_sqlite_conn() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return _session_out(dict(row)) if row else None


def list_sessions() -> List[Dict[str, Any]]:
    if not use_sqlite and _sessions_col is not None:
        from pymongo import DESCENDING
        return [_session_out(d) for d in _sessions_col.find().sort("updated_at", DESCENDING)]
    with _get_sqlite_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM sessions ORDER BY updated_at DESC"
        ).fetchall()
        return [_session_out(dict(r)) for r in rows]


def set_generated_title(session_id: str, title: str) -> None:
    if not use_sqlite and _sessions_col is not None:
        _sessions_col.update_one(
            {"_id": session_id},
            {"$set": {"title": title, "title_generated": True}},
        )
    else:
        with _get_sqlite_conn() as conn:
            conn.execute(
                "UPDATE sessions SET title = ?, title_generated = 1 WHERE id = ?",
                (title, session_id),
            )


def save_message(
    session_id: str,
    role: str,
    content: str,
    sources: Optional[List[Dict[str, Any]]] = None,
) -> None:
    now_dt = _now_dt()
    sources_data = sources or []
    if not use_sqlite and _messages_col is not None:
        _messages_col.insert_one(
            {
                "session_id": session_id,
                "role": role,
                "content": content,
                "sources": sources_data,
                "created_at": now_dt,
            }
        )
        _sessions_col.update_one({"_id": session_id}, {"$set": {"updated_at": now_dt}})
    else:
        iso = now_dt.isoformat()
        sources_json = json.dumps(sources_data)
        with _get_sqlite_conn() as conn:
            conn.execute(
                """
                INSERT INTO messages (session_id, role, content, sources, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, role, content, sources_json, iso),
            )
            conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (iso, session_id),
            )


def get_messages(session_id: str) -> List[Dict[str, Any]]:
    if not use_sqlite and _messages_col is not None:
        from pymongo import ASCENDING
        cursor = _messages_col.find({"session_id": session_id}).sort("created_at", ASCENDING)
        return [
            {
                "role": m["role"],
                "content": m["content"],
                "sources": m.get("sources", []),
                "created_at": m["created_at"].isoformat()
                if isinstance(m["created_at"], datetime)
                else str(m["created_at"]),
            }
            for m in cursor
        ]
    with _get_sqlite_conn() as conn:
        rows = conn.execute(
            "SELECT role, content, sources, created_at FROM messages WHERE session_id = ? ORDER BY id ASC",
            (session_id,),
        ).fetchall()
        result = []
        for r in rows:
            sources_val = []
            if r["sources"]:
                try:
                    sources_val = json.loads(r["sources"])
                except Exception:
                    sources_val = []
            result.append(
                {
                    "role": r["role"],
                    "content": r["content"],
                    "sources": sources_val,
                    "created_at": str(r["created_at"]),
                }
            )
        return result
