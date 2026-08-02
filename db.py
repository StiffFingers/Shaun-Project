"""Journal storage: Supabase (Postgres) when configured, else local SQLite.

Supabase keeps data permanent on Streamlit Cloud.
Local SQLite is used only when [supabase] secrets are missing (dev/offline).
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Generator, Optional

DB_PATH = Path(__file__).parent / "data" / "journal.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS workers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_date TEXT NOT NULL,
    worker_id INTEGER NOT NULL,
    project_id INTEGER NOT NULL,
    weather TEXT NOT NULL DEFAULT '',
    hours_worked REAL NOT NULL DEFAULT 0,
    work_done TEXT NOT NULL DEFAULT '',
    crew_notes TEXT NOT NULL DEFAULT '',
    materials_notes TEXT NOT NULL DEFAULT '',
    issues_delays TEXT NOT NULL DEFAULT '',
    safety_notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (worker_id) REFERENCES workers(id),
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE INDEX IF NOT EXISTS idx_entries_date ON entries(entry_date);
CREATE INDEX IF NOT EXISTS idx_entries_worker ON entries(worker_id);
CREATE INDEX IF NOT EXISTS idx_entries_project ON entries(project_id);
"""


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _as_date_str(entry_date: date | str) -> str:
    if isinstance(entry_date, date):
        return entry_date.isoformat()
    return str(entry_date)[:10]


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------


def _supabase_config() -> Optional[dict[str, str]]:
    try:
        import streamlit as st

        cfg = st.secrets.get("supabase", None)
        if not cfg:
            return None
        url = str(cfg.get("url", "")).strip()
        key = str(cfg.get("key", "")).strip()
        if url and key:
            return {"url": url, "key": key}
    except Exception:
        pass
    return None


def using_supabase() -> bool:
    return _supabase_config() is not None


def storage_label() -> str:
    return "Supabase (cloud, permanent)" if using_supabase() else "Local SQLite (resets on Streamlit Cloud)"


@lru_cache(maxsize=1)
def _supabase_client():
    from supabase import create_client

    cfg = _supabase_config()
    if not cfg:
        raise RuntimeError("Supabase is not configured")
    return create_client(cfg["url"], cfg["key"])


def _sb():
    # Don't cache forever if secrets change mid-session in rare cases
    return _supabase_client()


