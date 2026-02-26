import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class Case(SQLModel, table=True):
    __tablename__ = "cases"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    title: str
    type: str = Field(index=True)  # phishing/login/beacon
    severity: str = Field(default="low", index=True)  # low/med/high/critical
    status: str = Field(default="open", index=True)  # open/investigating/contained/closed
    score: int = Field(default=0, index=True)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
