from pydantic import Field

from .base import Entity, SlugMixin, TimeStampMixin


class Breed(Entity, TimeStampMixin, SlugMixin):
    """Порода лошади."""

    name: str = Field(
        default=...,
        description="Название породы",
        examples=["Арабская"],
    )
    short_name: str | None = Field(
        default=None,
        description="Короткое название породы",
        examples=["араб."],
    )
    description: str | None = Field(
        default=None,
        description="Описание породы",
        examples=["Быстрая и выносливая порода"],
    )
    page_data: str = Field(
        default="<div></div>",
        description="Данные страницы в формате HTML/текста",
        examples=["<div><p>Описание породы</p></div>"],
    )