def _normalize_worker(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    out["active"] = 1 if out.get("active") in (True, 1, "1", "true", "t") else 0
    if out.get("created_at") is not None:
        out["created_at"] = str(out["created_at"])
    return out


def _normalize_project(row: dict[str, Any]) -> dict[str, Any]:
    return _normalize_worker(row)


def _flatten_entry(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    workers = out.pop("workers", None) or {}
    projects = out.pop("projects", None) or {}
    if isinstance(workers, dict):
        out["worker_name"] = workers.get("name", "")
    if isinstance(projects, dict):
        out["project_name"] = projects.get("name", "")
    if out.get("entry_date") is not None:
        out["entry_date"] = str(out["entry_date"])[:10]
    for key in ("created_at", "updated_at"):
        if out.get(key) is not None:
            out[key] = str(out[key])
    if out.get("hours_worked") is not None:
        out["hours_worked"] = float(out["hours_worked"])
    if out.get("active") is not None:
        out["active"] = 1 if out["active"] in (True, 1, "1") else 0
    return out


def _raise_sb(resp_error: Any, action: str) -> None:
    if resp_error:
        raise RuntimeError(f"Supabase {action} failed: {resp_error}")


# ---------------------------------------------------------------------------
# SQLite helpers
# ---------------------------------------------------------------------------


@contextmanager
def get_conn() -> Generator[sqlite3.Connection, None, None]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def init_db() -> None:
    if using_supabase():
        # Schema is created once via supabase_schema.sql in the Supabase dashboard.
        return
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def seed_defaults() -> None:
    """Add starter workers/projects if tables are empty."""
    workers = list_workers(active_only=False)
    projects = list_projects(active_only=False)
    if not workers:
        for name in ("Alex Rivera", "Jordan Lee", "Sam Patel"):
            try:
                add_worker(name)
            except Exception:
                pass
    if not projects:
        for name in ("Main Site A", "Warehouse Renovation", "Road Extension"):
            try:
                add_project(name)
            except Exception:
                pass


# --- Workers ---


def list_workers(active_only: bool = True) -> list[dict[str, Any]]:
    if using_supabase():
        q = _sb().table("workers").select("*").order("name")
        if active_only:
            q = q.eq("active", True)
        resp = q.execute()
        return [_normalize_worker(r) for r in (resp.data or [])]

    with get_conn() as conn:
        if active_only:
            rows = conn.execute(
                "SELECT * FROM workers WHERE active = 1 ORDER BY name"
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM workers ORDER BY name").fetchall()
        return [dict(r) for r in rows]


def add_worker(name: str) -> int:
    name = name.strip()
    if not name:
        raise ValueError("Worker name is required")

    if using_supabase():
        resp = (
            _sb()
            .table("workers")
            .insert({"name": name, "active": True})
            .execute()
        )
        if not resp.data:
            raise RuntimeError("Failed to add worker in Supabase")
        return int(resp.data[0]["id"])

    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO workers (name, active, created_at) VALUES (?, 1, ?)",
            (name, _now()),
        )
        return int(cur.lastrowid)


def set_worker_active(worker_id: int, active: bool) -> None:
    if using_supabase():
        _sb().table("workers").update({"active": bool(active)}).eq(
            "id", worker_id
        ).execute()
        return

    with get_conn() as conn:
        conn.execute(
            "UPDATE workers SET active = ? WHERE id = ?",
            (1 if active else 0, worker_id),
        )


# --- Projects ---


def list_projects(active_only: bool = True) -> list[dict[str, Any]]:
    if using_supabase():
        q = _sb().table("projects").select("*").order("name")
        if active_only:
            q = q.eq("active", True)
        resp = q.execute()
        return [_normalize_project(r) for r in (resp.data or [])]

    with get_conn() as conn:
        if active_only:
            rows = conn.execute(
                "SELECT * FROM projects WHERE active = 1 ORDER BY name"
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM projects ORDER BY name").fetchall()
        return [dict(r) for r in rows]


def add_project(name: str) -> int:
    name = name.strip()
    if not name:
        raise ValueError("Project name is required")

    if using_supabase():
        resp = (
            _sb()
            .table("projects")
            .insert({"name": name, "active": True})
            .execute()
        )
        if not resp.data:
            raise RuntimeError("Failed to add project in Supabase")
        return int(resp.data[0]["id"])

    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO projects (name, active, created_at) VALUES (?, 1, ?)",
            (name, _now()),
        )
        return int(cur.lastrowid)


def set_project_active(project_id: int, active: bool) -> None:
    if using_supabase():
        _sb().table("projects").update({"active": bool(active)}).eq(
            "id", project_id
        ).execute()
        return

    with get_conn() as conn:
        conn.execute(
            "UPDATE projects SET active = ? WHERE id = ?",
            (1 if active else 0, project_id),
        )


# --- Entries ---


def add_entry(
    entry_date: date | str,
    worker_id: int,
    project_id: int,
    weather: str = "",
    hours_worked: float = 0.0,
    work_done: str = "",
    crew_notes: str = "",
    materials_notes: str = "",
    issues_delays: str = "",
    safety_notes: str = "",
) -> int:
    entry_date_s = _as_date_str(entry_date)
    payload = {
        "entry_date": entry_date_s,
        "worker_id": int(worker_id),
        "project_id": int(project_id),
        "weather": weather.strip(),
        "hours_worked": float(hours_worked),
        "work_done": work_done.strip(),
        "crew_notes": crew_notes.strip(),
        "materials_notes": materials_notes.strip(),
        "issues_delays": issues_delays.strip(),
        "safety_notes": safety_notes.strip(),
    }

    if using_supabase():
        now = datetime.utcnow().isoformat() + "Z"
        payload["created_at"] = now
        payload["updated_at"] = now
        resp = _sb().table("entries").insert(payload).execute()
        if not resp.data:
            raise RuntimeError("Failed to save entry in Supabase")
        return int(resp.data[0]["id"])

    now = _now()
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO entries (
                entry_date, worker_id, project_id, weather, hours_worked,
                work_done, crew_notes, materials_notes, issues_delays,
                safety_notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry_date_s,
                worker_id,
                project_id,
                payload["weather"],
                payload["hours_worked"],
                payload["work_done"],
                payload["crew_notes"],
                payload["materials_notes"],
                payload["issues_delays"],
                payload["safety_notes"],
                now,
                now,
            ),
        )
        return int(cur.lastrowid)


def update_entry(
    entry_id: int,
    entry_date: date | str,
    worker_id: int,
    project_id: int,
    weather: str = "",
    hours_worked: float = 0.0,
    work_done: str = "",
    crew_notes: str = "",
    materials_notes: str = "",
    issues_delays: str = "",
    safety_notes: str = "",
) -> None:
    entry_date_s = _as_date_str(entry_date)
    payload = {
        "entry_date": entry_date_s,
        "worker_id": int(worker_id),
        "project_id": int(project_id),
        "weather": weather.strip(),
        "hours_worked": float(hours_worked),
        "work_done": work_done.strip(),
        "crew_notes": crew_notes.strip(),
        "materials_notes": materials_notes.strip(),
        "issues_delays": issues_delays.strip(),
        "safety_notes": safety_notes.strip(),
        "updated_at": datetime.utcnow().isoformat() + "Z"
        if using_supabase()
        else _now(),
    }

    if using_supabase():
        _sb().table("entries").update(payload).eq("id", entry_id).execute()
        return

    with get_conn() as conn:
        conn.execute(
            """
            UPDATE entries SET
                entry_date = ?, worker_id = ?, project_id = ?, weather = ?,
                hours_worked = ?, work_done = ?, crew_notes = ?,
                materials_notes = ?, issues_delays = ?, safety_notes = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                entry_date_s,
                worker_id,
                project_id,
                payload["weather"],
                payload["hours_worked"],
                payload["work_done"],
                payload["crew_notes"],
                payload["materials_notes"],
                payload["issues_delays"],
                payload["safety_notes"],
                payload["updated_at"],
                entry_id,
            ),
        )


def delete_entry(entry_id: int) -> None:
    if using_supabase():
        _sb().table("entries").delete().eq("id", entry_id).execute()
        return

    with get_conn() as conn:
        conn.execute("DELETE FROM entries WHERE id = ?", (entry_id,))


def get_entry(entry_id: int) -> Optional[dict[str, Any]]:
    if using_supabase():
        resp = (
            _sb()
            .table("entries")
            .select("*, workers(name), projects(name)")
            .eq("id", entry_id)
            .limit(1)
            .execute()
        )
        if not resp.data:
            return None
        return _flatten_entry(resp.data[0])

    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT e.*, w.name AS worker_name, p.name AS project_name
            FROM entries e
            JOIN workers w ON w.id = e.worker_id
            JOIN projects p ON p.id = e.project_id
            WHERE e.id = ?
            """,
            (entry_id,),
        ).fetchone()
        return dict(row) if row else None


def list_entries(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    worker_id: Optional[int] = None,
    project_id: Optional[int] = None,
) -> list[dict[str, Any]]:
    if using_supabase():
        q = (
            _sb()
            .table("entries")
            .select("*, workers(name), projects(name)")
            .order("entry_date", desc=True)
            .order("id", desc=True)
        )
        if date_from:
            q = q.gte("entry_date", date_from)
        if date_to:
            q = q.lte("entry_date", date_to)
        if worker_id:
            q = q.eq("worker_id", worker_id)
        if project_id:
            q = q.eq("project_id", project_id)
        resp = q.execute()
        return [_flatten_entry(r) for r in (resp.data or [])]

    query = """
        SELECT e.*, w.name AS worker_name, p.name AS project_name
        FROM entries e
        JOIN workers w ON w.id = e.worker_id
        JOIN projects p ON p.id = e.project_id
        WHERE 1=1
    """
    params: list[Any] = []
    if date_from:
        query += " AND e.entry_date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND e.entry_date <= ?"
        params.append(date_to)
    if worker_id:
        query += " AND e.worker_id = ?"
        params.append(worker_id)
    if project_id:
        query += " AND e.project_id = ?"
        params.append(project_id)
    query += " ORDER BY e.entry_date DESC, e.id DESC"

    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def entry_stats(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    worker_id: Optional[int] = None,
    project_id: Optional[int] = None,
) -> dict[str, Any]:
    entries = list_entries(date_from, date_to, worker_id, project_id)
    total_hours = sum(float(e["hours_worked"] or 0) for e in entries)
    workers = {e.get("worker_name") for e in entries}
    projects = {e.get("project_name") for e in entries}
    return {
        "count": len(entries),
        "total_hours": total_hours,
        "worker_count": len(workers),
        "project_count": len(projects),
    }
