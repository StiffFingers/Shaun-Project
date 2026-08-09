"""Journal storage: Supabase (Postgres) when configured, else local SQLite.

Supabase keeps data permanent on Streamlit Cloud.
Local SQLite is used only when [supabase] secrets are missing (dev/offline).
"""

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
    logged_by_worker_id INTEGER,
    entry_group_id TEXT,
    weather TEXT NOT NULL DEFAULT '',
    temperature_c REAL,
    start_time TEXT NOT NULL DEFAULT '',
    finish_time TEXT NOT NULL DEFAULT '',
    break_minutes INTEGER NOT NULL DEFAULT 0,
    hours_worked REAL NOT NULL DEFAULT 0,
    work_done TEXT NOT NULL DEFAULT '',
    crew_notes TEXT NOT NULL DEFAULT '',
    materials_notes TEXT NOT NULL DEFAULT '',
    issues_delays TEXT NOT NULL DEFAULT '',
    safety_notes TEXT NOT NULL DEFAULT '',
    action_follow_up TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (worker_id) REFERENCES workers(id),
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (logged_by_worker_id) REFERENCES workers(id)
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


_PLACEHOLDER_MARKERS = (
    "xxxxx",
    "your_project",
    "your-project",
    "paste_",
    "your_service",
    "example.supabase",
    "replace_me",
    "changeme",
)


def _looks_like_placeholder(value: str) -> bool:
    lower = value.strip().lower()
    if not lower:
        return True
    return any(m in lower for m in _PLACEHOLDER_MARKERS)


def _supabase_config() -> Optional[dict[str, str]]:
    """Return url/key only when secrets look real (not template placeholders)."""
    try:
        import streamlit as st

        cfg = st.secrets.get("supabase", None)
        if not cfg:
            return None
        url = str(cfg.get("url", "")).strip().rstrip("/")
        key = str(cfg.get("key", "")).strip()
        if not url or not key:
            return None
        # Ignore copy-paste template values so the app does not crash
        if _looks_like_placeholder(url) or _looks_like_placeholder(key):
            return None
        if "supabase.co" not in url and "supabase.in" not in url:
            # Still allow custom domains, but require https
            if not url.startswith("https://"):
                return None
        if len(key) < 40:
            # Real service_role JWTs are long
            return None
        return {"url": url, "key": key}
    except Exception:
        pass
    return None


def using_supabase() -> bool:
    return _supabase_config() is not None


def storage_label() -> str:
    return (
        "Supabase (cloud, permanent)"
        if using_supabase()
        else "Local SQLite (resets on Streamlit Cloud)"
    )


def _supabase_client():
    from supabase import create_client

    cfg = _supabase_config()
    if not cfg:
        raise RuntimeError("Supabase is not configured")
    return create_client(cfg["url"], cfg["key"])


def _sb():
    if not hasattr(_sb, "_client") or _sb._client is None:
        _sb._client = _supabase_client()
    return _sb._client


_sb._client = None  # type: ignore[attr-defined]


def reset_supabase_client() -> None:
    _sb._client = None  # type: ignore[attr-defined]


