"""In-Spec Team Work Journal — daily logs for a small crew + Excel export."""

from __future__ import annotations

import base64
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st
import streamlit.components.v1 as components

import auth
import db
from export import build_excel
from pdf_entry import (
    build_entry_pdf,
    build_entries_pdf_zip,
    entry_pdf_filename,
    format_display_date,
)

# App “today” and default dates use Vancouver / Pacific time (not server UTC)
VANCOUVER_TZ = ZoneInfo("America/Vancouver")


def today_vancouver() -> date:
    """Current calendar date in America/Vancouver (handles PST/PDT)."""
    return datetime.now(VANCOUVER_TZ).date()

ASSETS_DIR = Path(__file__).parent / "assets"
LOGO_PATH = ASSETS_DIR / "in-spec-logo.png"
# Celebration pop-up (~2s): thumbs-up animation
SHAUN_CELEBRATE_MEDIA = ASSETS_DIR / "celebrate_thumbs_up.gif"
SHAUN_CELEBRATE_FALLBACK = ASSETS_DIR / "celebrate_thumbs_up.jpg"

# Total on-screen time for the celebration overlay (milliseconds)
CELEBRATION_MS = 2000

st.set_page_config(
    page_title="In-Spec Team Work Journal",
    page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

TEMPERATURE_C_OPTIONS = list(range(-5, 41))  # -5°C through 40°C

# 15-minute clock options from 6:00 AM through midnight; "—" = not on site
TIME_BLANK = "—"
TIME_OPTIONS = [TIME_BLANK] + [
    f"{h:02d}:{m:02d}"
    for h in range(6, 24)
    for m in (0, 15, 30, 45)
] + ["00:00"]  # midnight as end-of-day finish
# Lunch / break length in minutes (0–4 hours)
BREAK_MINUTE_OPTIONS = list(range(0, 241, 15))


def _calc_worked_hours(start: str, finish: str, break_minutes: int) -> float:
    """(finish - start) minus break, in hours. Supports overnight shifts."""
    if not start or not finish or start == TIME_BLANK or finish == TIME_BLANK:
        return 0.0
    try:
        sh, sm = map(int, start.split(":"))
        fh, fm = map(int, finish.split(":"))
    except (TypeError, ValueError):
        return 0.0
    start_m = sh * 60 + sm
    finish_m = fh * 60 + fm
    if finish_m < start_m:
        finish_m += 24 * 60
    try:
        brk = int(break_minutes or 0)
    except (TypeError, ValueError):
        brk = 0
    worked = finish_m - start_m - max(0, brk)
    return round(max(0, worked) / 60.0, 2)


def _break_label(minutes: int) -> str:
    m = int(minutes)
    if m < 60:
        return f"{m} min"
    h, r = divmod(m, 60)
    return f"{h}h {r:02d}m" if r else f"{h}h"


def render_header(title: str, caption: str | None = None) -> None:
    """Company logo + page heading (replaces crane emoji)."""
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=300)
    st.title(title)
    if caption:
        st.caption(caption)


