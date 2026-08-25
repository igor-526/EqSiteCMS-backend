from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import ConfigDict, Field

from core.schemas.baseschema import BaseSchema


class CallbackRequestOutDto(BaseSchema):
    """DTO для ответа на создание заявки на обратный звонок."""

    id: UUID = Field(..., description="Идентификатор заявки")
    name: str | None = Field(default=None, description="Имя заявителя")
    comment: str | None = Field(default=None, description="Комментарий заявителя")
    phone: str = Field(..., description="Контактный номер телефона")
    status: int = 1
    is_spam: bool = False
    notifications_delivered: bool = False
    created_at: datetime
    updated_at: datetime | None = None


class CallbackRequestCreateDto(BaseSchema):
    """DTO для создания заявки на обратный звонок."""

    name: str | None = Field(default=None, max_length=127, description="Имя заявителя")
    comment: str | None = Field(
        default=None, max_length=2000, description="Комментарий заявителя"
    )
    phone: str = Field(
        ..., min_length=1, max_length=63, description="Контактный номер телефона"
    )


class CallbackRequestStatusOutDto(BaseSchema):
    id: int
    name: str
    color: str


class CallbackRequestStatusInDto(BaseSchema):
    model_config = ConfigDict(extra="forbid")
    status: int


class CallbackRequestSpamInDto(BaseSchema):
    model_config = ConfigDict(extra="forbid")
    is_spam: bool


class CallbackRequestDeliveryInDto(BaseSchema):
    model_config = ConfigDict(extra="forbid")
    notifications_delivered: bool


class CallbackRequestSortField(StrEnum):
    CREATED_AT = "created_at"
    STATUS = "status"


class SortDirection(StrEnum):
    ASC = "asc"
    DESC = "desc"


class CallbackRequestPageOutDto(BaseSchema):
    items: list[CallbackRequestOutDto]
    total: int
    limit: int
    offset: int
