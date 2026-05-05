from datetime import datetime
from uuid import UUID

from pydantic import Field, field_serializer

from core.entities.horse_service import HorseServiceEntity
from core.entities.price import PriceFormatter
from core.schemas.baseschema import BaseSchema


class HorseServiceOutDto(BaseSchema):
    """DTO для вывода услуги."""

    id: UUID
    name: str
    slug: str
    description: str | None
    price: int
    price_formatter: PriceFormatter
    created_at: datetime
    updated_at: datetime | None

    @field_serializer("id")
    def serialize_id(self, value: UUID) -> str:
        return str(value)

    @field_serializer("price_formatter")
    def serialize_price_formatter(self, value: PriceFormatter) -> str:
        return str(value)

    @field_serializer("created_at", "updated_at")
    def serialize_datetime(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.isoformat()


class HorseServiceOutWithPageDataDto(HorseServiceOutDto):
    """DTO для вывода услуги с page_data."""

    page_data: str


class HorseServiceCreateDto(BaseSchema):
    """DTO для создания услуги."""

    name: str = Field(..., description="Название услуги")
    slug: str | None = Field(
        None, description="Slug (опционально, генерируется автоматически)"
    )
    description: str | None = Field(None, description="Описание услуги")
    price: int = Field(..., description="Цена услуги в копейках")
    price_formatter: PriceFormatter = Field(
        PriceFormatter.equal, description="Формат отображения цены"
    )
    page_data: str | None = Field(
        None, description="Данные страницы в формате HTML/текста"
    )


class HorseServiceUpdateDto(BaseSchema):
    """DTO для обновления услуги."""

    name: str | None = Field(None, description="Название услуги")
    slug: str | None = Field(None, description="Slug")
    description: str | None = Field(None, description="Описание услуги")
    price: int | None = Field(None, description="Цена услуги в копейках")
    price_formatter: PriceFormatter | None = Field(
        None, description="Формат отображения цены"
    )
    page_data: str | None = Field(
        None, description="Данные страницы в формате HTML/текста"
    )