def check_supabase() -> tuple[bool, str]:
    """
    Test Supabase connectivity and that required tables exist.
    Returns (ok, message). Reuses the shared client (no forced reconnect).
    """
    cfg = _supabase_config()
    if not cfg:
        # Distinguish missing vs placeholder
        try:
            import streamlit as st

            raw = st.secrets.get("supabase", None)
            if raw and (raw.get("url") or raw.get("key")):
                return (
                    False,
                    "Supabase secrets look incomplete or still use placeholder text "
                    "(e.g. xxxxx or PASTE_...). Use your real Project URL and "
                    "service_role key from Supabase → Project Settings → API.",
                )
        except Exception:
            pass
        return False, "Supabase is not configured in secrets."

    try:
        client = _sb()
        # Lightweight probe — fails clearly if table missing or key wrong
        client.table("workers").select("id").limit(1).execute()
        return True, "Connected to Supabase."
    except Exception as exc:
        reset_supabase_client()
        msg = str(exc)
        hint = (
            "Check: (1) Project URL is correct, "
            "(2) key is the **service_role** secret (not anon), "
            "(3) you ran supabase_schema.sql in the SQL Editor, "
            "(4) key is one line inside double quotes in Secrets."
        )
        return False, f"Supabase connection failed: {msg}\n\n{hint}"


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
    # PostgREST embed shapes (default or aliased)
    workers = out.pop("workers", None) or out.pop("worker", None) or {}
    projects = out.pop("projects", None) or out.pop("project", None) or {}
    logged_by = out.pop("logged_by", None) or {}
    if isinstance(workers, dict):
        out["worker_name"] = workers.get("name", "")
    if isinstance(projects, dict):
        out["project_name"] = projects.get("name", "")
    if isinstance(logged_by, dict):
        out["logged_by_name"] = logged_by.get("name") or ""
    else:
        out.setdefault("logged_by_name", "")
    if out.get("entry_date") is not None:
        out["entry_date"] = str(out["entry_date"])[:10]
    for key in ("created_at", "updated_at"):
        if out.get(key) is not None:
            out[key] = str(out[key])
    if out.get("hours_worked") is not None:
        out["hours_worked"] = float(out["hours_worked"])
    if out.get("temperature_c") is not None and out.get("temperature_c") != "":
        try:
            out["temperature_c"] = float(out["temperature_c"])
        except (TypeError, ValueError):
            pass
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
        # Schema / migrations are applied in the Supabase SQL Editor.
        return
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        cols = {
            r[1]
            for r in conn.execute("PRAGMA table_info(entries)").fetchall()
        }
        if "logged_by_worker_id" not in cols:
            conn.execute(
                "ALTER TABLE entries ADD COLUMN logged_by_worker_id INTEGER "
                "REFERENCES workers(id)"
            )
        if "action_follow_up" not in cols:
            conn.execute(
                "ALTER TABLE entries ADD COLUMN action_follow_up TEXT NOT NULL DEFAULT ''"
            )
        if "temperature_c" not in cols:
            conn.execute("ALTER TABLE entries ADD COLUMN temperature_c REAL")
        if "entry_group_id" not in cols:
            conn.execute("ALTER TABLE entries ADD COLUMN entry_group_id TEXT")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_entries_group ON entries(entry_group_id)"
            )
        if "start_time" not in cols:
            conn.execute("ALTER TABLE entries ADD COLUMN start_time TEXT NOT NULL DEFAULT ''")
        if "finish_time" not in cols:
            conn.execute("ALTER TABLE entries ADD COLUMN finish_time TEXT NOT NULL DEFAULT ''")
        if "break_minutes" not in cols:
            conn.execute(
                "ALTER TABLE entries ADD COLUMN break_minutes INTEGER NOT NULL DEFAULT 0"
            )


def _table_is_empty(table: str) -> bool:
    """Cheap emptiness check (1 row max) — avoids downloading full tables on every boot."""
    if using_supabase():
        resp = _sb().table(table).select("id").limit(1).execute()
        return not bool(resp.data)
    with get_conn() as conn:
        row = conn.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone()
        return row is None


def seed_defaults() -> None:
    """Add starter workers/projects if tables are empty (fast no-op when data exists)."""
    if _table_is_empty("workers"):
        for name in ("Alex Rivera", "Jordan Lee", "Sam Patel"):
            try:
                add_worker(name)
            except Exception:
                pass
    if _table_is_empty("projects"):
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


def count_entries_for_worker(worker_id: int) -> int:
    if using_supabase():
        resp = (
            _sb()
            .table("entries")
            .select("id", count="exact")
            .eq("worker_id", worker_id)
            .limit(1)
            .execute()
        )
        if resp.count is not None:
            return int(resp.count)
        return len(resp.data or [])

    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM entries WHERE worker_id = ?",
            (worker_id,),
        ).fetchone()
        return int(row[0] if row else 0)


def delete_worker(worker_id: int) -> None:
    """Hard-delete only when this worker has no journal entries."""
    n = count_entries_for_worker(worker_id)
    if n > 0:
        raise ValueError(
            f"Cannot delete: this worker has {n} log entr"
            f"{'y' if n == 1 else 'ies'}. Deactivate instead."
        )

    if using_supabase():
        _sb().table("workers").delete().eq("id", worker_id).execute()
        return

    with get_conn() as conn:
        conn.execute("DELETE FROM workers WHERE id = ?", (worker_id,))


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


