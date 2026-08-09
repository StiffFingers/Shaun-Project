"""PDF export for a single journal entry — layout mirrors the New Entry form."""

from __future__ import annotations

from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Iterable
from zipfile import ZIP_DEFLATED, ZipFile

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

LOGO_PATH = Path(__file__).parent / "assets" / "in-spec-logo.png"
NAVY = colors.HexColor("#1F4E79")
LIGHT = colors.HexColor("#F4F7FA")
BORDER = colors.HexColor("#CCCCCC")
RED = colors.HexColor("#C62828")

# Letter page with 0.75" side margins → 7.0" content width
CONTENT_W = 7.0 * inch
COL_GAP = 0.2 * inch
HALF_W = (CONTENT_W - COL_GAP) / 2


def _styles():
    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle(
            "EntryTitle",
            parent=base["Heading1"],
            fontSize=14,
            textColor=NAVY,
            spaceAfter=8,
            leading=18,
        ),
        "label": ParagraphStyle(
            "FieldLabel",
            parent=base["Normal"],
            fontSize=9,
            textColor=colors.HexColor("#333333"),
            fontName="Helvetica-Bold",
            spaceBefore=6,
            spaceAfter=2,
            leading=12,
            leftIndent=0,
            firstLineIndent=0,
        ),
        "req": ParagraphStyle(
            "FieldLabelReq",
            parent=base["Normal"],
            fontSize=9,
            textColor=colors.HexColor("#333333"),
            fontName="Helvetica-Bold",
            spaceBefore=6,
            spaceAfter=2,
            leading=12,
            leftIndent=0,
            firstLineIndent=0,
        ),
        "value": ParagraphStyle(
            "FieldValue",
            parent=base["Normal"],
            fontSize=10,
            leading=13,
            spaceAfter=4,
        ),
        "box": ParagraphStyle(
            "BoxValue",
            parent=base["Normal"],
            fontSize=10,
            leading=13,
        ),
        "small": ParagraphStyle(
            "SmallNote",
            parent=base["Normal"],
            fontSize=8,
            textColor=colors.HexColor("#666666"),
            leading=10,
        ),
        "footer": ParagraphStyle(
            "Footer",
            parent=base["Normal"],
            fontSize=8,
            textColor=colors.HexColor("#888888"),
            alignment=TA_LEFT,
        ),
    }
    return styles


def _esc(text: Any) -> str:
    if text is None:
        return ""
    s = str(text)
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )


def format_display_date(value: Any) -> str:
    """Format as 'Aug 09, 2026' for UI and PDF."""
    if value is None or value == "":
        return "—"
    if isinstance(value, datetime):
        d = value.date()
    elif isinstance(value, date):
        d = value
    else:
        s = str(value).strip()[:10]
        try:
            d = date.fromisoformat(s)
        except ValueError:
            return str(value)
    return d.strftime("%b %d, %Y")


def _label(styles, text: str, required: bool = False) -> Paragraph:
    if required:
        return Paragraph(
            f'{_esc(text)} <font color="#c62828"><b>*</b></font>',
            styles["req"],
        )
    return Paragraph(_esc(text), styles["label"])


def _value_box(styles, text: Any, width: float = CONTENT_W) -> Table:
    body = Paragraph(_esc(text) if text not in (None, "") else "—", styles["box"])
    t = Table([[body]], colWidths=[width])
    t.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return t


