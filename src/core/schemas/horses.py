from datetime import date, datetime
from uuid import UUID

from pydantic import Field, computed_field, model_validator

from core.entities import HorseDateModeEnum, HorseKindEnum, HorseSexEnum
from core.entities.horse import Horse
from core.schemas.baseschema import BaseSchema
from core.schemas.breeds import BreedOutDto
from core.schemas.coat_color import CoatColorOutDto
from core.schemas.horse_owner import HorseOwnerOutDto
from core.schemas.horse_service import HorseServiceOutDto
from core.schemas.photos import PhotoOutShortDto


class HorseOutDto(BaseSchema):
    """DTO для вывода лошади."""

    id: UUID = Field(..., description="Идентификатор лошади")
    slug: str = Field(..., description="Slug лошади")
    name: str = Field(
        default=...,
        description="Имя лошади",
    )

    description: str | None = Field(
        default=None,
        description="Описание лошади",
    )
    breed: BreedOutDto | None = Field(
        default=None,
        description="Порода лошади",
    )
    coat_color: CoatColorOutDto | None = Field(
        default=None,
        description="Масть лошади",
    )
    kind: HorseKindEnum = Field(
        default=HorseKindEnum.HORSE,
        description="Вид лошади",
    )
    height: int | None = Field(
        default=None,
        description="Рост в сантиметрах",
    )
    sex: HorseSexEnum = Field(
        default=HorseSexEnum.MALE,
        description="Пол лошади",
    )
    bdate: date | None = Field(
        default=None,
        description="Дата рождения",
    )
    ddate: date | None = Field(
        default=None,
        description="Дата смерти",
    )
    bdate_mode: HorseDateModeEnum = Field(
        default=HorseDateModeEnum.HIDE,
        description="Режим отображения даты рождения",
    )
    ddate_mode: HorseDateModeEnum = Field(
        default=HorseDateModeEnum.HIDE,
        description="Режим отображения даты смерти",
    )
    horse_owner: HorseOwnerOutDto | None = Field(
        default=None,
        description="Владелец лошади",
    )
    photos: list[PhotoOutShortDto] = Field(
        default_factory=list, description="Фотографии лошади"
    )
    services: list[HorseServiceOutDto] = Field(
        default_factory=list, description="Услуги лошади"
    )
    this_stable: bool = Field(
        default=False,
        description="Лошадь находится на этой конюшке",
    )

    @computed_field
    def bdate_formatted(self) -> str | None:
        if self.bdate is None:
            return None
        match self.bdate_mode:
            case HorseDateModeEnum.Y:
                return self.bdate.strftime("%Y")
            case HorseDateModeEnum.YM:
                return self.bdate.strftime("%m.%Y")
            case HorseDateModeEnum.YMD:
                return self.bdate.strftime("%d.%m.%Y")
            case HorseDateModeEnum.HIDE:
                return None

    @computed_field
    def ddate_formatted(self) -> str | None:
        if self.ddate is None:
            return None
        match self.ddate_mode:
            case HorseDateModeEnum.Y:
                return self.ddate.strftime("%Y")
            case HorseDateModeEnum.YM:
                return self.ddate.strftime("%m.%Y")
            case HorseDateModeEnum.YMD:
                return self.ddate.strftime("%d.%m.%Y")
            case HorseDateModeEnum.HIDE:
                return None

    @computed_field
    def age(self) -> int | None:
        if self.bdate is None or self.ddate is None:
            return None
        days = (self.ddate - self.bdate).days
        return int(days / 365.25)


class HorsePedigree(BaseSchema):
    """DTO для вывода родословной лошади (sire/dam рекурсивно с родословной по поколениям)."""

    sire: "HorseWithPedigreeOutDto | HorseOutDto | None" = Field(
        default=None,
        description="Родитель-самец",
    )
    dam: "HorseWithPedigreeOutDto | HorseOutDto | None" = Field(
        default=None,
        description="Родитель-самочка",
    )
    foals: list[HorseOutDto] = Field(default_factory=list, description="Потомки лошади")


class HorseWithPedigreeOutDto(HorseOutDto, BaseSchema):
    """DTO для вывода лошади с родословной."""

    pedigree: HorsePedigree = Field(..., description="Родословная")


HorsePedigree.model_rebuild()


class HorseCreateInDto(BaseSchema):
    """DTO для создания лошади."""

    name: str = Field(
        default=...,
        description="Имя лошади",
    )

    description: str | None = Field(
        default=None,
        description="Описание лошади",
    )
    breed_id: UUID | None = Field(
        default=None,
        description="Идентификатор породы",
    )
    coat_color_id: UUID | None = Field(
        default=None,
        description="Идентификатор масти",
    )
    kind: HorseKindEnum = Field(
        default=HorseKindEnum.HORSE,
        description="Вид лошади",
    )
    height: int | None = Field(
        default=None,
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
    )
    ddate: date | None = Field(
        default=None,
        description="Дата смерти",
    )
    bdate_mode: HorseDateModeEnum = Field(
        default=HorseDateModeEnum.HIDE,
        description="Режим отображения даты рождения",
    )
    ddate_mode: HorseDateModeEnum = Field(
        default=HorseDateModeEnum.HIDE,
        description="Режим отображения даты смерти",
    )
    horse_owner_id: UUID | None = Field(
        default=None,
        description="Идентификатор владельца",
    )
    this_stable: bool = Field(
        default=False,
        description="Лошадь находится на этой конюшке",
    )


