from uuid import UUID

from pydantic import Field

from .base import Entity, SlugMixin, TimeStampMixin
from .price import PriceFormatter


class HorseServiceEntity(Entity, TimeStampMixin, SlugMixin):
    """Услуга для лошади."""

    name: str = Field(
        default=...,
        description="Название услуги",
        examples=["Разведение"],
    )
    description: str | None = Field(
        default=None,
        description="Описание услуги",
        examples=["Разведение лошадей"],
    )
    price: int = Field(
        default=...,
        description="Цена услуги в копейках",
        examples=[500000],
    )
    price_formatter: PriceFormatter = Field(
        default=PriceFormatter.equal,
        description="Формат отображения цены",
        examples=[PriceFormatter.equal],
    )
    page_data: str = Field(
        default="<div></div>",
        description="Данные страницы в формате HTML/текста",
        examples=["<div><p>Описание услуги</p></div>"],
    )


class HorseServiceRelations(Entity):
    """Связь между лошадью и услугой с возможностью переопределения параметров."""

    horse_id: UUID = Field(
        default=...,
        description="Идентификатор лошади",
        examples=["123e4567-e89b-12d3-a456-426614174000"],
    )
    service_id: UUID = Field(
        default=...,
        description="Идентификатор услуги",
        examples=["123e4567-e89b-12d3-a456-426614174000"],
    )
    description_override: str | None = Field(
        default=None,
        description="Переопределенное описание",
        examples=["Особое описание для этой лошади"],
    )
    price_override: int | None = Field(
        default=None,
        description="Переопределенная цена в копейках",
        examples=[600000],
    )
    price_formatter_override: PriceFormatter | None = Field(
        default=None,
        description="Переопределенный формат отображения цены",
        examples=[PriceFormatter.equal],
    )
