from uuid import UUID

from pydantic import Field

from .base import Entity, SlugMixin, TimeStampMixin
from .table import Table


class Price(Entity, TimeStampMixin, SlugMixin):
    """Ценовая позиция."""

    name: str = Field(
        default=...,
        description="Название цены",
        examples=["Абонемент на месяц"],
    )
    description: str | None = Field(
        default=None,
        description="Описание цены",
        examples=["Абонемент включает 8 занятий"],
    )
    page_data: str | None = Field(
        default=None,
        description="Данные страницы в формате HTML/текста",
        examples=["<p>Описание услуги</p>"],
    )
    price_tables: list[Table] = Field(
        default_factory=list,
        description="Таблицы цен в формате JSON",
        examples=[[{"name": "Таблица 1", "rows": []}]],
    )


class PriceGroup(Entity, TimeStampMixin):
    """Группа цен."""

    name: str = Field(
        default=...,
        description="Название группы",
        examples=["Основные услуги"],
    )
    description: str | None = Field(
        default=None,
        description="Описание группы",
        examples=["Основные услуги конюшни"],
    )


class PriceGroupsRelation(Entity):
    """Связь между ценой и группой."""

    price_id: UUID = Field(
        default=...,
        description="Идентификатор цены",
        examples=["123e4567-e89b-12d3-a456-426614174000"],
    )
    group_id: UUID = Field(
        default=...,
        description="Идентификатор группы",
        examples=["123e4567-e89b-12d3-a456-426614174000"],
    )


class PricePhotos(Entity):
    """Связь между ценой и фотографией."""

    price_id: UUID = Field(
        default=...,
        description="Идентификатор цены",
        examples=["123e4567-e89b-12d3-a456-426614174000"],
    )
    photo_id: UUID = Field(
        default=...,
        description="Идентификатор фотографии",
        examples=["123e4567-e89b-12d3-a456-426614174000"],
    )
    is_main: bool = Field(
        default=False,
        description="Является ли фотография главной",
        examples=[True],
    )
