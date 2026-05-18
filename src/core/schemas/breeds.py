from uuid import UUID

from pydantic import Field

from core.entities.horse import HorseKindEnum
from core.schemas.baseschema import BaseSchema


class BreedOutDto(BaseSchema):
    """DTO для вывода породы."""

    id: UUID = Field(..., description="Идентификатор породы")
    name: str = Field(..., description="Название породы")
    short_name: str = Field(..., description="Короткое название породы")
    slug: str = Field(..., description="Slug")
    description: str | None = Field(None, description="Описание породы")
    kind: HorseKindEnum = Field(HorseKindEnum.HORSE, description="Вид породы")


class BreedOutWithPageDataDto(BreedOutDto):
    """DTO для вывода породы с page_data."""

    page_data: str


class BreedCreateDto(BaseSchema):
    """DTO для создания породы."""

    name: str = Field(..., description="Название породы")
    short_name: str | None = Field(default=None, description="Короткое название породы")
    slug: str | None = Field(
        None, description="Slug (опционально, генерируется автоматически)"
    )
    description: str | None = Field(None, description="Описание породы")
    page_data: str | None = Field(
        None, description="Данные страницы в формате HTML/текста"
    )
    kind: HorseKindEnum = Field(HorseKindEnum.HORSE, description="Вид породы")


class BreedUpdateDto(BaseSchema):
    """DTO для обновления породы."""

    name: str | None = Field(None, description="Название породы")
    short_name: str | None = Field(default=None, description="Короткое название породы")
    slug: str | None = Field(None, description="Slug")
    description: str | None = Field(None, description="Описание породы")
    page_data: str | None = Field(
        None, description="Данные страницы в формате HTML/текста"
    )
    kind: HorseKindEnum | None = Field(None, description="Вид породы")
