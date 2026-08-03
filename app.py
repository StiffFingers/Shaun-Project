"""In-Spec Team Work Journal — daily logs for a small crew + Excel export."""

from __future__ import annotations

import base64
from datetime import date, datetime, timedelta
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

import auth
import db
from export import build_excel

ASSETS_DIR = Path(__file__).parent / "assets"
LOGO_PATH = ASSETS_DIR / "in-spec-logo.png"
# 2-frame thumbs-up GIF; overlay lasts ~1.5s then auto-dismisses
SHAUN_CELEBRATE_GIF = ASSETS_DIR / "shaun_celebrate.gif"
SHAUN_CELEBRATE_FALLBACK = ASSETS_DIR / "shaun_celebrate_still.png"

# How long the pop-up stays on screen (ms)
CELEBRATION_MS = 1500

st.set_page_config(
    page_title="In-Spec Team Work Journal",
    page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

WEATHER_OPTIONS = [
    "Clear / Sunny",
    "Partly Cloudy",
    "Overcast",
    "Light Rain",
    "Heavy Rain",
    "Snow",
    "Windy",
    "Extreme Heat",
    "Extreme Cold",
    "Other / Mixed",
]


def render_header(title: str, caption: str | None = None) -> None:
    """Company logo + page heading (replaces crane emoji)."""
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=300)
    st.title(title)
    if caption:
        st.caption(caption)


