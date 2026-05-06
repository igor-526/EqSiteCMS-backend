from datetime import datetime
from uuid import UUID

from pydantic import ConfigDict, Field, field_serializer

from core.entities.site_settings import SiteSettingType
from core.schemas.baseschema import BaseSchema


class SiteSettingOutDto(BaseSchema):
    """DTO для вывода настройки."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    key: str
    value: str
    name: str
    description: str | None
    type: str
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


class SiteSettingSimpleOutDto(BaseSchema):
    """DTO для вывода настройки без пагинации (только key, value, type)."""

    model_config = ConfigDict(from_attributes=True)

    key: str
    value: str
    type: str


class SiteSettingCreateDto(BaseSchema):
    """DTO для создания настройки."""

    key: str = Field(..., description="Ключ настройки")
    value: str = Field(..., description="Значение настройки (всегда строка)")
    name: str = Field(..., description="Человекочитаемое название настройки")
    description: str | None = Field(None, description="Описание настройки")
    type: SiteSettingType = Field(..., description="Тип настройки")


class SiteSettingUpdateDto(BaseSchema):
    """DTO для обновления настройки."""

    key: str | None = Field(None, description="Ключ настройки")
    value: str | None = Field(None, description="Значение настройки (всегда строка)")
    name: str | None = Field(None, description="Человекочитаемое название настройки")
    description: str | None = Field(None, description="Описание настройки")
    type: SiteSettingType | None = Field(None, description="Тип настройки")
