from uuid import UUID

from pydantic import Field

from .base import Entity, SlugMixin, TimeStampMixin


class CoatColor(Entity, TimeStampMixin, SlugMixin):
    """Масть лошади."""

    equestrian_id: UUID = Field(default=...)
    name: str = Field(
        default=...,
        description="Название масти",
        examples=["Гнедая"],
    )
    short_name: str = Field(
        default=...,
        description="Короткое название масти",
        examples=["гн."],
    )
    description: str | None = Field(
        default=None,
        description="Описание масти",
        examples=["Коричневая масть с черными гривой и хвостом"],
    )
    page_data: str = Field(
        default="<div></div>",
        description="Данные страницы в формате HTML/текста",
        examples=["<div><p>Описание масти</p></div>"],
    )
