from uuid import UUID

from pydantic import Field

from core.entities.horse_owner import HorseOwnerType
from core.schemas.baseschema import BaseSchema


class HorseOwnerOutDto(BaseSchema):
    """DTO для вывода владельца."""

    id: UUID
    name: str
    description: str | None
    type: HorseOwnerType
    address: str | None
    phone_numbers: list[str]


class HorseOwnerCreateInDto(BaseSchema):
    """DTO для создания владельца."""

    name: str = Field(..., description="Имя владельца")
    description: str | None = Field(None, description="Описание владельца")
    type: HorseOwnerType = Field(HorseOwnerType.person, description="Тип владельца")
    address: str | None = Field(None, description="Адрес владельца")
    phone_numbers: list[str] = Field(
        default_factory=list, description="Список телефонных номеров"
    )


class HorseOwnerUpdateDto(BaseSchema):
    """DTO для обновления владельца."""

    name: str | None = Field(None, description="Имя владельца")
    description: str | None = Field(None, description="Описание владельца")
    type: HorseOwnerType | None = Field(None, description="Тип владельца")
    address: str | None = Field(None, description="Адрес владельца")
    phone_numbers: list[str] | None = Field(
        None, description="Список телефонных номеров"
    )
