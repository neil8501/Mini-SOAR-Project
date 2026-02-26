import os
import textwrap
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from sqlmodel import Session, select

from app.core.config import settings
from app.models.action import Action
from app.models.artifact import Artifact
from app.models.case import Case
from app.models.ticket import Ticket
from app.models.timeline import TimelineEvent


def _ts(dt: datetime | None) -> str:
    if not dt:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def build_incident_report_markdown(
    session: Session,
    case_id: uuid.UUID,
) -> dict[str, Any]:
    case = session.exec(select(Case).where(Case.id == case_id)).first()
    if not case:
        raise ValueError("Case not found")

    artifacts = session.exec(select(Artifact).where(Artifact.case_id == case_id)).all()
    timeline = session.exec(
        select(TimelineEvent).where(TimelineEvent.case_id == case_id).order_by(TimelineEvent.ts)
    ).all()
    actions = session.exec(
        select(Action).where(Action.case_id == case_id).order_by(Action.started_at)
    ).all()
    tickets = session.exec(select(Ticket).where(Ticket.case_id == case_id)).all()

    # Summary observables
    by_type: dict[str, list[str]] = {}
    for a in artifacts:
        by_type.setdefault(a.type, []).append(a.value)

    created_at = getattr(case, "created_at", None)
    updated_at = getattr(case, "updated_at", None)

    md = []
    md.append(f"# Incident Report — Case {case.id}")
    md.append("")
    md.append("## Summary")
    md.append("")
    md.append(f"- **Type:** {case.type}")
    md.append(f"- **Status:** {case.status}")
    md.append(f"- **Severity:** {case.severity}")
    md.append(f"- **Score:** {case.score}")
    md.append(f"- **Created:** {_ts(created_at)}")
    md.append(f"- **Updated:** {_ts(updated_at)}")
    md.append("")

    md.append("## Indicators / Artifacts")
    md.append("")
    if not artifacts:
        md.append("_No artifacts recorded._")
    else:
        for t in sorted(by_type.keys()):
            md.append(f"### {t}")
            for v in sorted(set(by_type[t])):
                md.append(f"- `{v}`")
            md.append("")

    md.append("## Actions")
    md.append("")
    if not actions:
        md.append("_No actions executed._")
    else:
        for a in actions:
            md.append(f"- **{a.action_type}** | success={a.success} | started={_ts(a.started_at)} | finished={_ts(a.finished_at)}")
            if a.params:
                md.append(f"  - params: `{a.params}`")
            if a.result:
                md.append(f"  - result: `{a.result}`")
    md.append("")

    md.append("## Tickets")
    md.append("")
    if not tickets:
        md.append("_No tickets created._")
    else:
        for t in tickets:
            md.append(f"- **{t.id}** | status={t.status} | created={_ts(t.created_at)} | summary={t.summary}")
    md.append("")

    md.append("## Timeline")
    md.append("")
    if not timeline:
        md.append("_No timeline events._")
    else:
        for ev in timeline:
            md.append(f"- `{_ts(ev.ts)}` **{ev.event_type}** — {ev.message}")
            if ev.details:
                # keep compact
                md.append(f"  - details: `{ev.details}`")
    md.append("")

    report_md = "\n".join(md).strip() + "\n"

    return {
        "case": case,
        "markdown": report_md,
        "artifacts_count": len(artifacts),
        "actions_count": len(actions),
        "timeline_count": len(timeline),
        "tickets_count": len(tickets),
    }


def write_report_files(case_id: uuid.UUID, markdown: str) -> dict[str, str]:
    report_dir = Path(settings.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    md_path = report_dir / f"case_{case_id}.md"
    md_path.write_text(markdown, encoding="utf-8")

    out = {"markdown_path": str(md_path)}

    if settings.report_generate_pdf:
        pdf_path = report_dir / f"case_{case_id}.pdf"
        _markdown_to_simple_pdf(markdown, pdf_path)
        out["pdf_path"] = str(pdf_path)

    return out


def _markdown_to_simple_pdf(markdown: str, pdf_path: Path) -> None:
    # Minimal, dependency-free markdown->PDF: render as wrapped plain text.
    c = canvas.Canvas(str(pdf_path), pagesize=LETTER)
    width, height = LETTER

    left = 54
    top = height - 54
    line_height = 12
    y = top

    text = markdown.replace("\t", "  ")
    lines: list[str] = []
    for raw in text.splitlines():
        if raw.strip() == "":
            lines.append("")
            continue
        wrapped = textwrap.wrap(raw, width=95)
        if not wrapped:
            lines.append("")
        else:
            lines.extend(wrapped)

    c.setFont("Helvetica", 10)

    for line in lines:
        if y <= 54:
            c.showPage()
            c.setFont("Helvetica", 10)
            y = top
        c.drawString(left, y, line[:2000])
        y -= line_height

    c.save()