def get_or_create_project(name: str) -> int:
    """Match existing job site by name (case-insensitive) or create a new active project."""
    name = name.strip()
    if not name:
        raise ValueError("Job site is required")
    for p in list_projects(active_only=False):
        if (p.get("name") or "").strip().lower() == name.lower():
            # Reactivate if it was inactive
            if not p.get("active"):
                set_project_active(int(p["id"]), True)
            return int(p["id"])
    return add_project(name)


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


def count_entries_for_project(project_id: int) -> int:
    if using_supabase():
        resp = (
            _sb()
            .table("entries")
            .select("id", count="exact")
            .eq("project_id", project_id)
            .limit(1)
            .execute()
        )
        if resp.count is not None:
            return int(resp.count)
        return len(resp.data or [])

    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM entries WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        return int(row[0] if row else 0)


def delete_project(project_id: int) -> None:
    """Hard-delete only when this project has no journal entries."""
    n = count_entries_for_project(project_id)
    if n > 0:
        raise ValueError(
            f"Cannot delete: this project has {n} log entr"
            f"{'y' if n == 1 else 'ies'}. Deactivate instead."
        )

    if using_supabase():
        _sb().table("projects").delete().eq("id", project_id).execute()
        return

    with get_conn() as conn:
        conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))


# --- Entries ---


def add_entry(
    entry_date: date | str,
    worker_id: int,
    project_id: int,
    weather: str = "",
    temperature_c: Optional[float] = None,
    hours_worked: float = 0.0,
    start_time: str = "",
    finish_time: str = "",
    break_minutes: int = 0,
    work_done: str = "",
    crew_notes: str = "",
    materials_notes: str = "",
    issues_delays: str = "",
    safety_notes: str = "",
    action_follow_up: str = "",
    logged_by_worker_id: Optional[int] = None,
    entry_group_id: Optional[str] = None,
) -> int:
    entry_date_s = _as_date_str(entry_date)
    temp_val: Optional[float]
    if temperature_c is None or temperature_c == "":
        temp_val = None
    else:
        temp_val = float(temperature_c)
    payload: dict[str, Any] = {
        "entry_date": entry_date_s,
        "worker_id": int(worker_id),
        "project_id": int(project_id),
        "weather": weather.strip(),
        "temperature_c": temp_val,
        "hours_worked": float(hours_worked),
        "start_time": (start_time or "").strip(),
        "finish_time": (finish_time or "").strip(),
        "break_minutes": int(break_minutes or 0),
        "work_done": work_done.strip(),
        "crew_notes": crew_notes.strip(),
        "materials_notes": materials_notes.strip(),
        "issues_delays": issues_delays.strip(),
        "safety_notes": safety_notes.strip(),
        "action_follow_up": action_follow_up.strip(),
    }
    if logged_by_worker_id is not None:
        payload["logged_by_worker_id"] = int(logged_by_worker_id)
    if entry_group_id:
        payload["entry_group_id"] = str(entry_group_id)

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
                entry_date, worker_id, project_id, logged_by_worker_id, entry_group_id,
                weather, temperature_c, start_time, finish_time, break_minutes, hours_worked,
                work_done, crew_notes, materials_notes, issues_delays, safety_notes,
                action_follow_up, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry_date_s,
                worker_id,
                project_id,
                int(logged_by_worker_id) if logged_by_worker_id is not None else None,
                str(entry_group_id) if entry_group_id else None,
                payload["weather"],
                temp_val,
                payload["start_time"],
                payload["finish_time"],
                payload["break_minutes"],
                payload["hours_worked"],
                payload["work_done"],
                payload["crew_notes"],
                payload["materials_notes"],
                payload["issues_delays"],
                payload["safety_notes"],
                payload["action_follow_up"],
                now,
                now,
            ),
        )
        return int(cur.lastrowid)