class HorseUpdateInDto(BaseSchema):
    """DTO для создания лошади."""

    name: str | None = Field(
        default=None,
        description="Имя лошади",
    )

    description: str | None = Field(
        default=None,
        description="Описание лошади",
    )
    breed_id: UUID | None = Field(
        default=None,
        description="Идентификатор породы",
    )
    coat_color_id: UUID | None = Field(
        default=None,
        description="Идентификатор масти",
    )
    kind: HorseKindEnum | None = Field(
        default=None,
        description="Вид лошади",
    )
    height: int | None = Field(
        default=None,
        description="Рост в сантиметрах",
    )
    sex: HorseSexEnum | None = Field(
        default=None,
        description="Пол лошади",
    )
    bdate: date | None = Field(
        default=None,
        description="Дата рождения",
    )
    ddate: date | None = Field(
        default=None,
        description="Дата смерти",
    )
    bdate_mode: HorseDateModeEnum | None = Field(
        default=None,
        description="Режим отображения даты рождения",
    )
    ddate_mode: HorseDateModeEnum | None = Field(
        default=None,
        description="Режим отображения даты смерти",
    )
    horse_owner_id: UUID | None = Field(
        default=None,
        description="Идентификатор владельца",
    )
    this_stable: bool | None = Field(
        default=None,
        description="Лошадь находится на этой конюшке",
    )


class HorseSetPedigreeInDto(BaseSchema):
    """DTO для установки родословной лошади."""

    sire_id: UUID | None = Field(
        default=None,
        description="Идентификатор отца",
    )
    dam_id: UUID | None = Field(
        default=None,
        description="Идентификатор матери",
    )
    foals: list[UUID] | None = Field(
        default=None,
        description="Идентификаторы потомков",
    )


class SetPedigreeEntities(BaseSchema):
    """Набор лошадей для установки родословной с валидацией по тем же правилам, что и поиск доступных."""

    target_horse: Horse = Field(..., description="Целевая лошадь")
    sire: Horse | None = Field(default=None, description="Отец")
    dam: Horse | None = Field(default=None, description="Мать")
    foals: list[Horse] | None = Field(default=None, description="Потомки")

    @model_validator(mode="after")
    def validate_pedigree(self) -> "SetPedigreeEntities":
        target = self.target_horse
        if self.sire is None and self.dam is None and self.foals is None:
            raise ValueError("Необходимо указать хотя бы одного родителя или потомка")
        if self.sire is not None:
            if self.sire.id == target.id:
                raise ValueError("Отец не может совпадать с целевой лошадью")
            if self.sire.sex != HorseSexEnum.MALE:
                raise ValueError("Отец должен быть мужского пола")
            if self.sire.kind != target.kind:
                raise ValueError("Отец должен быть того же вида, что и целевая лошадь")
            if target.bdate is not None and self.sire.bdate is not None:
                if self.sire.bdate > target.bdate:
                    raise ValueError(
                        "Дата рождения отца не может быть позже даты рождения целевой лошади"
                    )
        if self.dam is not None:
            if self.dam.id == target.id:
                raise ValueError("Мать не может совпадать с целевой лошадью")
            if self.dam.sex != HorseSexEnum.FEMALE:
                raise ValueError("Мать должна быть женского пола")
            if self.dam.kind != target.kind:
                raise ValueError("Мать должна быть того же вида, что и целевая лошадь")
            if target.bdate is not None:
                if self.dam.bdate is not None and self.dam.bdate > target.bdate:
                    raise ValueError(
                        "Дата рождения матери не может быть позже даты рождения целевой лошади"
                    )
                if self.dam.ddate is not None and self.dam.ddate < target.bdate:
                    raise ValueError(
                        "Дата смерти матери не может быть раньше даты рождения целевой лошади"
                    )
        if self.foals:
            for foal in self.foals:
                if foal.id == target.id:
                    raise ValueError("Ребёнок не может совпадать с целевой лошадью")
                if foal.kind != target.kind:
                    raise ValueError(
                        "Все дети должны быть того же вида, что и целевая лошадь"
                    )
                if target.bdate is not None and foal.bdate is not None:
                    if foal.bdate < target.bdate:
                        raise ValueError(
                            "Дата рождения ребёнка не может быть раньше даты рождения целевой лошади"
                        )
                if (
                    target.sex == HorseSexEnum.FEMALE
                    and target.ddate is not None
                    and foal.bdate is not None
                ):
                    if foal.bdate > target.ddate:
                        raise ValueError(
                            "Дата рождения ребёнка не может быть позже даты смерти матери (целевой лошади)"
                        )
        return self
