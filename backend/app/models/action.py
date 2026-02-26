import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class Action(SQLModel, table=True):
    __tablename__ = "actions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    case_id: uuid.UUID = Field(index=True)

    action_type: str = Field(index=True)  # block_domain/block_ip/notify/create_ticket/disable_user
    params: Any = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False))

    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    finished_at: Optional[datetime] = Field(default=None, index=True)

    success: Optional[bool] = Field(default=None, index=True)
    result: Any = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False))
