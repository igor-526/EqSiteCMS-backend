from datetime import datetime
from uuid import UUID

from pydantic import Field, computed_field, field_serializer

from core.entities.photos import Photo
from core.schemas.baseschema import BaseSchema
from settings import settings


class PhotoOutDto(BaseSchema):
    """DTO для вывода фотографии."""

    id: UUID
    name: str
    description: str | None
    path: str
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

    @property
    def url(self) -> str:
        """Вычисляемый URL для фотографии."""
        protocol = "https" if not settings.debug else "http"
        return f"{protocol}://{settings.cms_backend_domain}/media/{self.path}"

    class Config:
        from_attributes = True


class PhotoCreateDto(BaseSchema):
    """DTO для создания фотографии."""

    name: str | None = Field(
        None,
        description="Название фотографии (опционально, генерируется из имени файла)",
    )
    description: str | None = Field(None, description="Описание фотографии")


class PhotoUpdateDto(BaseSchema):
    """DTO для обновления фотографии."""

    name: str | None = Field(
        None, description="Название фотографии (пустая строка = сгенерировать из файла)"
    )
    description: str | None = Field(
        default=None,
        description="Описание фотографии (None = не обновлять, '' = пустая строка)",
    )


class PhotoOutShortDto(BaseSchema):
    """Упрощенный DTO для фотографии - только id, is_main и url."""

    id: UUID
    is_main: bool
    url: str

    @field_serializer("id")
    def serialize_id(self, value: UUID) -> str:
        return str(value)

    class Config:
        from_attributes = True


class PhotoBatchDeleteDto(BaseSchema):
    """DTO для массового удаления фотографий."""

    ids: list[UUID] = Field(..., description="Список UUID фотографий для удаления")
