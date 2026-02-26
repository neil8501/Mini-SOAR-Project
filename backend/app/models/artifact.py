import uuid
from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class Artifact(SQLModel, table=True):
    __tablename__ = "artifacts"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    case_id: uuid.UUID = Field(index=True)

    type: str = Field(index=True)   # url/domain/ip/email/user/hash
    value: str = Field(index=True)

    first_seen: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
