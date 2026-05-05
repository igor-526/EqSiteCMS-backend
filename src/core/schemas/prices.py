from datetime import datetime
from uuid import UUID

from pydantic import Field, field_serializer

from core.entities.prices import Price, PriceGroup
from core.entities.table import Table as TableEntity
from core.schemas.baseschema import BaseSchema
from core.schemas.photos import PhotoOutShortDto


class PriceGroupOutDto(BaseSchema):
    """DTO для вывода группы цен."""

    id: UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime | None

    @field_serializer("id")
    def serialize_id(self, value: UUID) -> str:
        return str(value)

    @field_serializer("created_at", "updated_at")
    def serialize_datetime(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.isoformat()

    class Config:
        from_attributes = True


class PriceGroupCreateDto(BaseSchema):
    """DTO для создания группы цен."""

    name: str = Field(..., description="Название группы")
    description: str | None = Field(None, description="Описание группы")


class PriceGroupUpdateDto(BaseSchema):
    """DTO для обновления группы цен."""

    name: str | None = Field(None, description="Название группы")
    description: str | None = Field(None, description="Описание группы")


class PriceGroupSimpleDto(BaseSchema):
    """Упрощенный DTO группы для вложенных объектов."""

    id: UUID
    name: str

    @field_serializer("id")
    def serialize_id(self, value: UUID) -> str:
        return str(value)

    class Config:
        from_attributes = True


class PriceOutDto(BaseSchema):
    """DTO для вывода цены."""

    id: UUID
    name: str
    slug: str | None
    description: str | None
    photos: list[PhotoOutShortDto]
    groups: list[PriceGroupSimpleDto]
    created_at: datetime
    updated_at: datetime | None

    @field_serializer("id")
    def serialize_id(self, value: UUID) -> str:
        return str(value)

    @field_serializer("created_at", "updated_at")
    def serialize_datetime(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.isoformat()

    class Config:
        from_attributes = True


class PriceOutWithPageDataDto(PriceOutDto):
    """DTO для вывода цены с page_data."""

    page_data: str


class PriceOutWithTablesDto(PriceOutWithPageDataDto):
    """DTO для вывода цены с таблицами."""

    price_tables: list[TableEntity]


class PriceCreateDto(BaseSchema):
    """DTO для создания цены."""

    name: str = Field(..., description="Название цены")
    description: str | None = Field(None, description="Описание цены")
    groups: list[UUID] = Field(default_factory=list, description="Список UUID групп")
    page_data: str | None = Field(
        None, description="Данные страницы в формате HTML/текста"
    )
    price_tables: list[TableEntity] | None = Field(None, description="Таблицы цен")


class PriceUpdateDto(BaseSchema):
    """DTO для обновления цены."""

    name: str | None = Field(None, description="Название цены")
    description: str | None = Field(None, description="Описание цены")
    groups: list[UUID] | None = Field(
        None, description="Список UUID групп (заменяет все связи)"
    )
    page_data: str | None = Field(
        None, description="Данные страницы в формате HTML/текста"
    )
    price_tables: list[TableEntity] | None = Field(None, description="Таблицы цен")


class PricePhotosUpdateDto(BaseSchema):
    """DTO для обновления фотографий цены."""

    photo_ids: list[UUID] | None = Field(None, description="Список UUID фотографий")
    main: UUID | None = Field(None, description="UUID главной фотографии")