def _two_col(styles, left_label, left_val, right_label, right_val, left_req=False, right_req=False):
    """Two fields on one row; total width == CONTENT_W so left edge matches full-width fields."""
    zero = [
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]
    # Labels as plain paragraphs so spaceBefore matches full-width fields
    left_lab = _label(styles, left_label, left_req)
    right_lab = _label(styles, right_label, right_req)
    # left | gap | right  → exactly CONTENT_W wide, left column starts at 0
    data = [
        [
            left_lab,
            "",
            right_lab,
        ],
        [
            _value_box(styles, left_val, width=HALF_W),
            "",
            _value_box(styles, right_val, width=HALF_W),
        ],
    ]
    row = Table(data, colWidths=[HALF_W, COL_GAP, HALF_W])
    row.setStyle(
        TableStyle(
            zero
            + [
                ("BOTTOMPADDING", (0, 0), (-1, 0), 2),  # under labels
                ("TOPPADDING", (0, 1), (-1, 1), 0),
            ]
        )
    )
    # Wrap so the outer flowable is exactly content width (left-aligned with page)
    wrapper = Table([[row]], colWidths=[CONTENT_W])
    wrapper.setStyle(TableStyle(zero))
    return wrapper


def _fmt_temp(entry: dict[str, Any]) -> str:
    temp = entry.get("temperature_c")
    if temp is None or temp == "":
        return "—"
    try:
        t = float(temp)
        return f"{int(t) if t == int(t) else t} °C"
    except (TypeError, ValueError):
        return str(temp)


def _fmt_hours(entry: dict[str, Any]) -> str:
    h = entry.get("hours_worked")
    try:
        return f"{float(h):g}"
    except (TypeError, ValueError):
        return str(h or "—")


def _people_rows(journal: dict[str, Any]) -> list[list[str]]:
    """Return table rows: name, start, finish, break, total for PDF hours section."""
    people = journal.get("people") or []
    if people:
        rows = []
        for p in people:
            name = p.get("worker_name") or "—"
            start = p.get("start_time") or "—"
            finish = p.get("finish_time") or "—"
            try:
                brk = int(p.get("break_minutes") or 0)
                brk_s = f"{brk} min"
            except (TypeError, ValueError):
                brk_s = "—"
            try:
                hrs = f"{float(p.get('hours_worked') or 0):g} hr"
            except (TypeError, ValueError):
                hrs = str(p.get("hours_worked") or "—")
            rows.append([name, start, finish, brk_s, hrs])
        return rows
    # Legacy single person-row
    return [
        [
            journal.get("worker_name") or "—",
            journal.get("start_time") or "—",
            journal.get("finish_time") or "—",
            f"{int(journal.get('break_minutes') or 0)} min",
            f"{_fmt_hours(journal)} hr",
        ]
    ]


