from enum import StrEnum, auto

from pydantic import Field

from .base import Entity, TimeStampMixin


class HorseOwnerType(StrEnum):
    """Тип владельца."""

    person = auto()
    company = auto()


class HorseOwner(Entity, TimeStampMixin):
    """Владелец лошади."""

    name: str = Field(
        default=...,
        description="Имя владельца",
        examples=["Иванов Иван Иванович"],
    )
    description: str | None = Field(
        default=None,
        description="Описание владельца",
        examples=["Опытный коневод"],
    )
    type: HorseOwnerType = Field(
        default=HorseOwnerType.person,
        description="Тип владельца",
        examples=[HorseOwnerType.person],
    )
    address: str | None = Field(
        default=None,
        description="Адрес владельца",
        examples=["г. Москва, ул. Ленина, д. 1"],
    )
    phone_numbers: list[str] = Field(
        default_factory=list,
        description="Список телефонных номеров",
        examples=[["+7 (999) 123-45-67"]],
    )
