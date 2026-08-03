from datetime import datetime
from uuid import UUID

from pydantic import Field, field_serializer

from core.entities.price import PriceFormatter
from core.schemas.baseschema import BaseSchema


class HorseServiceRelationOutDto(BaseSchema):
    """DTO для вывода связи лошадь-услуга с учётом override."""

    id: UUID = Field(..., description="Идентификатор связи")
    created_at: datetime = Field(..., description="Момент создания связи")
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

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        return value.isoformat()


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


class HorseServiceAvailableOutDto(BaseSchema):
    """DTO услуги, доступной для создания связи."""

    id: UUID = Field(..., description="Идентификатор услуги")
    name: str = Field(..., description="Название услуги")
    slug: str = Field(..., description="Slug услуги")
    description: str | None = Field(None, description="Описание услуги")
    price: int = Field(..., description="Цена в копейках")
    price_formatter: PriceFormatter = Field(..., description="Формат цены")

    @field_serializer("id")
    def serialize_available_id(self, value: UUID) -> str:
        return str(value)

    @field_serializer("price_formatter")
    def serialize_available_price_formatter(self, value: PriceFormatter) -> str:
        return str(value)