def build_entry_pdf(entry: dict[str, Any]) -> bytes:
    """Return PDF bytes for one journal (may include multiple people/hours)."""
    styles = _styles()
    buf = BytesIO()
    people = entry.get("people") or []
    title_id = entry.get("group_id") or entry.get("id") or ""
    if isinstance(title_id, str) and title_id.startswith("solo-"):
        title_id = title_id.replace("solo-", "#")
    elif isinstance(title_id, str) and len(title_id) > 8:
        title_id = title_id[:8]
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
        title=f"Journal Entry {title_id}",
    )
    story = []

    if LOGO_PATH.exists():
        img = Image(str(LOGO_PATH), width=2.6 * inch, height=0.72 * inch)
        img.hAlign = "LEFT"
        story.append(img)
        story.append(Spacer(1, 6))

    story.append(Paragraph("In-Spec Team Work Journal Entry", styles["title"]))
    story.append(
        Paragraph(
            f"Journal { _esc(title_id) } · exported from the field journal",
            styles["small"],
        )
    )
    story.append(HRFlowable(width="100%", thickness=1, color=NAVY, spaceAfter=8, spaceBefore=4))

    story.append(
        _two_col(
            styles,
            "Date",
            format_display_date(entry.get("entry_date")),
            "Job",
            entry.get("project_name") or "—",
            left_req=True,
            right_req=True,
        )
    )
    story.append(_label(styles, "Log entry by", required=True))
    story.append(_value_box(styles, entry.get("logged_by_name") or "—"))

    # Same vertical gap as full-width fields before Weather / Temperature
    story.append(Spacer(1, 4))
    story.append(
        _two_col(
            styles,
            "Weather",
            entry.get("weather") or "—",
            "Temperature (°C)",
            _fmt_temp(entry),
            left_req=True,
            right_req=True,
        )
    )

    # Hours by person — all people on this journal
    story.append(Spacer(1, 8))
    story.append(Paragraph("Hours", styles["label"]))
    header = [
        Paragraph("<b>Name</b>", styles["small"]),
        Paragraph("<b>Start</b>", styles["small"]),
        Paragraph("<b>Finish</b>", styles["small"]),
        Paragraph("<b>Break</b>", styles["small"]),
        Paragraph("<b>Total</b>", styles["small"]),
    ]
    hour_lines = [header]
    for row in _people_rows(entry):
        hour_lines.append(
            [Paragraph(_esc(cell), styles["value"]) for cell in row]
        )
    if len(hour_lines) == 1:
        hour_lines.append(
            [Paragraph("—", styles["value"]) for _ in range(5)]
        )

    col_w = [CONTENT_W * 0.32, CONTENT_W * 0.15, CONTENT_W * 0.15, CONTENT_W * 0.18, CONTENT_W * 0.20]
    hours_people_table = Table(hour_lines, colWidths=col_w)
    hours_people_table.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LINEBELOW", (0, 0), (-1, 0), 0.4, BORDER),
            ]
        )
    )
    hours_inner = Table(
        [
            [
                Paragraph(
                    "Start, finish, lunch/break, and calculated total for each person.",
                    styles["small"],
                )
            ],
            [hours_people_table],
        ],
        colWidths=[CONTENT_W],
    )
    hours_inner.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.8, BORDER),
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(hours_inner)

    story.append(_label(styles, "Work performed", required=True))
    story.append(_value_box(styles, entry.get("work_done") or "—"))

    story.append(_label(styles, "Health, Safety, Environment", required=True))
    story.append(_value_box(styles, entry.get("safety_notes") or "—"))

    story.append(_label(styles, "Visitor / Subcontractors"))
    story.append(_value_box(styles, entry.get("crew_notes") or "—"))

    story.append(_label(styles, "Equipment/Materials"))
    story.append(_value_box(styles, entry.get("materials_notes") or "—"))

    story.append(_label(styles, "Issues / delays"))
    story.append(_value_box(styles, entry.get("issues_delays") or "—"))

    story.append(_label(styles, "Action / Follow up Items"))
    story.append(_value_box(styles, entry.get("action_follow_up") or "—"))

    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", thickness=0.4, color=BORDER, spaceAfter=6))
    logged_at = entry.get("created_at") or ""
    story.append(
        Paragraph(
            f"Logged at: {_esc(logged_at)}",
            styles["footer"],
        )
    )

    doc.build(story)
    return buf.getvalue()


def entry_pdf_filename(entry: dict[str, Any]) -> str:
    """Filename: Job {Job site}_{Date}.pdf  e.g. Job Main Site A_Aug 09, 2026.pdf"""
    site = str(entry.get("project_name") or "Site").strip() or "Site"
    day = format_display_date(entry.get("entry_date"))
    if day == "—":
        day = "Unknown date"
    # Job {site}_{date}.pdf — replace path-unsafe chars
    raw = f"Job {site}_{day}.pdf"
    safe = "".join(c if c not in '\\/:*?"<>|' else "-" for c in raw)
    while "  " in safe:
        safe = safe.replace("  ", " ")
    return safe.strip()


def build_entries_pdf_zip(entries: Iterable[dict[str, Any]]) -> bytes:
    """One PDF per journal group, packaged in a single ZIP download."""
    buf = BytesIO()
    with ZipFile(buf, "w", ZIP_DEFLATED) as zf:
        used_names: set[str] = set()
        for entry in entries:
            name = entry_pdf_filename(entry)
            base = name
            n = 1
            while name in used_names:
                name = base.replace(".pdf", f"_{n}.pdf")
                n += 1
            used_names.add(name)
            zf.writestr(name, build_entry_pdf(entry))
    return buf.getvalue()