def celebrate_entry_saved() -> None:
    """Pop-up 2-frame Shaun thumbs-up GIF (~1.5s), then auto-dismiss like balloons."""
    media = SHAUN_CELEBRATE_GIF if SHAUN_CELEBRATE_GIF.exists() else SHAUN_CELEBRATE_FALLBACK
    if not media.exists():
        return

    raw = media.read_bytes()
    b64 = base64.b64encode(raw).decode("ascii")
    suffix = media.suffix.lower()
    mime = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(suffix, "image/png")
    duration_ms = CELEBRATION_MS

    # Inject into parent page so it covers the app and removes itself (balloons-style).
    # Falls back to an in-component overlay if parent access is blocked.
    components.html(
        f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<style>
  html, body {{ margin: 0; padding: 0; background: transparent; overflow: hidden; }}
</style>
</head>
<body>
<script>
(function () {{
  const DURATION = {duration_ms};
  const src = "data:{mime};base64,{b64}";

  function buildOverlay(doc) {{
    const existing = doc.getElementById("shaun-celebration-overlay");
    if (existing) existing.remove();

    const style = doc.createElement("style");
    style.id = "shaun-celebration-style";
    style.textContent = `
      @keyframes shaunCelebInOut {{
        0%   {{ opacity: 0; transform: scale(0.25) translateY(50px); }}
        12%  {{ opacity: 1; transform: scale(1.08) translateY(0); }}
        22%  {{ transform: scale(1) translateY(0); }}
        78%  {{ opacity: 1; transform: scale(1) translateY(0); }}
        100% {{ opacity: 0; transform: scale(0.9) translateY(-24px); }}
      }}
      #shaun-celebration-overlay {{
        position: fixed !important;
        inset: 0 !important;
        z-index: 2147483646 !important;
        display: flex !important;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        background: rgba(10, 25, 40, 0.42);
        animation: shaunCelebInOut ${{DURATION}}ms ease-in-out forwards;
        pointer-events: none !important;
        font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
      }}
      #shaun-celebration-overlay img {{
        width: min(300px, 72vw);
        height: auto;
        border-radius: 18px;
        box-shadow: 0 16px 48px rgba(0,0,0,0.4);
        background: #fff;
      }}
      #shaun-celebration-overlay .shaun-caption {{
        margin-top: 14px;
        color: #fff;
        font-size: 1.2rem;
        font-weight: 650;
        text-shadow: 0 2px 10px rgba(0,0,0,0.55);
        text-align: center;
      }}
    `;

    const oldStyle = doc.getElementById("shaun-celebration-style");
    if (oldStyle) oldStyle.remove();
    doc.head.appendChild(style);

    const overlay = doc.createElement("div");
    overlay.id = "shaun-celebration-overlay";
    overlay.innerHTML = `
      <img src="${{src}}" alt="Shaun thumbs up" />
      <div class="shaun-caption">👍 Nice work — entry saved!</div>
    `;
    doc.body.appendChild(overlay);

    setTimeout(function () {{
      const el = doc.getElementById("shaun-celebration-overlay");
      if (el) el.remove();
      const st = doc.getElementById("shaun-celebration-style");
      if (st) st.remove();
    }}, DURATION + 80);
  }}

  try {{
    buildOverlay(window.parent.document);
  }} catch (e) {{
    buildOverlay(document);
  }}
}})();
</script>
</body>
</html>
        """,
        height=1,
        width=1,
    )


def bootstrap() -> tuple[bool, str]:
    """
    Initialize storage. Returns (ok, error_message).
    Runs the Supabase health check + seed only once per browser session
    so later clicks/reruns stay fast.
    """
    if st.session_state.get("_db_bootstrapped_ok"):
        return True, ""
    if st.session_state.get("_db_bootstrapped_err"):
        return False, st.session_state["_db_bootstrapped_err"]

    try:
        if db.using_supabase():
            ok, message = db.check_supabase()
            if not ok:
                st.session_state["_db_bootstrapped_err"] = message
                return False, message
        db.init_db()
        db.seed_defaults()
        st.session_state["_db_bootstrapped_ok"] = True
        st.session_state.pop("_db_bootstrapped_err", None)
        return True, ""
    except Exception as exc:
        message = (
            f"Database startup failed: {exc}\n\n"
            "If you just added Supabase secrets, confirm the URL and "
            "**service_role** key, and that you ran `supabase_schema.sql`."
        )
        st.session_state["_db_bootstrapped_err"] = message
        return False, message


@st.cache_data(ttl=45, show_spinner=False)
def _cached_workers(active_only: bool) -> list[dict]:
    """Short cache — avoids refetching crew on every widget interaction."""
    return db.list_workers(active_only=active_only)


@st.cache_data(ttl=45, show_spinner=False)
def _cached_projects(active_only: bool) -> list[dict]:
    return db.list_projects(active_only=active_only)


def _clear_crew_cache() -> None:
    _cached_workers.clear()
    _cached_projects.clear()


def _worker_options(active_only: bool = True) -> dict[str, int]:
    return {w["name"]: w["id"] for w in _cached_workers(active_only=active_only)}


def _project_options(active_only: bool = True) -> dict[str, int]:
    return {p["name"]: p["id"] for p in _cached_projects(active_only=active_only)}


def _id_to_name(options: dict[str, int], target_id: int) -> str | None:
    for name, oid in options.items():
        if oid == target_id:
            return name
    return None


def page_new_entry() -> None:
    st.caption("Fill this out at the end of the shift — only a few fields are required.")

    workers = _worker_options()
    projects = _project_options()

    if not workers:
        st.warning("Add at least one worker in **Crew & Projects** before logging.")
        return
    if not projects:
        st.warning("Add at least one project in **Crew & Projects** before logging.")
        return

    with st.form("new_entry", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            entry_date = st.date_input("Date", value=date.today())
        with c2:
            worker_name = st.selectbox("Worker", list(workers.keys()))
        with c3:
            project_name = st.selectbox("Project / job site", list(projects.keys()))

        c4, c5 = st.columns(2)
        with c4:
            weather = st.selectbox("Weather", WEATHER_OPTIONS)
        with c5:
            hours = st.number_input(
                "Hours worked",
                min_value=0.0,
                max_value=24.0,
                value=8.0,
                step=0.25,
            )

        work_done = st.text_area(
            "Work performed *",
            placeholder="What did you do today? e.g. Formed footings on north wall, poured slab section B…",
            height=120,
        )
        crew_notes = st.text_area(
            "Crew notes",
            placeholder="Who was on site, subcontractors, headcount…",
            height=80,
        )
        materials_notes = st.text_area(
            "Materials",
            placeholder="Deliveries, materials used, shortages…",
            height=80,
        )
        issues = st.text_area(
            "Issues / delays",
            placeholder="Weather delays, missing materials, change orders, access problems…",
            height=80,
        )
        safety = st.text_area(
            "Safety notes",
            placeholder="Incidents, near misses, toolbox talk topics, PPE issues…",
            height=80,
        )

        submitted = st.form_submit_button("Save entry", type="primary", use_container_width=True)

    if submitted:
        if not work_done.strip():
            st.error("Please describe the work performed.")
            return
        entry_id = db.add_entry(
            entry_date=entry_date,
            worker_id=workers[worker_name],
            project_id=projects[project_name],
            weather=weather,
            hours_worked=hours,
            work_done=work_done,
            crew_notes=crew_notes,
            materials_notes=materials_notes,
            issues_delays=issues,
            safety_notes=safety,
        )
        st.success(f"Saved entry #{entry_id} for {worker_name} on {entry_date.isoformat()}.")
        celebrate_entry_saved()


def page_journal() -> None:
    workers = _worker_options(active_only=False)
    projects = _project_options(active_only=False)

    with st.expander("Filters", expanded=True):
        f1, f2, f3, f4 = st.columns(4)
        with f1:
            date_from = st.date_input(
                "From",
                value=date.today() - timedelta(days=30),
                key="filter_from",
            )
        with f2:
            date_to = st.date_input("To", value=date.today(), key="filter_to")
        with f3:
            worker_filter = st.selectbox(
                "Worker",
                ["All workers"] + list(workers.keys()),
                key="filter_worker",
            )
        with f4:
            project_filter = st.selectbox(
                "Project",
                ["All projects"] + list(projects.keys()),
                key="filter_project",
            )

    worker_id = None if worker_filter == "All workers" else workers.get(worker_filter)
    project_id = None if project_filter == "All projects" else projects.get(project_filter)

    entries = db.list_entries(
        date_from=date_from.isoformat(),
        date_to=date_to.isoformat(),
        worker_id=worker_id,
        project_id=project_id,
    )
    stats = db.entry_stats(
        date_from=date_from.isoformat(),
        date_to=date_to.isoformat(),
        worker_id=worker_id,
        project_id=project_id,
    )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Entries", stats["count"])
    m2.metric("Total hours", f"{stats['total_hours']:.1f}")
    m3.metric("Workers", stats["worker_count"])
    m4.metric("Projects", stats["project_count"])

    if not entries:
        st.info("No entries match these filters.")
        return

    for entry in entries:
        with st.container(border=True):
            top_l, top_r = st.columns([4, 1])
            with top_l:
                st.markdown(
                    f"**#{entry['id']} · {entry['entry_date']}** — "
                    f"{entry['worker_name']} @ **{entry['project_name']}** · "
                    f"{entry['hours_worked']}h · {entry['weather'] or '—'}"
                )
            with top_r:
                action = st.selectbox(
                    "Action",
                    ["", "Edit", "Delete"],
                    key=f"action_{entry['id']}",
                    label_visibility="collapsed",
                )

            st.write(entry["work_done"] or "_(no work description)_")

            details = []
            if entry["crew_notes"]:
                details.append(f"**Crew:** {entry['crew_notes']}")
            if entry["materials_notes"]:
                details.append(f"**Materials:** {entry['materials_notes']}")
            if entry["issues_delays"]:
                details.append(f"**Issues:** {entry['issues_delays']}")
            if entry["safety_notes"]:
                details.append(f"**Safety:** {entry['safety_notes']}")
            if details:
                st.markdown("  \n".join(details))

            if action == "Edit":
                _edit_entry_form(entry, workers, projects)
            elif action == "Delete":
                if st.button(
                    f"Confirm delete entry #{entry['id']}",
                    key=f"del_{entry['id']}",
                    type="primary",
                ):
                    db.delete_entry(entry["id"])
                    st.success(f"Deleted entry #{entry['id']}.")
                    st.rerun()


def _edit_entry_form(
    entry: dict,
    workers: dict[str, int],
    projects: dict[str, int],
) -> None:
    st.markdown("---")
    st.markdown(f"#### Edit entry #{entry['id']}")

    # Include inactive names if needed so existing links still show
    active_workers = _worker_options(active_only=True)
    active_projects = _project_options(active_only=True)
    # Merge so current selection always available
    all_workers = {**workers, **active_workers}
    all_projects = {**projects, **active_projects}

    worker_names = list(all_workers.keys())
    project_names = list(all_projects.keys())
    current_worker = entry["worker_name"]
    current_project = entry["project_name"]
    if current_worker not in worker_names:
        worker_names.insert(0, current_worker)
        all_workers[current_worker] = entry["worker_id"]
    if current_project not in project_names:
        project_names.insert(0, current_project)
        all_projects[current_project] = entry["project_id"]

    with st.form(f"edit_{entry['id']}"):
        c1, c2, c3 = st.columns(3)
        with c1:
            entry_date = st.date_input(
                "Date",
                value=date.fromisoformat(entry["entry_date"]),
                key=f"ed_date_{entry['id']}",
            )
        with c2:
            worker_name = st.selectbox(
                "Worker",
                worker_names,
                index=worker_names.index(current_worker),
                key=f"ed_worker_{entry['id']}",
            )
        with c3:
            project_name = st.selectbox(
                "Project",
                project_names,
                index=project_names.index(current_project),
                key=f"ed_project_{entry['id']}",
            )

        c4, c5 = st.columns(2)
        with c4:
            weather_idx = (
                WEATHER_OPTIONS.index(entry["weather"])
                if entry["weather"] in WEATHER_OPTIONS
                else 0
            )
            weather = st.selectbox(
                "Weather",
                WEATHER_OPTIONS,
                index=weather_idx,
                key=f"ed_weather_{entry['id']}",
            )
        with c5:
            hours = st.number_input(
                "Hours worked",
                min_value=0.0,
                max_value=24.0,
                value=float(entry["hours_worked"] or 0),
                step=0.25,
                key=f"ed_hours_{entry['id']}",
            )

        work_done = st.text_area(
            "Work performed",
            value=entry["work_done"] or "",
            height=100,
            key=f"ed_work_{entry['id']}",
        )
        crew_notes = st.text_area(
            "Crew notes",
            value=entry["crew_notes"] or "",
            height=70,
            key=f"ed_crew_{entry['id']}",
        )
        materials_notes = st.text_area(
            "Materials",
            value=entry["materials_notes"] or "",
            height=70,
            key=f"ed_mat_{entry['id']}",
        )
        issues = st.text_area(
            "Issues / delays",
            value=entry["issues_delays"] or "",
            height=70,
            key=f"ed_iss_{entry['id']}",
        )
        safety = st.text_area(
            "Safety notes",
            value=entry["safety_notes"] or "",
            height=70,
            key=f"ed_safe_{entry['id']}",
        )

        saved = st.form_submit_button("Update entry", type="primary")

    if saved:
        if not work_done.strip():
            st.error("Work performed cannot be empty.")
            return
        db.update_entry(
            entry_id=entry["id"],
            entry_date=entry_date,
            worker_id=all_workers[worker_name],
            project_id=all_projects[project_name],
            weather=weather,
            hours_worked=hours,
            work_done=work_done,
            crew_notes=crew_notes,
            materials_notes=materials_notes,
            issues_delays=issues,
            safety_notes=safety,
        )
        st.success(f"Updated entry #{entry['id']}.")
        st.rerun()


def page_export() -> None:
    st.caption(
        "Download one spreadsheet with all matching entries plus summary sheets by worker and project."
    )

    workers = _worker_options(active_only=False)
    projects = _project_options(active_only=False)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        date_from = st.date_input(
            "From",
            value=date.today().replace(day=1),
            key="export_from",
        )
    with c2:
        date_to = st.date_input("To", value=date.today(), key="export_to")
    with c3:
        worker_filter = st.selectbox(
            "Worker",
            ["All workers"] + list(workers.keys()),
            key="export_worker",
        )
    with c4:
        project_filter = st.selectbox(
            "Project",
            ["All projects"] + list(projects.keys()),
            key="export_project",
        )

    worker_id = None if worker_filter == "All workers" else workers.get(worker_filter)
    project_id = None if project_filter == "All projects" else projects.get(project_filter)

    entries = db.list_entries(
        date_from=date_from.isoformat(),
        date_to=date_to.isoformat(),
        worker_id=worker_id,
        project_id=project_id,
    )
    stats = db.entry_stats(
        date_from=date_from.isoformat(),
        date_to=date_to.isoformat(),
        worker_id=worker_id,
        project_id=project_id,
    )

    st.write(
        f"**{stats['count']}** entries · **{stats['total_hours']:.1f}** hours · "
        f"{stats['worker_count']} workers · {stats['project_count']} projects"
    )

    filters_summary = (
        f"Date {date_from.isoformat()} to {date_to.isoformat()}; "
        f"Worker: {worker_filter}; Project: {project_filter}"
    )

    if entries:
        # Preview table
        preview_rows = [
            {
                "Date": e["entry_date"],
                "Worker": e["worker_name"],
                "Project": e["project_name"],
                "Hours": e["hours_worked"],
                "Weather": e["weather"],
                "Work performed": (e["work_done"] or "")[:120],
            }
            for e in sorted(entries, key=lambda x: (x["entry_date"], x["id"]))
        ]
        st.dataframe(preview_rows, use_container_width=True, hide_index=True)

        xlsx_bytes = build_excel(entries, filters_summary=filters_summary)
        filename = f"work_journal_{date_from.isoformat()}_to_{date_to.isoformat()}.xlsx"
        st.download_button(
            label="Download Excel spreadsheet",
            data=xlsx_bytes,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True,
        )
        st.info(
            "The file includes four sheets: **Export Info**, **All Entries**, "
            "**By Worker**, and **By Project**."
        )
    else:
        st.warning("Nothing to export for these filters.")


def page_crew() -> None:
    st.caption(
        "Deactivate people/sites that are done. **Delete** is only allowed when "
        "there are no linked journal entries (protects history)."
    )
    left, right = st.columns(2)

    with left:
        st.markdown("### Workers")
        with st.form("add_worker"):
            name = st.text_input("New worker name", placeholder="e.g. Chris Morgan")
            if st.form_submit_button("Add worker", use_container_width=True):
                try:
                    db.add_worker(name)
                    _clear_crew_cache()
                    st.success(f"Added worker: {name.strip()}")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

        for w in _cached_workers(active_only=False):
            entry_count = db.count_entries_for_worker(w["id"])
            cols = st.columns([3, 1, 1, 1])
            label = w["name"] + ("" if w["active"] else " _(inactive)_")
            if entry_count:
                label += f" · {entry_count} entr{'y' if entry_count == 1 else 'ies'}"
            cols[0].write(label)

            if w["active"]:
                if cols[1].button("Deactivate", key=f"w_off_{w['id']}"):
                    db.set_worker_active(w["id"], False)
                    _clear_crew_cache()
                    st.rerun()
            else:
                if cols[1].button("Activate", key=f"w_on_{w['id']}"):
                    db.set_worker_active(w["id"], True)
                    _clear_crew_cache()
                    st.rerun()

            if entry_count == 0:
                if cols[2].button("Delete", key=f"w_del_{w['id']}"):
                    try:
                        db.delete_worker(w["id"])
                        _clear_crew_cache()
                        st.success(f"Deleted worker: {w['name']}")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))
            else:
                cols[2].caption("In use")

    with right:
        st.markdown("### Projects / job sites")
        with st.form("add_project"):
            name = st.text_input("New project name", placeholder="e.g. Bridge Deck Phase 2")
            if st.form_submit_button("Add project", use_container_width=True):
                try:
                    db.add_project(name)
                    _clear_crew_cache()
                    st.success(f"Added project: {name.strip()}")
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))

        for p in _cached_projects(active_only=False):
            entry_count = db.count_entries_for_project(p["id"])
            cols = st.columns([3, 1, 1, 1])
            label = p["name"] + ("" if p["active"] else " _(inactive)_")
            if entry_count:
                label += f" · {entry_count} entr{'y' if entry_count == 1 else 'ies'}"
            cols[0].write(label)

            if p["active"]:
                if cols[1].button("Deactivate", key=f"p_off_{p['id']}"):
                    db.set_project_active(p["id"], False)
                    _clear_crew_cache()
                    st.rerun()
            else:
                if cols[1].button("Activate", key=f"p_on_{p['id']}"):
                    db.set_project_active(p["id"], True)
                    _clear_crew_cache()
                    st.rerun()

            if entry_count == 0:
                if cols[2].button("Delete", key=f"p_del_{p['id']}"):
                    try:
                        db.delete_project(p["id"])
                        _clear_crew_cache()
                        st.success(f"Deleted project: {p['name']}")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))
            else:
                cols[2].caption("In use")


def main() -> None:
    ok, db_error = bootstrap()

    # Gate the whole app behind email/password when secrets are configured
    if not auth.require_login():
        return

    if not ok:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), width=300)
        st.title("Database setup needed")
        st.error(db_error)
        st.markdown(
            """
### Fix Supabase (checklist)

1. Open [Supabase](https://supabase.com/dashboard) → your project  
2. **SQL Editor** → run the full contents of `supabase_schema.sql` (from the GitHub repo) once  
3. **Project Settings → API** copy:
   - **Project URL** (real URL, not `xxxxx`)
   - **`service_role`** key (click Reveal) — **not** the `anon` key  
4. Streamlit → **Manage app → Settings → Secrets** — use real values:

```toml
[supabase]
url = "https://YOURREALREF.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...."
```

5. Save secrets and wait for the app to reboot  
6. Refresh this page  

**Do not** leave placeholders like `xxxxx` or `PASTE_SERVICE_ROLE_KEY_HERE` — those break the app.
            """
        )
        return

    page = st.sidebar.radio(
        "Navigate",
        [
            "New entry",
            "Journal",
            "Excel export",
            "Crew & projects",
        ],
        index=0,
    )

    auth.render_user_sidebar()

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        f"**Today:** {date.today().strftime('%a, %b %d, %Y')}  \n"
        f"**Data:** {db.storage_label()}"
    )
    if not db.using_supabase():
        st.sidebar.warning(
            "Supabase is not configured with real credentials. "
            "On Streamlit Cloud, data can reset until you add a real "
            "`[supabase]` url + service_role key."
        )

    try:
        if page == "New entry":
            render_header(
                "In-Spec Team Work Journal Entry",
                "Daily site logs for your crew — then export everything to Excel.",
            )
            page_new_entry()
        elif page == "Journal":
            render_header(
                "Journal",
                "Browse, filter, edit, or delete log entries.",
            )
            page_journal()
        elif page == "Excel export":
            render_header(
                "Excel export",
                "Download a spreadsheet overview of matching entries.",
            )
            page_export()
        else:
            render_header(
                "Crew & projects",
                "Manage who can be selected on log entries and which job sites appear.",
            )
            page_crew()
    except Exception as exc:
        st.error(f"Something went wrong talking to the database: {exc}")
        st.info(
            "If this started after adding Supabase, double-check the service_role key "
            "and that tables exist (run supabase_schema.sql)."
        )


if __name__ == "__main__":
    main()
