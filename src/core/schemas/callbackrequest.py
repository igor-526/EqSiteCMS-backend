from uuid import UUID

from pydantic import Field

from core.schemas.baseschema import BaseSchema


class CallbackRequestOutDto(BaseSchema):
    """DTO для ответа на создание заявки на обратный звонок."""

    id: UUID = Field(..., description="Идентификатор заявки")
    name: str | None = Field(default=None, description="Имя заявителя")
    comment: str | None = Field(default=None, description="Комментарий заявителя")
    phone: str = Field(..., description="Контактный номер телефона")


class CallbackRequestCreateDto(BaseSchema):
    """DTO для создания заявки на обратный звонок."""

    name: str | None = Field(default=None, description="Имя заявителя")
    comment: str | None = Field(default=None, description="Комментарий заявителя")
    phone: str = Field(..., description="Контактный номер телефона")
