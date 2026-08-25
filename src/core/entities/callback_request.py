from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class CallbackRequestStatus(BaseModel):
    id: int
    name: str
    color: str


class CallbackRequest(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    equestrian_id: UUID
    name: str | None = None
    phone: str
    comment: str | None = None
    status: int = 1
    is_spam: bool = False
    notifications_delivered: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime | None = None
