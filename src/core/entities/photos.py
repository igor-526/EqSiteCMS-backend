from pydantic import Field

from .base import Entity, TimeStampMixin


class Photo(Entity, TimeStampMixin):
    """Фотография."""

    name: str = Field(
        default=...,
        description="Название фотографии",
        examples=["Фото 1"],
    )
    description: str | None = Field(
        default=None,
        description="Описание фотографии",
        examples=["Главная фотография"],
    )
    path: str = Field(
        default=...,
        description="Путь к файлу фотографии",
        examples=["/photos/horse1.jpg"],
    )
