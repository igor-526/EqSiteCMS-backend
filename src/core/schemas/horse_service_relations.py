from datetime import datetime
from uuid import UUID

from pydantic import Field, field_serializer

from core.entities.price import PriceFormatter
from core.schemas.baseschema import BaseSchema


class HorseServiceRelationOutDto(BaseSchema):
    """DTO для вывода связи лошадь-услуга с учётом override."""

    id: UUID = Field(..., description="Идентификатор связи")
    service_id: UUID = Field(..., description="Идентификатор услуги")
    name: str = Field(..., description="Название услуги")
    slug: str = Field(..., description="Slug услуги")
    description: str | None = Field(None, description="Описание (override или дефолт)")
    price: int = Field(..., description="Цена в копейках (override или дефолт)")
    price_formatter: PriceFormatter = Field(
        ..., description="Формат цены (override или дефолт)"
    )

    @field_serializer("id", "service_id")
    def serialize_id(self, value: UUID) -> str:
        return str(value)

    @field_serializer("price_formatter")
    def serialize_price_formatter(self, value: PriceFormatter) -> str:
        return str(value)


class HorseServiceRelationCreateDto(BaseSchema):
    """DTO для создания связи лошадь-услуга."""

    service_id: UUID = Field(..., description="Идентификатор услуги")
    description_override: str | None = Field(
        None, description="Переопределённое описание"
    )
    price_override: int | None = Field(None, description="Переопределённая цена")
    price_formatter_override: PriceFormatter | None = Field(
        None, description="Переопределённый формат цены"
    )


class HorseServiceRelationUpdateDto(BaseSchema):
    """DTO для обновления связи лошадь-услуга."""

    description_override: str | None = Field(
        None, description="Переопределённое описание"
    )
    price_override: int | None = Field(None, description="Переопределённая цена")
    price_formatter_override: PriceFormatter | None = Field(
        None, description="Переопределённый формат цены"
    )