def celebrate_entry_saved() -> None:
    """2-frame GIF (arms crossed → thumbs up); hard-capped at ~2 seconds."""
    media = SHAUN_CELEBRATE_MEDIA if SHAUN_CELEBRATE_MEDIA.exists() else SHAUN_CELEBRATE_FALLBACK
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

    # Inject into parent page so it covers the app and removes itself (balloons-style).
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
  // v5 — 2s celebration, new thumbs-up
  const DURATION = 2000;
  const src = "data:{mime};base64,{b64}";
  const STYLE_ID = "shaun-celebration-style-v5";
  const OVERLAY_ID = "shaun-celebration-overlay-v5";

  function buildOverlay(doc) {{
    ["shaun-celebration-overlay", "shaun-celebration-overlay-v3", "shaun-celebration-overlay-v5"].forEach(function (id) {{
      var el = doc.getElementById(id);
      if (el) el.remove();
    }});
    ["shaun-celebration-style", "shaun-celebration-style-v3", "shaun-celebration-style-v5"].forEach(function (id) {{
      var el = doc.getElementById(id);
      if (el) el.remove();
    }});

    const style = doc.createElement("style");
    style.id = STYLE_ID;
    style.textContent = `
      @keyframes shaunCelebInOutV5 {{
        0%   {{ opacity: 0; transform: scale(0.35); }}
        10%  {{ opacity: 1; transform: scale(1.05); }}
        15%  {{ opacity: 1; transform: scale(1); }}
        80%  {{ opacity: 1; transform: scale(1); }}
        100% {{ opacity: 0; transform: scale(0.95); }}
      }}
      #${{OVERLAY_ID}} {{
        position: fixed !important;
        inset: 0 !important;
        z-index: 2147483646 !important;
        display: flex !important;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        background: rgba(10, 25, 40, 0.42);
        animation: shaunCelebInOutV5 ${{DURATION}}ms ease-out forwards;
        pointer-events: none !important;
        font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
      }}
      #${{OVERLAY_ID}} img {{
        width: min(300px, 72vw);
        height: auto;
        border-radius: 18px;
        box-shadow: 0 16px 48px rgba(0,0,0,0.4);
        background: #fff;
      }}
      #${{OVERLAY_ID}} .shaun-caption {{
        margin-top: 14px;
        color: #fff;
        font-size: 1.2rem;
        font-weight: 650;
        text-shadow: 0 2px 10px rgba(0,0,0,0.55);
        text-align: center;
      }}
    `;
    doc.head.appendChild(style);

    const overlay = doc.createElement("div");
    overlay.id = OVERLAY_ID;
    overlay.innerHTML = `
      <img src="${{src}}" alt="Shaun thumbs up" />
      <div class="shaun-caption">👍 Nice work — entry saved!</div>
    `;
    doc.body.appendChild(overlay);

    setTimeout(function () {{
      var el = doc.getElementById(OVERLAY_ID);
      if (el) el.remove();
      var st = doc.getElementById(STYLE_ID);
      if (st) st.remove();
    }}, DURATION + 50);
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


def _req_label(text: str) -> None:
    """Field label with a red bold required asterisk."""
    st.markdown(
        f'<div style="font-size:0.875rem;margin-bottom:0.15rem;">'
        f'{text} <span style="color:#c62828;font-weight:700;">*</span>'
        f"</div>",
        unsafe_allow_html=True,
    )


def page_new_entry() -> None:
    st.caption(
        "Log who is filling this out, then enter hours for each person on site. "
        "Only people with hours above 0 are saved. Type the job site name freely. "
        "Fields marked with a red * are required."
    )

    # After a successful save we remount the form (empty). On validation errors we keep values.
    if st.session_state.pop("new_entry_success_msg", None):
        st.success(st.session_state.pop("new_entry_success_detail", "Entry saved."))
        celebrate_entry_saved()

    workers = _worker_options()
    known_sites = list(_project_options(active_only=False).keys())

    if not workers:
        st.warning("Add at least one worker in **Crew & Projects** before logging.")
        return

    worker_names = list(workers.keys())

    if "new_entry_form_id" not in st.session_state:
        st.session_state["new_entry_form_id"] = 0
    form_id = st.session_state["new_entry_form_id"]
    pfx = f"ne{form_id}_"

    # No st.form wrapper: time widgets must rerun live so totals update as times change.
    # Keys use form_id so a successful save remounts empty fields.
    c1, c2 = st.columns(2)
    with c1:
        _req_label("Date")
        entry_date = st.date_input(
            "Date",
            value=today_vancouver(),
            label_visibility="collapsed",
            key=f"{pfx}date",
            format="DD/MM/YYYY",
        )
        st.caption(format_display_date(entry_date))
    with c2:
        _req_label("Job site")
        project_name = st.text_input(
            "Job site",
            placeholder="Type job site name…",
            label_visibility="collapsed",
            key=f"{pfx}site",
            help=(
                "Type the job site. Matching names reuse an existing site; "
                "a new name creates one automatically."
                + (
                    f" Known sites: {', '.join(known_sites[:12])}"
                    + ("…" if len(known_sites) > 12 else "")
                    if known_sites
                    else ""
                )
            ),
        )

    _req_label("Log entry by")
    _default_logger = "Shaun Hellmich"
    _log_index = (
        worker_names.index(_default_logger) if _default_logger in worker_names else 0
    )
    logged_by_name = st.selectbox(
        "Log entry by",
        worker_names,
        index=_log_index,
        label_visibility="collapsed",
        key=f"{pfx}logged_by",
        help="Who is filling out this log (the person submitting).",
    )
    wcol, tcol = st.columns(2)
    with wcol:
        _req_label("Weather")
        weather = st.text_input(
            "Weather",
            placeholder="e.g. Sunny, light rain, overcast…",
            label_visibility="collapsed",
            key=f"{pfx}weather",
        )
    with tcol:
        _req_label("Temperature (°C)")
        temperature_c = st.selectbox(
            "Temperature (°C)",
            TEMPERATURE_C_OPTIONS,
            index=TEMPERATURE_C_OPTIONS.index(15),
            label_visibility="collapsed",
            key=f"{pfx}temp",
        )

    with st.container(border=True):
        st.caption(
            "Set start, finish, and lunch/break (15‑minute steps) for each person. "
            "Total is calculated automatically and cannot be edited. "
            "Leave start/finish as — if they did not work."
        )
        # Column weights: name (fixed left) + start close beside name + finish + break + total
        _time_cols = [1.35, 0.95, 0.95, 0.95, 0.85]
        # Header labels once (not repeated per worker)
        h0, h1, h2, h3, h4 = st.columns(_time_cols)
        with h0:
            st.markdown("&nbsp;", unsafe_allow_html=True)
        with h1:
            st.markdown(
                "<div style='font-size:0.85rem;font-weight:600;'>Start time</div>",
                unsafe_allow_html=True,
            )
        with h2:
            st.markdown(
                "<div style='font-size:0.85rem;font-weight:600;'>Finish time</div>",
                unsafe_allow_html=True,
            )
        with h3:
            st.markdown(
                "<div style='font-size:0.85rem;font-weight:600;'>Lunch / break</div>",
                unsafe_allow_html=True,
            )
        with h4:
            st.markdown(
                "<div style='font-size:0.85rem;font-weight:600;'>Total</div>",
                unsafe_allow_html=True,
            )

        for name in worker_names:
            wid = workers[name]
            ncol, c1, c2, c3, c4 = st.columns(_time_cols)
            with ncol:
                st.markdown(
                    f"<div style='padding-top:0.45rem;font-weight:600;'>{name}</div>",
                    unsafe_allow_html=True,
                )
            with c1:
                start = st.selectbox(
                    f"Start — {name}",
                    TIME_OPTIONS,
                    key=f"{pfx}st_{wid}",
                    label_visibility="collapsed",
                )
            with c2:
                finish = st.selectbox(
                    f"Finish — {name}",
                    TIME_OPTIONS,
                    key=f"{pfx}fn_{wid}",
                    label_visibility="collapsed",
                )
            with c3:
                brk = st.selectbox(
                    f"Break — {name}",
                    BREAK_MINUTE_OPTIONS,
                    format_func=_break_label,
                    key=f"{pfx}br_{wid}",
                    label_visibility="collapsed",
                )
            total = _calc_worked_hours(start, finish, brk)
            with c4:
                st.markdown(
                    f"<div style='padding-top:0.45rem;font-weight:600;'>"
                    f"{total:g} hr</div>",
                    unsafe_allow_html=True,
                )

    _req_label("Work performed")
    work_done = st.text_area(
        "Work performed",
        placeholder="Detail of today jobsite activities",
        height=120,
        label_visibility="collapsed",
        key=f"{pfx}work",
    )
    _req_label("Health, Safety, Environment")
    safety = st.text_area(
        "Health, Safety, Environment",
        placeholder="Incidents, toolbox talk topics, PPE used",
        height=80,
        label_visibility="collapsed",
        key=f"{pfx}hse",
    )
    crew_notes = st.text_area(
        "Visitor / Subcontractors",
        placeholder="Visitors, subcontractors, extra headcount notes…",
        height=80,
        key=f"{pfx}visitors",
    )
    materials_notes = st.text_area(
        "Equipment/Materials",
        placeholder="Equipment and materials used, deliveries, shortages…",
        height=80,
        key=f"{pfx}materials",
    )
    issues = st.text_area(
        "Issues / delays",
        placeholder="Weather delays, missing materials, change orders, access problems…",
        height=80,
        key=f"{pfx}issues",
    )
    action_follow_up = st.text_area(
        "Action / Follow up Items",
        placeholder="Follow-ups, open actions, items for next shift…",
        height=80,
        key=f"{pfx}followup",
    )

    submitted = st.button("Save entry", type="primary", use_container_width=True)

    if submitted:
        missing: list[str] = []
        if entry_date is None:
            missing.append("Date")
        if not (project_name or "").strip():
            missing.append("Job site")
        if not logged_by_name:
            missing.append("Log entry by")
        if not (weather or "").strip():
            missing.append("Weather")
        if temperature_c is None:
            missing.append("Temperature")
        if not (safety or "").strip():
            missing.append("Health, Safety, Environment")
        if not (work_done or "").strip():
            missing.append("Work performed")
        if missing:
            st.error(
                "Please fill in all required fields: " + ", ".join(missing) + "."
            )
            return
        hours_by_id: dict[int, dict] = {}
        people_with_hours: list[str] = []
        for name in worker_names:
            wid = workers[name]
            start = st.session_state.get(f"{pfx}st_{wid}", TIME_BLANK)
            finish = st.session_state.get(f"{pfx}fn_{wid}", TIME_BLANK)
            brk = st.session_state.get(f"{pfx}br_{wid}", 0)
            total = _calc_worked_hours(start, finish, brk)
            hours_by_id[wid] = {
                "start_time": "" if start == TIME_BLANK else start,
                "finish_time": "" if finish == TIME_BLANK else finish,
                "break_minutes": int(brk or 0),
                "hours_worked": total,
            }
            if total > 0:
                people_with_hours.append(name)
        if not people_with_hours:
            st.error(
                "Set start and finish times so at least one person has total hours above 0."
            )
            return
        try:
            project_id = db.get_or_create_project(project_name)
            _clear_crew_cache()
            ids = db.add_entries_for_crew(
                entry_date=entry_date,
                project_id=project_id,
                hours_by_worker_id=hours_by_id,
                logged_by_worker_id=workers[logged_by_name],
                weather=weather,
                temperature_c=float(temperature_c),
                work_done=work_done,
                crew_notes=crew_notes,
                materials_notes=materials_notes,
                issues_delays=issues,
                safety_notes=safety,
                action_follow_up=action_follow_up,
            )
        except Exception as exc:
            st.error(f"Could not save: {exc}")
            st.info(
                "If this mentions a missing column, run the latest SQL migration files "
                "in your Supabase SQL Editor (`supabase_migration_*.sql`), then try again."
            )
            return

        detail = ", ".join(
            f"{n} ({hours_by_id[workers[n]]['hours_worked']:g}h)"
            for n in people_with_hours
        )
        st.session_state["new_entry_success_msg"] = True
        st.session_state["new_entry_success_detail"] = (
            f"Saved journal for {format_display_date(entry_date)} "
            f"@ {project_name.strip()} (logged by {logged_by_name}): {detail}."
        )
        st.session_state["new_entry_form_id"] = form_id + 1
        # Drop old widget keys so the next form_id starts clean
        for key in list(st.session_state.keys()):
            if str(key).startswith(pfx):
                del st.session_state[key]
        st.rerun()


def page_journal() -> None:
    workers = _worker_options(active_only=False)
    projects = _project_options(active_only=False)

    with st.expander("Filters", expanded=True):
        f1, f2, f3, f4 = st.columns(4)
        with f1:
            date_from = st.date_input(
                "From",
                value=today_vancouver() - timedelta(days=30),
                key="filter_from",
            )
        with f2:
            date_to = st.date_input("To", value=today_vancouver(), key="filter_to")
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

    # One journal card per form submission (may include multiple people/hours)
    journals = db.list_journal_groups(
        date_from=date_from.isoformat(),
        date_to=date_to.isoformat(),
        worker_id=worker_id,
        project_id=project_id,
    )
    stats = db.journal_group_stats(journals)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Journals", stats["count"])
    m2.metric("Total hours", f"{stats['total_hours']:.1f}")
    m3.metric("Workers", stats["worker_count"])
    m4.metric("Projects", stats["project_count"])

    if not journals:
        st.info("No journals match these filters.")
        return

    by_gid = {str(j["group_id"]): j for j in journals}
    selected_gids = [
        str(j["group_id"])
        for j in journals
        if st.session_state.get(f"sel_g_{j['group_id']}", False)
    ]
    selected_journals = [by_gid[g] for g in selected_gids if g in by_gid]

    if selected_journals:
        zip_bytes = build_entries_pdf_zip(selected_journals)
        st.download_button(
            label=f"Download {len(selected_journals)} PDF(s) as ZIP",
            data=zip_bytes,
            file_name="journal_entries_pdfs.zip",
            mime="application/zip",
            type="primary",
            key="zip_selected_pdfs_top",
            use_container_width=True,
        )
        st.caption(
            f"{len(selected_journals)} journal(s) selected — one PDF per journal inside the ZIP."
        )

    st.caption(
        "Each card is one daily log (all people/hours from that save). "
        "Check boxes to bulk-export PDFs, or use **Export PDF** on a card."
    )

    for journal in journals:
        gid = str(journal["group_id"])
        people = journal.get("people") or []
        with st.container(border=True):
            top_l, top_mid, top_r = st.columns([0.4, 3.6, 1.2])
            with top_l:
                st.checkbox(
                    f"Select {gid}",
                    key=f"sel_g_{gid}",
                    label_visibility="collapsed",
                )
            with top_mid:
                logged_by = journal.get("logged_by_name") or ""
                logged_bit = f" · logged by {logged_by}" if logged_by else ""
                temp = journal.get("temperature_c")
                temp_bit = (
                    f" · {int(temp) if temp == int(temp) else temp}°C"
                    if temp is not None and temp != ""
                    else ""
                )
                hours_summary = ", ".join(
                    f"{p.get('worker_name')} "
                    f"({p.get('start_time') or '—'}–{p.get('finish_time') or '—'}, "
                    f"brk {_break_label(int(p.get('break_minutes') or 0))}, "
                    f"{float(p.get('hours_worked') or 0):g}h)"
                    for p in people
                )
                st.markdown(
                    f"**{format_display_date(journal.get('entry_date'))}** — "
                    f"**{journal.get('project_name')}** · "
                    f"{float(journal.get('total_hours') or 0):g} hr total · "
                    f"{journal.get('weather') or '—'}"
                    f"{temp_bit}{logged_bit}"
                )
                if hours_summary:
                    st.caption(hours_summary)
            with top_r:
                action = st.selectbox(
                    "Action",
                    ["", "Edit", "Delete"],
                    key=f"action_g_{gid}",
                    label_visibility="collapsed",
                )

            st.write(journal.get("work_done") or "_(no work description)_")

            details = []
            if journal.get("safety_notes"):
                details.append(
                    f"**Health, Safety, Environment:** {journal['safety_notes']}"
                )
            if journal.get("crew_notes"):
                details.append(
                    f"**Visitor / Subcontractors:** {journal['crew_notes']}"
                )
            if journal.get("materials_notes"):
                details.append(f"**Equipment/Materials:** {journal['materials_notes']}")
            if journal.get("issues_delays"):
                details.append(f"**Issues:** {journal['issues_delays']}")
            if journal.get("action_follow_up"):
                details.append(f"**Action / Follow up:** {journal['action_follow_up']}")
            if details:
                st.markdown("  \n".join(details))

            pdf_bytes = build_entry_pdf(journal)
            st.download_button(
                label="Export PDF",
                data=pdf_bytes,
                file_name=entry_pdf_filename(journal),
                mime="application/pdf",
                key=f"pdf_g_{gid}",
                use_container_width=True,
            )

            if action == "Edit":
                # Edit first person-row shared fields (updates apply to that row);
                # full multi-line edit stays available via person rows if needed.
                primary = None
                if people:
                    primary = db.get_entry(int(people[0]["id"]))
                if primary:
                    _edit_entry_form(primary, workers, projects)
                    if len(people) > 1:
                        st.info(
                            "This journal has multiple people. Editing updates the first "
                            "person’s line fields; hours for others stay as logged. "
                            "Delete the journal and re-enter if you need a full rewrite."
                        )
            elif action == "Delete":
                if st.button(
                    "Confirm delete this entire journal (all people on it)",
                    key=f"del_g_{gid}",
                    type="primary",
                ):
                    db.delete_entry_group(journal)
                    st.success("Deleted journal.")
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
                format="DD/MM/YYYY",
            )
            st.caption(format_display_date(entry_date))
        with c2:
            worker_name = st.selectbox(
                "Worker",
                worker_names,
                index=worker_names.index(current_worker),
                key=f"ed_worker_{entry['id']}",
            )
        with c3:
            project_name = st.text_input(
                "Job site",
                value=current_project,
                key=f"ed_project_{entry['id']}",
            )

        wcol, tcol = st.columns(2)
        with wcol:
            weather = st.text_input(
                "Weather",
                value=entry.get("weather") or "",
                key=f"ed_weather_{entry['id']}",
            )
        with tcol:
            raw_temp = entry.get("temperature_c")
            try:
                temp_default = int(float(raw_temp)) if raw_temp is not None and raw_temp != "" else 15
            except (TypeError, ValueError):
                temp_default = 15
            temp_default = max(-5, min(40, temp_default))
            temperature_c = st.selectbox(
                "Temperature (°C)",
                TEMPERATURE_C_OPTIONS,
                index=TEMPERATURE_C_OPTIONS.index(temp_default),
                key=f"ed_temp_{entry['id']}",
            )
        st.caption("Times use 15‑minute steps. Total is calculated and not editable.")
        tc1, tc2, tc3, tc4 = st.columns(4)
        st_raw = entry.get("start_time") or TIME_BLANK
        fn_raw = entry.get("finish_time") or TIME_BLANK
        if st_raw not in TIME_OPTIONS:
            st_raw = TIME_BLANK
        if fn_raw not in TIME_OPTIONS:
            fn_raw = TIME_BLANK
        try:
            br_raw = int(entry.get("break_minutes") or 0)
        except (TypeError, ValueError):
            br_raw = 0
        if br_raw not in BREAK_MINUTE_OPTIONS:
            br_raw = min(BREAK_MINUTE_OPTIONS, key=lambda x: abs(x - br_raw))
        with tc1:
            start = st.selectbox(
                "Start time",
                TIME_OPTIONS,
                index=TIME_OPTIONS.index(st_raw),
                key=f"ed_st_{entry['id']}",
            )
        with tc2:
            finish = st.selectbox(
                "Finish time",
                TIME_OPTIONS,
                index=TIME_OPTIONS.index(fn_raw),
                key=f"ed_fn_{entry['id']}",
            )
        with tc3:
            brk = st.selectbox(
                "Lunch / break",
                BREAK_MINUTE_OPTIONS,
                index=BREAK_MINUTE_OPTIONS.index(br_raw),
                format_func=_break_label,
                key=f"ed_br_{entry['id']}",
            )
        hours = _calc_worked_hours(start, finish, brk)
        with tc4:
            st.markdown(
                f"<div style='padding-top:1.6rem;font-weight:600;'>Total: {hours:g} hr</div>",
                unsafe_allow_html=True,
            )

        work_done = st.text_area(
            "Work performed",
            value=entry["work_done"] or "",
            placeholder="Detail of today jobsite activities",
            height=100,
            key=f"ed_work_{entry['id']}",
        )
        safety = st.text_area(
            "Health, Safety, Environment",
            value=entry["safety_notes"] or "",
            placeholder="Incidents, toolbox talk topics, PPE used",
            height=70,
            key=f"ed_safe_{entry['id']}",
        )
        crew_notes = st.text_area(
            "Visitor / Subcontractors",
            value=entry["crew_notes"] or "",
            height=70,
            key=f"ed_crew_{entry['id']}",
        )
        materials_notes = st.text_area(
            "Equipment/Materials",
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
        action_follow_up = st.text_area(
            "Action / Follow up Items",
            value=entry.get("action_follow_up") or "",
            height=70,
            key=f"ed_follow_{entry['id']}",
        )

        saved = st.form_submit_button("Update entry", type="primary")

    if saved:
        if not work_done.strip():
            st.error("Work performed cannot be empty.")
            return
        if not (project_name or "").strip():
            st.error("Job site cannot be empty.")
            return
        try:
            project_id = db.get_or_create_project(project_name)
            _clear_crew_cache()
        except Exception as exc:
            st.error(str(exc))
            return
        db.update_entry(
            entry_id=entry["id"],
            entry_date=entry_date,
            worker_id=all_workers[worker_name],
            project_id=project_id,
            weather=weather,
            temperature_c=float(temperature_c),
            hours_worked=hours,
            start_time="" if start == TIME_BLANK else start,
            finish_time="" if finish == TIME_BLANK else finish,
            break_minutes=int(brk or 0),
            work_done=work_done,
            crew_notes=crew_notes,
            materials_notes=materials_notes,
            issues_delays=issues,
            safety_notes=safety,
            action_follow_up=action_follow_up,
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
            value=today_vancouver().replace(day=1),
            key="export_from",
        )
    with c2:
        date_to = st.date_input("To", value=today_vancouver(), key="export_to")
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
        f"**Today (Vancouver):** {today_vancouver().strftime('%a, %b %d, %Y')}  \n"
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
