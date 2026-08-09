"""PDF export for a single journal entry — layout mirrors the New Entry form."""

from __future__ import annotations

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


def _label(styles, text: str, required: bool = False) -> Paragraph:
    if required:
        return Paragraph(
            f'{_esc(text)} <font color="#c62828"><b>*</b></font>',
            styles["req"],
        )
    return Paragraph(_esc(text), styles["label"])


def _value_box(styles, text: Any, min_height: float = 28) -> Table:
    body = Paragraph(_esc(text) if text not in (None, "") else "—", styles["box"])
    t = Table([[body]], colWidths=[6.5 * inch])
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
    # min height via spacer inside if empty long fields
    return t


def _two_col(styles, left_label, left_val, right_label, right_val, left_req=False, right_req=False):
    left = [
        _label(styles, left_label, left_req),
        _value_box(styles, left_val),
    ]
    right = [
        _label(styles, right_label, right_req),
        _value_box(styles, right_val),
    ]
    # Stack labels+values into mini tables then side by side
    def stack(parts):
        data = [[p] for p in parts]
        t = Table(data, colWidths=[3.15 * inch])
        t.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
        return t

    row = Table([[stack(left), stack(right)]], colWidths=[3.25 * inch, 3.25 * inch])
    row.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return row


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


def build_entry_pdf(entry: dict[str, Any]) -> bytes:
    """Return PDF bytes for one journal entry in New Entry form style."""
    styles = _styles()
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
        title=f"Journal Entry #{entry.get('id', '')}",
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
            f"Entry #{_esc(entry.get('id'))} · exported from the field journal",
            styles["small"],
        )
    )
    story.append(HRFlowable(width="100%", thickness=1, color=NAVY, spaceAfter=8, spaceBefore=4))

    story.append(
        _two_col(
            styles,
            "Date",
            entry.get("entry_date") or "—",
            "Job site",
            entry.get("project_name") or "—",
            left_req=True,
            right_req=True,
        )
    )
    story.append(_label(styles, "Log entry by", required=True))
    story.append(_value_box(styles, entry.get("logged_by_name") or "—"))

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

    # Hours by person (this entry's worker)
    story.append(Spacer(1, 6))
    story.append(Paragraph("Hours", styles["label"]))
    hours_inner = Table(
        [
            [
                Paragraph(
                    "Enter hours for each active crew member who worked. "
                    "Leave at 0 if they did not work.",
                    styles["small"],
                )
            ],
            [
                Table(
                    [
                        [
                            Paragraph(
                                f"<b>{_esc(entry.get('worker_name') or '—')}</b>",
                                styles["value"],
                            ),
                            Paragraph(_fmt_hours(entry), styles["value"]),
                        ]
                    ],
                    colWidths=[4.5 * inch, 1.5 * inch],
                )
            ],
        ],
        colWidths=[6.5 * inch],
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

    story.append(_label(styles, "Materials"))
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
    eid = entry.get("id", "x")
    day = str(entry.get("entry_date") or "date")[:10]
    worker = str(entry.get("worker_name") or "worker").replace(" ", "_")
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in worker)[:40]
    return f"journal_{day}_{safe}_{eid}.pdf"


def build_entries_pdf_zip(entries: Iterable[dict[str, Any]]) -> bytes:
    """One PDF per entry, packaged in a single ZIP download."""
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
