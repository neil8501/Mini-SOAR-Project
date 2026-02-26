import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlmodel import Session, select

from app.core.config import settings
from app.metrics.prometheus import time_to_contain_seconds
from app.db.session import get_session
from app.models.action import Action
from app.models.artifact import Artifact
from app.models.case import Case
from app.models.ticket import Ticket
from app.models.timeline import TimelineEvent
from app.services.reporting import build_incident_report_markdown, write_report_files

router = APIRouter(prefix="/cases", tags=["cases"])


def _require_admin_key(x_admin_key: Optional[str]) -> None:
    if not x_admin_key or x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=401, detail="Invalid admin key")


@router.get("")
def list_cases(
    session: Session = Depends(get_session),
    status: Optional[str] = Query(default=None),
    type: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
):
    q = select(Case).order_by(Case.created_at.desc())
    if status:
        q = q.where(Case.status == status)
    if type:
        q = q.where(Case.type == type)
    if severity:
        q = q.where(Case.severity == severity)

    cases = session.exec(q.limit(limit)).all()
    return {"cases": [c.model_dump() for c in cases]}


@router.get("/{case_id}")
def get_case(case_id: uuid.UUID, session: Session = Depends(get_session)):
    case = session.exec(select(Case).where(Case.id == case_id)).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    artifacts = session.exec(select(Artifact).where(Artifact.case_id == case_id)).all()
    timeline = session.exec(
        select(TimelineEvent).where(TimelineEvent.case_id == case_id).order_by(TimelineEvent.ts)
    ).all()
    actions = session.exec(
        select(Action).where(Action.case_id == case_id).order_by(Action.started_at)
    ).all()
    tickets = session.exec(select(Ticket).where(Ticket.case_id == case_id)).all()

    return {
        "case": case.model_dump(),
        "artifacts": [a.model_dump() for a in artifacts],
        "timeline": [t.model_dump() for t in timeline],
        "actions": [a.model_dump() for a in actions],
        "tickets": [t.model_dump() for t in tickets],
    }


@router.post("/{case_id}/close")
def close_case(
    case_id: uuid.UUID,
    session: Session = Depends(get_session),
    x_admin_key: Optional[str] = Header(default=None),
):
    _require_admin_key(x_admin_key)

    case = session.exec(select(Case).where(Case.id == case_id)).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    now = datetime.now(timezone.utc)

    # mark closed
    case.status = "closed"
    case.updated_at = now
    session.add(case)

    session.add(
        TimelineEvent(
            id=uuid.uuid4(),
            case_id=case.id,
            ts=now,
            event_type="close",
            message="case closed",
            details={"closed_at": now.isoformat().replace("+00:00", "Z")},
        )
    )
    session.commit()

    # report generation
    built = build_incident_report_markdown(session=session, case_id=case_id)
    paths = write_report_files(case_id=case_id, markdown=built["markdown"])

    session.add(
        TimelineEvent(
            id=uuid.uuid4(),
            case_id=case.id,
            ts=now,
            event_type="report",
            message="incident report generated",
            details={"paths": paths},
        )
    )
    session.commit()

    # metric: time to contain
    created_at = getattr(case, "created_at", None)
    if isinstance(created_at, datetime):
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        dt = (now - created_at.astimezone(timezone.utc)).total_seconds()
        time_to_contain_seconds.labels(type=case.type, severity=case.severity).observe(max(0.0, dt))

    return {
        "closed": True,
        "case_id": str(case_id),
        "report": {
            "markdown_path": paths.get("markdown_path"),
            "pdf_path": paths.get("pdf_path"),
        },
        "markdown_preview": built["markdown"],
    }
