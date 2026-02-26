import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class TimelineEvent(SQLModel, table=True):
    __tablename__ = "timeline_events"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    case_id: uuid.UUID = Field(index=True)
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)

    event_type: str = Field(index=True)  # ingest/extract/enrich/score/playbook/action
    message: str
    details: Any = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False))
