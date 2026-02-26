import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db.session import get_session
from app.models.ticket import Ticket

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.get("/{ticket_id}")
def get_ticket(ticket_id: uuid.UUID, session: Session = Depends(get_session)):
    t = session.exec(select(Ticket).where(Ticket.id == ticket_id)).first()
    if not t:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return t.model_dump()
