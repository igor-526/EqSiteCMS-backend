import uuid

from pydantic import BaseModel, Field


class MessagingEvent(BaseModel):
    event_id: uuid.UUID = Field(default_factory=uuid.uuid4, description="UUID события")
    event_subject: str = Field(
        default="site.callback.requested", description="Тип события"
    )
