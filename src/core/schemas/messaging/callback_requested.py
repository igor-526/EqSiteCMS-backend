import uuid

from pydantic import ConfigDict, Field

from core.schemas.messaging.base_event_data import MessagingBaseEventData


class CallbackRequestedData(MessagingBaseEventData):
    equestrian_id: uuid.UUID = Field(..., description="UUID конюшни")
    callback_request_id: uuid.UUID = Field(
        ..., description="UUID заявки на обратный звонок"
    )
    name: str | None = Field(default=None, description="Имя заявителя")
    comment: str | None = Field(default=None, description="Комментарий заявителя")
    phone: str = Field(..., description="Контактный номер телефона")

    model_config = ConfigDict(extra="forbid")
