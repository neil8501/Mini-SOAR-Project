from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.db.session import get_session
from app.models.case import Case

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("")
def stats(session: Session = Depends(get_session)):
    cases = session.exec(select(Case)).all()

    by_status: dict[str, int] = {}
    by_type: dict[str, int] = {}
    by_severity: dict[str, int] = {}

    for c in cases:
        by_status[c.status] = by_status.get(c.status, 0) + 1
        by_type[c.type] = by_type.get(c.type, 0) + 1
        by_severity[c.severity] = by_severity.get(c.severity, 0) + 1

    # last 10 cases
    latest = session.exec(select(Case).order_by(Case.created_at.desc()).limit(10)).all()

    return {
        "totals": {
            "cases": len(cases),
        },
        "by_status": by_status,
        "by_type": by_type,
        "by_severity": by_severity,
        "latest_cases": [c.model_dump() for c in latest],
    }