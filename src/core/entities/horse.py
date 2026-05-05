from datetime import date
from enum import StrEnum, auto
from typing import Literal, TypeAlias
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from .base import Entity, SlugMixin, TimeStampMixin


class HorseKindEnum(StrEnum):
    """Вид лошади."""

    HORSE = auto()
    PONY = auto()


class HorseSexEnum(StrEnum):
    """Пол лошади."""

    MALE = auto()
    FEMALE = auto()
    GELD = auto()


class HorseDateModeEnum(StrEnum):
    """Режим отображения даты."""

    Y = auto()
    YM = auto()
    YMD = auto()
    HIDE = auto()


_HORSE_AVAILABLE_SORT_FIELDS: TypeAlias = Literal[
    "name",
    "breed_name",
    "coat_color_name",
    "kind",
    "height",
    "sex",
    "bdate",
    "ddate",
    "this_stable",
    "created_at",
    "-name",
    "-breed_name",
    "-coat_color_name",
    "-kind",
    "-height",
    "-sex",
    "-bdate",
    "-ddate",
    "-this_stable",
    "-created_at",
]


class Horse(Entity, TimeStampMixin, SlugMixin):
    """Лошадь."""

    name: str = Field(
        default=...,
        min_length=2,
        max_length=63,
        description="Имя лошади",
        examples=["Арабский жеребец"],
    )

    description: str | None = Field(
        default=None,
        max_length=511,
        description="Описание лошади",
        examples=["Красивый и быстрый жеребец"],
    )

    breed_id: UUID | None = Field(
        default=None,
        description="Идентификатор породы",
        examples=["123e4567-e89b-12d3-a456-426614174000"],
    )
    coat_color_id: UUID | None = Field(
        default=None,
        description="Идентификатор масти",
        examples=["123e4567-e89b-12d3-a456-426614174000"],
    )
    kind: HorseKindEnum = Field(
        default=HorseKindEnum.HORSE,
        description="Вид лошади",
        examples=[HorseKindEnum.HORSE.value, HorseKindEnum.PONY.value],
    )
    height: int | None = Field(
        default=None,
        ge=0,
        le=300,
        description="Рост в сантиметрах",
        examples=[165],
    )

    sex: HorseSexEnum = Field(
        default=HorseSexEnum.MALE,
        description="Пол лошади",
        examples=[
            HorseSexEnum.MALE.value,
            HorseSexEnum.FEMALE.value,
            HorseSexEnum.GELD.value,
        ],
    )
    bdate: date | None = Field(
        default=None,
        description="Дата рождения",
        examples=["2020-01-01"],
    )

    ddate: date | None = Field(
        default=None,
        description="Дата смерти",
        examples=["2023-01-01"],
    )
    bdate_mode: HorseDateModeEnum = Field(
        default=HorseDateModeEnum.HIDE,
        description="Режим отображения даты рождения",
        examples=[
            HorseDateModeEnum.Y.value,
            HorseDateModeEnum.YM.value,
            HorseDateModeEnum.YMD.value,
            HorseDateModeEnum.HIDE.value,
        ],
    )
    ddate_mode: HorseDateModeEnum = Field(
        default=HorseDateModeEnum.HIDE,
        description="Режим отображения даты смерти",
        examples=[
            HorseDateModeEnum.Y.value,
            HorseDateModeEnum.YM.value,
            HorseDateModeEnum.YMD.value,
            HorseDateModeEnum.HIDE.value,
        ],
    )
    horse_owner_id: UUID | None = Field(
        default=None,
        description="Идентификатор владельца",
        examples=["123e4567-e89b-12d3-a456-426614174000"],
    )
    this_stable: bool = Field(
        default=False,
        description="Лошадь находится на этой конюшек",
        examples=[True],
    )

    @field_validator("bdate", "ddate")
    @classmethod
    def validate_date_not_future(cls, v: date | None) -> date | None:
        if v is not None and v > date.today():
            raise ValueError("Дата не может быть в будущем")
        return v

    @model_validator(mode="after")
    def validate_dates_consistency(self) -> "Horse":
        if self.bdate is not None and self.ddate is not None:
            if self.bdate > self.ddate:
                raise ValueError("Дата рождения не может быть позже даты смерти")
        return self


class HorseChildren(Entity, TimeStampMixin):
    """Связь родитель-потомок между лошадьми."""

    horse_id: UUID = Field(
        default=...,
        description="Идентификатор родительской лошади",
        examples=["123e4567-e89b-12d3-a456-426614174000"],
    )
    child_id: UUID = Field(
        default=...,
        description="Идентификатор дочерней лошади",
        examples=["123e4567-e89b-12d3-a456-426614174000"],
    )


class HorsePhotos(Entity, TimeStampMixin):
    """Связь между лошадью и фотографией."""

    horse_id: UUID = Field(
        default=...,
        description="Идентификатор лошади",
        examples=["123e4567-e89b-12d3-a456-426614174000"],
    )
    photo_id: UUID = Field(
        default=...,
        description="Идентификатор фотографии",
        examples=["123e4567-e89b-12d3-a456-426614174000"],
    )
    is_main: bool = Field(
        default=False,
        description="Является ли фотография главной",
        examples=[True],
    )
