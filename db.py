"""SQLite storage for construction work journal entries."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
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


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def seed_defaults() -> None:
    """Add a few starter workers/projects if the DB is empty."""
    with get_conn() as conn:
        worker_count = conn.execute("SELECT COUNT(*) FROM workers").fetchone()[0]
        project_count = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        now = _now()
        if worker_count == 0:
            for name in ("Alex Rivera", "Jordan Lee", "Sam Patel"):
                conn.execute(
                    "INSERT INTO workers (name, active, created_at) VALUES (?, 1, ?)",
                    (name, now),
                )
        if project_count == 0:
            for name in ("Main Site A", "Warehouse Renovation", "Road Extension"):
                conn.execute(
                    "INSERT INTO projects (name, active, created_at) VALUES (?, 1, ?)",
                    (name, now),
                )


# --- Workers ---


def list_workers(active_only: bool = True) -> list[dict[str, Any]]:
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
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO workers (name, active, created_at) VALUES (?, 1, ?)",
            (name, _now()),
        )
        return int(cur.lastrowid)


def set_worker_active(worker_id: int, active: bool) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE workers SET active = ? WHERE id = ?",
            (1 if active else 0, worker_id),
        )


# --- Projects ---


def list_projects(active_only: bool = True) -> list[dict[str, Any]]:
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
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO projects (name, active, created_at) VALUES (?, 1, ?)",
            (name, _now()),
        )
        return int(cur.lastrowid)


def set_project_active(project_id: int, active: bool) -> None:
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
    if isinstance(entry_date, date):
        entry_date = entry_date.isoformat()
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
                entry_date,
                worker_id,
                project_id,
                weather.strip(),
                float(hours_worked),
                work_done.strip(),
                crew_notes.strip(),
                materials_notes.strip(),
                issues_delays.strip(),
                safety_notes.strip(),
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
    if isinstance(entry_date, date):
        entry_date = entry_date.isoformat()
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
                entry_date,
                worker_id,
                project_id,
                weather.strip(),
                float(hours_worked),
                work_done.strip(),
                crew_notes.strip(),
                materials_notes.strip(),
                issues_delays.strip(),
                safety_notes.strip(),
                _now(),
                entry_id,
            ),
        )


def delete_entry(entry_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM entries WHERE id = ?", (entry_id,))


def get_entry(entry_id: int) -> Optional[dict[str, Any]]:
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
    workers = {e["worker_name"] for e in entries}
    projects = {e["project_name"] for e in entries}
    return {
        "count": len(entries),
        "total_hours": total_hours,
        "worker_count": len(workers),
        "project_count": len(projects),
    }
