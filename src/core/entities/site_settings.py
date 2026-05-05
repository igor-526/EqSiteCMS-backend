from enum import StrEnum, auto

from pydantic import Field

from .base import Entity, TimeStampMixin


class SiteSettingType(StrEnum):
    """Тип настройки сайта."""

    string = auto()
    number = auto()
    float = auto()
    boolean = auto()
    object = auto()
    date = auto()
    time = auto()
    datetime = auto()


class SiteSetting(Entity, TimeStampMixin):
    """Настройка сайта."""

    key: str = Field(
        default=...,
        description="Ключ настройки",
        examples=["site_name", "site_description", "site_logo", "site_favicon"],
    )
    value: str = Field(
        default=...,
        description="Значение настройки",
        examples=["Моя Конюшня"],
    )
    name: str = Field(
        default=...,
        description="Человекочитаемое настройки",
        examples=["Название сайта"],
    )
    description: str | None = Field(
        default=None,
        description="Описание настройки",
        examples=["Основное название сайта"],
    )
    type: str = Field(
        default=...,
        description="Тип настройки (хранится как строка)",
        examples=["string"],
    )
