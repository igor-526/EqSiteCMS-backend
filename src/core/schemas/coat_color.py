from uuid import UUID

from pydantic import Field

from core.schemas.baseschema import BaseSchema


class CoatColorOutDto(BaseSchema):
    """DTO для вывода масти."""

    id: UUID = Field(..., description="Идентификатор масти")
    name: str = Field(..., description="Название масти")
    short_name: str | None = Field(default=None, description="Короткое название масти")
    slug: str = Field(..., description="Slug")
    description: str | None = Field(None, description="Описание масти")


class CoatColorOutWithPageDataDto(CoatColorOutDto):
    """DTO для вывода масти с page_data."""

    page_data: str


class CoatColorCreateDto(BaseSchema):
    """DTO для создания масти."""

    name: str = Field(..., description="Название масти")
    short_name: str | None = Field(default=None, description="Короткое название масти")
    slug: str | None = Field(
        None, description="Slug (опционально, генерируется автоматически)"
    )
    description: str | None = Field(None, description="Описание масти")
    page_data: str | None = Field(
        None, description="Данные страницы в формате HTML/текста"
    )


class CoatColorUpdateDto(BaseSchema):
    """DTO для обновления масти."""

    name: str | None = Field(None, description="Название масти")
    short_name: str | None = Field(default=None, description="Короткое название масти")
    slug: str | None = Field(None, description="Slug")
    description: str | None = Field(None, description="Описание масти")
    page_data: str | None = Field(
        None, description="Данные страницы в формате HTML/текста"
    )
