from datetime import datetime
from uuid import UUID

from pydantic import ConfigDict, Field, field_serializer

from core.schemas.baseschema import BaseSchema
from core.schemas.photos import PhotoOutShortDto


class NewsOutDto(BaseSchema):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    snippet: str | None
    content: str
    published_at: datetime
    is_deleted: bool
    deleted_at: datetime | None
    photos: list[PhotoOutShortDto]
    created_at: datetime
    updated_at: datetime | None

    @field_serializer("id")
    def serialize_id(self, value: UUID) -> str:
        return str(value)

    @field_serializer("created_at", "updated_at", "published_at", "deleted_at")
    def serialize_datetime(self, value: datetime | None) -> str | None:
        if value is None:
            return None
        return value.isoformat()


class NewsPublicOutDto(BaseSchema):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    snippet: str | None
    published_at: datetime
    photos: list[PhotoOutShortDto]

    @field_serializer("id")
    def serialize_id(self, value: UUID) -> str:
        return str(value)

    @field_serializer("published_at")
    def serialize_datetime(self, value: datetime) -> str:
        return value.isoformat()


class NewsCreateDto(BaseSchema):
    name: str = Field(..., description="Название новости (1-63 символа)")
    snippet: str | None = Field(
        None, description="Сниппет (None = автогенерация из content)"
    )
    content: str = Field("", description="HTML-содержимое")
    published_at: datetime = Field(..., description="Дата публикации (ISO 8601 с TZ)")
    photo_ids: list[UUID] = Field(default_factory=list, description="UUID фотографий")
    main_photo_id: UUID | None = Field(None, description="UUID главной фотографии")


class NewsUpdateDto(BaseSchema):
    name: str | None = Field(None)
    snippet: str | None = Field(None)
    content: str | None = Field(None)
    published_at: datetime | None = Field(None)


class NewsPhotosUpdateDto(BaseSchema):
    photo_ids: list[UUID] | None = Field(None, description="Список UUID фотографий")
    main: UUID | None = Field(None, description="UUID главной фотографии")
