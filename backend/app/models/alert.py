import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class Alert(SQLModel, table=True):
    __tablename__ = "alerts"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    source: str = Field(index=True)  # email/auth/network
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)

    raw_payload: Any = Field(sa_column=Column(JSONB, nullable=False))
    dedup_hash: str = Field(index=True)

    status: str = Field(default="new", index=True)  # new/processed
    case_id: Optional[uuid.UUID] = Field(default=None, index=True)
