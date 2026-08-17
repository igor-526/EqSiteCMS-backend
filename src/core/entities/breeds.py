from uuid import UUID

from pydantic import Field

from .base import Entity, SlugMixin, TimeStampMixin
from .breed_groups import BreedGroupIdentity
from .horse import HorseKindEnum


class Breed(Entity, TimeStampMixin, SlugMixin):
    """Порода лошади."""

    equestrian_id: UUID = Field(default=...)
    breed_group_id: UUID | None = Field(default=None)
    group: BreedGroupIdentity | None = Field(default=None)
    name: str = Field(
        default=...,
        description="Название породы",
        examples=["Арабская"],
    )
    short_name: str = Field(
        default=...,
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
    kind: HorseKindEnum = Field(
        default=HorseKindEnum.HORSE,
        description="Вид породы",
        examples=[HorseKindEnum.HORSE.value, HorseKindEnum.PONY.value],
    )
