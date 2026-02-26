import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class Ticket(SQLModel, table=True):
    __tablename__ = "tickets"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    case_id: uuid.UUID = Field(index=True)

    external_ref: Optional[str] = Field(default=None, index=True)
    summary: str
    status: str = Field(default="open", index=True)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
