"""
Jarvis Script Runner – generates, saves, executes, and reuses Python scripts.
"""

import asyncio
import logging
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "jarvis_scripts.db"
SCRIPTS_DIR = Path(__file__).parent.parent / "jarvis_scripts"
SCRIPTS_DIR.mkdir(exist_ok=True)

TIMEOUT_SECONDS = 15

# Patterns blocked before execution
BLOCKED_PATTERNS = [
    r"\bos\.system\b", r"\bos\.popen\b", r"\bsubprocess\b",
    r"\bshutil\.rmtree\b", r"\bshutil\.move\b", r"\bos\.remove\b",
    r"\bos\.unlink\b", r"\brm\s+-rf\b",
    r"open\s*\([^)]*['\"]w['\"]",   # open(..., "w")
    r"open\s*\([^)]*['\"]a['\"]",   # open(..., "a")
    r"\beval\s*\(", r"\bexec\s*\(",
    r"\b__import__\s*\(",
]


def _init_db():
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS scripts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT UNIQUE NOT NULL,
            description TEXT,
            tags        TEXT,
            code        TEXT NOT NULL,
            created_at  TEXT NOT NULL,
            last_used   TEXT,
            use_count   INTEGER DEFAULT 0,
            last_output TEXT
        )
    """)
    con.commit()
    con.close()


_init_db()


# ── Safety ────────────────────────────────────────────────────────────────────

def _safety_check(code: str) -> tuple[bool, str]:
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, code):
            return False, f"Geblockt: `{pattern}`"
    return True, ""


# ── Execution ─────────────────────────────────────────────────────────────────

def _run_script_sync(code: str, args: list[str] | None = None) -> dict:
    safe, reason = _safety_check(code)
    if not safe:
        return {"success": False, "error": f"Sicherheitsprüfung fehlgeschlagen: {reason}",
                "stdout": "", "stderr": "", "duration": 0}

    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(code)
        tmp_path = f.name

    start = time.time()
    try:
        result = subprocess.run(
            [sys.executable, tmp_path] + (args or []),
            capture_output=True, text=True, timeout=TIMEOUT_SECONDS,
            cwd=str(SCRIPTS_DIR),
        )
        duration = round(time.time() - start, 2)
        stdout = result.stdout[:8000]
        stderr = result.stderr[:2000]
        return {
            "success": result.returncode == 0,
            "stdout": stdout,
            "stderr": stderr,
            "returncode": result.returncode,
            "duration": duration,
            "error": stderr if result.returncode != 0 else "",
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Timeout nach {TIMEOUT_SECONDS}s",
                "stdout": "", "stderr": "", "duration": TIMEOUT_SECONDS}
    except Exception as e:
        return {"success": False, "error": str(e),
                "stdout": "", "stderr": "", "duration": 0}
    finally:
        Path(tmp_path).unlink(missing_ok=True)


async def run_code(code: str, args: list[str] | None = None) -> dict:
    return await asyncio.get_event_loop().run_in_executor(None, _run_script_sync, code, args)


# ── Library ───────────────────────────────────────────────────────────────────

def _save_script_sync(name: str, description: str, tags: str, code: str, last_output: str = "") -> int:
    con = sqlite3.connect(DB_PATH)
    try:
        now = datetime.now().isoformat()
        con.execute("""
            INSERT INTO scripts (name, description, tags, code, created_at, last_output)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                description=excluded.description,
                tags=excluded.tags,
                code=excluded.code,
                last_used=excluded.created_at,
                last_output=excluded.last_output,
                use_count=use_count+1
        """, (name, description, tags, code, now, last_output))
        con.commit()
        row = con.execute("SELECT id FROM scripts WHERE name=?", (name,)).fetchone()
        return row[0] if row else -1
    finally:
        con.close()


def _search_scripts_sync(query: str) -> list[dict]:
    con = sqlite3.connect(DB_PATH)
    try:
        q = f"%{query.lower()}%"
        rows = con.execute("""
            SELECT id, name, description, tags, code, last_used, use_count, last_output
            FROM scripts
            WHERE LOWER(name) LIKE ? OR LOWER(description) LIKE ? OR LOWER(tags) LIKE ?
            ORDER BY use_count DESC, last_used DESC
            LIMIT 5
        """, (q, q, q)).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        con.close()


def _list_scripts_sync() -> list[dict]:
    con = sqlite3.connect(DB_PATH)
    try:
        rows = con.execute("""
            SELECT id, name, description, tags, code, last_used, use_count, last_output
            FROM scripts ORDER BY use_count DESC, last_used DESC
        """).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        con.close()


def _get_script_sync(id_or_name: str | int) -> dict | None:
    con = sqlite3.connect(DB_PATH)
    try:
        if isinstance(id_or_name, int) or str(id_or_name).isdigit():
            row = con.execute(
                "SELECT id,name,description,tags,code,last_used,use_count,last_output FROM scripts WHERE id=?",
                (int(id_or_name),)
            ).fetchone()
        else:
            row = con.execute(
                "SELECT id,name,description,tags,code,last_used,use_count,last_output FROM scripts WHERE name=?",
                (id_or_name,)
            ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        con.close()


def _delete_script_sync(id_or_name: str | int) -> bool:
    con = sqlite3.connect(DB_PATH)
    try:
        if isinstance(id_or_name, int) or str(id_or_name).isdigit():
            con.execute("DELETE FROM scripts WHERE id=?", (int(id_or_name),))
        else:
            con.execute("DELETE FROM scripts WHERE name=?", (id_or_name,))
        con.commit()
        return con.total_changes > 0
    finally:
        con.close()


def _update_last_output_sync(name: str, output: str):
    con = sqlite3.connect(DB_PATH)
    try:
        con.execute(
            "UPDATE scripts SET last_output=?, last_used=?, use_count=use_count+1 WHERE name=?",
            (output[:4000], datetime.now().isoformat(), name)
        )
        con.commit()
    finally:
        con.close()


def _row_to_dict(row) -> dict:
    return {
        "id": row[0], "name": row[1], "description": row[2],
        "tags": row[3], "code": row[4], "last_used": row[5],
        "use_count": row[6], "last_output": row[7],
    }


async def save_script(name: str, description: str, tags: str, code: str, last_output: str = "") -> int:
    return await asyncio.get_event_loop().run_in_executor(
        None, _save_script_sync, name, description, tags, code, last_output
    )


async def search_scripts(query: str) -> list[dict]:
    return await asyncio.get_event_loop().run_in_executor(None, _search_scripts_sync, query)


async def list_scripts() -> list[dict]:
    return await asyncio.get_event_loop().run_in_executor(None, _list_scripts_sync)


async def get_script(id_or_name) -> dict | None:
    return await asyncio.get_event_loop().run_in_executor(None, _get_script_sync, id_or_name)


async def delete_script(id_or_name) -> bool:
    return await asyncio.get_event_loop().run_in_executor(None, _delete_script_sync, id_or_name)


async def update_last_output(name: str, output: str):
    await asyncio.get_event_loop().run_in_executor(None, _update_last_output_sync, name, output)


# ── LLM response parser ───────────────────────────────────────────────────────

EXEC_MARKER = re.compile(
    r"\[JARVIS_EXEC:\s*name=([^\]|,]+)(?:,\s*tags=([^\]]+))?\]",
    re.IGNORECASE
)
CODE_BLOCK = re.compile(r"```(?:python)?\n(.*?)```", re.DOTALL)


def extract_script_from_response(text: str) -> dict | None:
    """Extract script + metadata if LLM marked a block for execution."""
    marker = EXEC_MARKER.search(text)
    code_match = CODE_BLOCK.search(text)
    if not marker or not code_match:
        return None

    name = marker.group(1).strip().replace(" ", "_").lower()[:40]
    tags = marker.group(2).strip() if marker.group(2) else ""
    code = code_match.group(1).strip()

    # Remove marker + code block from display text
    clean = EXEC_MARKER.sub("", text)
    clean = CODE_BLOCK.sub("", clean).strip()

    return {"name": name, "tags": tags, "code": code, "clean_text": clean}


# ── Formatters ────────────────────────────────────────────────────────────────

def format_scripts_list(scripts: list[dict]) -> str:
    if not scripts:
        return "📂 Keine Skripte in der Library."
    lines = ["📂 *Jarvis Script Library:*\n"]
    for s in scripts:
        used = f", verwendet {s['use_count']}×" if s['use_count'] else ""
        tags = f" `[{s['tags']}]`" if s['tags'] else ""
        lines.append(f"*#{s['id']}* `{s['name']}`{tags}\n_{s['description'] or 'Kein Beschreibung'}_{used}\n")
    return "\n".join(lines)


def format_run_result(result: dict, script_name: str = "") -> str:
    label = f"`{script_name}`" if script_name else "Skript"
    if not result["success"]:
        return f"❌ {label} fehlgeschlagen:\n```\n{result['error'][:800]}\n```"
    out = result["stdout"] or "(kein Output)"
    duration = result.get("duration", 0)
    header = f"✅ {label} ausgeführt in {duration}s\n\n"
    if len(out) > 3000:
        out = out[:3000] + "\n...(gekürzt)"
    return header + f"```\n{out}\n```"
