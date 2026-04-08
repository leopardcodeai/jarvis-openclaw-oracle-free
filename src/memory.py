import sqlite3
import asyncio
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path("jarvis_memory.db")


def _init_db():
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category TEXT DEFAULT 'note',
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    con.commit()
    con.close()


_init_db()


def _add_sync(user_id: int, content: str, category: str) -> int:
    con = sqlite3.connect(DB_PATH)
    cur = con.execute(
        "INSERT INTO memories (user_id, category, content, created_at) VALUES (?, ?, ?, ?)",
        (user_id, category, content, datetime.now().strftime("%Y-%m-%d %H:%M"))
    )
    row_id = cur.lastrowid
    con.commit()
    con.close()
    return row_id


def _list_sync(user_id: int, category: str | None, limit: int) -> list[dict]:
    con = sqlite3.connect(DB_PATH)
    if category:
        rows = con.execute(
            "SELECT id, category, content, created_at FROM memories WHERE user_id=? AND category=? ORDER BY id DESC LIMIT ?",
            (user_id, category, limit)
        ).fetchall()
    else:
        rows = con.execute(
            "SELECT id, category, content, created_at FROM memories WHERE user_id=? ORDER BY id DESC LIMIT ?",
            (user_id, limit)
        ).fetchall()
    con.close()
    return [{"id": r[0], "category": r[1], "content": r[2], "created_at": r[3]} for r in rows]


def _search_sync(user_id: int, query: str) -> list[dict]:
    con = sqlite3.connect(DB_PATH)
    rows = con.execute(
        "SELECT id, category, content, created_at FROM memories WHERE user_id=? AND content LIKE ? ORDER BY id DESC LIMIT 10",
        (user_id, f"%{query}%")
    ).fetchall()
    con.close()
    return [{"id": r[0], "category": r[1], "content": r[2], "created_at": r[3]} for r in rows]


def _delete_sync(user_id: int, memory_id: int) -> bool:
    con = sqlite3.connect(DB_PATH)
    cur = con.execute("DELETE FROM memories WHERE id=? AND user_id=?", (memory_id, user_id))
    con.commit()
    con.close()
    return cur.rowcount > 0


async def add_memory(user_id: int, content: str, category: str = "note") -> int:
    return await asyncio.get_event_loop().run_in_executor(None, _add_sync, user_id, content, category)


async def list_memories(user_id: int, category: str | None = None, limit: int = 10) -> list[dict]:
    return await asyncio.get_event_loop().run_in_executor(None, _list_sync, user_id, category, limit)


async def search_memories(user_id: int, query: str) -> list[dict]:
    return await asyncio.get_event_loop().run_in_executor(None, _search_sync, user_id, query)


async def delete_memory(user_id: int, memory_id: int) -> bool:
    return await asyncio.get_event_loop().run_in_executor(None, _delete_sync, user_id, memory_id)


CATEGORY_EMOJI = {
    "note": "📝", "shopping": "🛒", "reminder": "⏰", "idea": "💡",
    "todo": "✅", "link": "🔗", "info": "ℹ️",
}


def format_memories(entries: list[dict], title: str = "Erinnerungen") -> str:
    if not entries:
        return f"🧠 Keine {title} gefunden."
    lines = [f"🧠 *{title}*\n"]
    for e in entries:
        emoji = CATEGORY_EMOJI.get(e["category"], "📌")
        lines.append(f"{emoji} `#{e['id']}` [{e['category']}] {e['content']}\n   _{e['created_at']}_")
    return "\n".join(lines)
