from datetime import datetime
from uuid import UUID

from pydantic import ConfigDict, Field, field_serializer

from core.schemas.baseschema import BaseSchema


class PhotoOutDto(BaseSchema):
    """DTO для вывода фотографии."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    path: str
    url: str = Field(
        ..., description="Публичный URL, собирается на adapter/API-границе"
    )
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


class PhotoUploadDto(BaseSchema):
    """DTO для файла фотографии или видео, подготовленного API-слоем."""

    filename: str
    content: bytes
    content_type: str | None = None


class PhotoOutShortDto(BaseSchema):
    """Упрощенный DTO для фотографии - только id, is_main и url."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    is_main: bool
    url: str

    @field_serializer("id")
    def serialize_id(self, value: UUID) -> str:
        return str(value)


class PhotoBatchDeleteDto(BaseSchema):
    """DTO для массового удаления фотографий."""

    ids: list[UUID] = Field(..., description="Список UUID фотографий для удаления")