def add_entries_for_crew(
    entry_date: date | str,
    project_id: int,
    hours_by_worker_id: dict[int, Any],
    logged_by_worker_id: int,
    weather: str = "",
    temperature_c: Optional[float] = None,
    work_done: str = "",
    crew_notes: str = "",
    materials_notes: str = "",
    issues_delays: str = "",
    safety_notes: str = "",
    action_follow_up: str = "",
) -> list[int]:
    """Create one journal row per worker with hours > 0 (same entry_group_id).

    hours_by_worker_id values may be a float (legacy) or a dict with
    start_time, finish_time, break_minutes, hours_worked.
    """
    import uuid

    group_id = str(uuid.uuid4())
    ids: list[int] = []
    for worker_id, raw in hours_by_worker_id.items():
        start_time = ""
        finish_time = ""
        break_minutes = 0
        if isinstance(raw, dict):
            start_time = str(raw.get("start_time") or "")
            finish_time = str(raw.get("finish_time") or "")
            try:
                break_minutes = int(raw.get("break_minutes") or 0)
            except (TypeError, ValueError):
                break_minutes = 0
            try:
                h = float(raw.get("hours_worked") or 0)
            except (TypeError, ValueError):
                h = 0.0
        else:
            try:
                h = float(raw or 0)
            except (TypeError, ValueError):
                h = 0.0
        if h <= 0:
            continue
        ids.append(
            add_entry(
                entry_date=entry_date,
                worker_id=int(worker_id),
                project_id=project_id,
                weather=weather,
                temperature_c=temperature_c,
                hours_worked=h,
                start_time=start_time,
                finish_time=finish_time,
                break_minutes=break_minutes,
                work_done=work_done,
                crew_notes=crew_notes,
                materials_notes=materials_notes,
                issues_delays=issues_delays,
                safety_notes=safety_notes,
                action_follow_up=action_follow_up,
                logged_by_worker_id=logged_by_worker_id,
                entry_group_id=group_id,
            )
        )
    return ids


