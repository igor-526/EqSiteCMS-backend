from uuid import UUID

from pydantic import BaseModel, ConfigDict, StrictBool


class NotificationSettingWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: StrictBool


class NotificationSettingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: UUID
    event_code: str
    event_name: str
    event_description: str | None
    channel_code: str
    channel_name: str
    enabled: bool
