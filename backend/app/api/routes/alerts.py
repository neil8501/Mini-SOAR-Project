import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db.session import get_session
from app.models.alert import Alert

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/{alert_id}")
def get_alert(alert_id: uuid.UUID, session: Session = Depends(get_session)):
    alert = session.exec(select(Alert).where(Alert.id == alert_id)).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {
        "id": str(alert.id),
        "source": alert.source,
        "received_at": alert.received_at,
        "dedup_hash": alert.dedup_hash,
        "status": alert.status,
        "case_id": str(alert.case_id) if alert.case_id else None,
        "raw_payload": alert.raw_payload,
    }