def update_entry(
    entry_id: int,
    entry_date: date | str,
    worker_id: int,
    project_id: int,
    weather: str = "",
    temperature_c: Optional[float] = None,
    hours_worked: float = 0.0,
    start_time: str = "",
    finish_time: str = "",
    break_minutes: int = 0,
    work_done: str = "",
    crew_notes: str = "",
    materials_notes: str = "",
    issues_delays: str = "",
    safety_notes: str = "",
    action_follow_up: str = "",
) -> None:
    entry_date_s = _as_date_str(entry_date)
    if temperature_c is None or temperature_c == "":
        temp_val = None
    else:
        temp_val = float(temperature_c)
    payload = {
        "entry_date": entry_date_s,
        "worker_id": int(worker_id),
        "project_id": int(project_id),
        "weather": weather.strip(),
        "temperature_c": temp_val,
        "hours_worked": float(hours_worked),
        "start_time": (start_time or "").strip(),
        "finish_time": (finish_time or "").strip(),
        "break_minutes": int(break_minutes or 0),
        "work_done": work_done.strip(),
        "crew_notes": crew_notes.strip(),
        "materials_notes": materials_notes.strip(),
        "issues_delays": issues_delays.strip(),
        "safety_notes": safety_notes.strip(),
        "action_follow_up": action_follow_up.strip(),
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
                temperature_c = ?, start_time = ?, finish_time = ?, break_minutes = ?,
                hours_worked = ?, work_done = ?, crew_notes = ?,
                materials_notes = ?, issues_delays = ?, safety_notes = ?,
                action_follow_up = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                entry_date_s,
                worker_id,
                project_id,
                payload["weather"],
                temp_val,
                payload["start_time"],
                payload["finish_time"],
                payload["break_minutes"],
                payload["hours_worked"],
                payload["work_done"],
                payload["crew_notes"],
                payload["materials_notes"],
                payload["issues_delays"],
                payload["safety_notes"],
                payload["action_follow_up"],
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


_ENTRY_SELECT_SB = (
    "*, "
    "worker:workers!worker_id(name), "
    "logged_by:workers!logged_by_worker_id(name), "
    "project:projects!project_id(name)"
)


def get_entry(entry_id: int) -> Optional[dict[str, Any]]:
    if using_supabase():
        try:
            resp = (
                _sb()
                .table("entries")
                .select(_ENTRY_SELECT_SB)
                .eq("id", entry_id)
                .limit(1)
                .execute()
            )
        except Exception:
            # Fallback if FK embed names differ before migration
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
            SELECT e.*, w.name AS worker_name, p.name AS project_name,
                   lb.name AS logged_by_name
            FROM entries e
            JOIN workers w ON w.id = e.worker_id
            JOIN projects p ON p.id = e.project_id
            LEFT JOIN workers lb ON lb.id = e.logged_by_worker_id
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
        try:
            q = (
                _sb()
                .table("entries")
                .select(_ENTRY_SELECT_SB)
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
        except Exception:
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
        SELECT e.*, w.name AS worker_name, p.name AS project_name,
               lb.name AS logged_by_name
        FROM entries e
        JOIN workers w ON w.id = e.worker_id
        JOIN projects p ON p.id = e.project_id
        LEFT JOIN workers lb ON lb.id = e.logged_by_worker_id
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


def group_journal_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse person-rows into one journal card per form submission (entry_group_id)."""
    from collections import OrderedDict

    buckets: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    for e in entries:
        gid = (e.get("entry_group_id") or "").strip() or f"solo-{e.get('id')}"
        if gid not in buckets:
            buckets[gid] = {
                "group_id": gid,
                "ids": [],
                "entry_date": e.get("entry_date"),
                "project_name": e.get("project_name"),
                "project_id": e.get("project_id"),
                "logged_by_name": e.get("logged_by_name") or "",
                "logged_by_worker_id": e.get("logged_by_worker_id"),
                "weather": e.get("weather") or "",
                "temperature_c": e.get("temperature_c"),
                "work_done": e.get("work_done") or "",
                "crew_notes": e.get("crew_notes") or "",
                "materials_notes": e.get("materials_notes") or "",
                "issues_delays": e.get("issues_delays") or "",
                "safety_notes": e.get("safety_notes") or "",
                "action_follow_up": e.get("action_follow_up") or "",
                "created_at": e.get("created_at") or "",
                "people": [],
                "total_hours": 0.0,
            }
        g = buckets[gid]
        try:
            hrs = float(e.get("hours_worked") or 0)
        except (TypeError, ValueError):
            hrs = 0.0
        g["ids"].append(int(e["id"]))
        g["people"].append(
            {
                "id": int(e["id"]),
                "worker_id": e.get("worker_id"),
                "worker_name": e.get("worker_name") or "",
                "hours_worked": hrs,
                "start_time": e.get("start_time") or "",
                "finish_time": e.get("finish_time") or "",
                "break_minutes": int(e.get("break_minutes") or 0),
            }
        )
        g["total_hours"] += hrs
        # Prefer earliest created_at for group stamp
        if (e.get("created_at") or "") < (g.get("created_at") or "z"):
            g["created_at"] = e.get("created_at") or g["created_at"]
    # Sort people by name
    for g in buckets.values():
        g["people"].sort(key=lambda p: (p.get("worker_name") or "").lower())
        # Primary id for display
        g["id"] = g["ids"][0] if g["ids"] else None
    return list(buckets.values())


def list_journal_groups(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    worker_id: Optional[int] = None,
    project_id: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Journals for display/PDF: one item per multi-person form submit."""
    # Load all person-rows in range (do not filter worker yet so groups stay complete)
    rows = list_entries(
        date_from=date_from,
        date_to=date_to,
        worker_id=None,
        project_id=project_id,
    )
    groups = group_journal_entries(rows)
    if worker_id:
        wid = int(worker_id)
        groups = [
            g
            for g in groups
            if any(int(p.get("worker_id") or 0) == wid for p in g.get("people") or [])
        ]
    return groups


def delete_entry_group(group: dict[str, Any]) -> None:
    for eid in group.get("ids") or []:
        delete_entry(int(eid))


def journal_group_stats(groups: list[dict[str, Any]]) -> dict[str, Any]:
    total_hours = sum(float(g.get("total_hours") or 0) for g in groups)
    workers: set[str] = set()
    projects: set[str] = set()
    for g in groups:
        for p in g.get("people") or []:
            if p.get("worker_name"):
                workers.add(p["worker_name"])
        if g.get("project_name"):
            projects.add(g["project_name"])
    return {
        "count": len(groups),
        "total_hours": total_hours,
        "worker_count": len(workers),
        "project_count": len(projects),
    }
