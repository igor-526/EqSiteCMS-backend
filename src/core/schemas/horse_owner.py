from uuid import UUID

from pydantic import Field, field_validator

from core.entities.horse_owner import HorseOwnerType
from core.schemas.baseschema import BaseSchema


class HorseOwnerOutDto(BaseSchema):
    """DTO для вывода владельца."""

    id: UUID
    name: str
    description: str | None
    type: HorseOwnerType
    address: str | None
    phone_numbers: list[str]


class HorseOwnerCreateInDto(BaseSchema):
    """DTO для создания владельца."""

    name: str = Field(..., description="Имя владельца")
    description: str | None = Field(None, description="Описание владельца")
    type: HorseOwnerType = Field(HorseOwnerType.person, description="Тип владельца")
    address: str | None = Field(None, description="Адрес владельца")
    phone_numbers: list[str] = Field(
        default_factory=list, description="Список телефонных номеров"
    )

    @field_validator("phone_numbers")
    @classmethod
    def validate_phone_numbers(cls, v: list[str]) -> list[str]:
        """Валидация формата телефонов: должен начинаться с + и содержать от 7 до 15 цифр."""
        import re

        from core.exceptions.base import ClientError

        pattern = r"^\+\d{7,15}$"
        for phone in v:
            if not re.match(pattern, phone):
                raise ClientError(
                    f"Неверный формат телефона: {phone}. "
                    "Телефон должен начинаться с + и содержать от 7 до 15 цифр"
                )
        return v


class HorseOwnerUpdateDto(BaseSchema):
    """DTO для обновления владельца."""

    name: str | None = Field(None, description="Имя владельца")
    description: str | None = Field(None, description="Описание владельца")
    type: HorseOwnerType | None = Field(None, description="Тип владельца")
    address: str | None = Field(None, description="Адрес владельца")
    phone_numbers: list[str] | None = Field(
        None, description="Список телефонных номеров"
    )

    @field_validator("phone_numbers")
    @classmethod
    def validate_phone_numbers(cls, v: list[str] | None) -> list[str] | None:
        """Валидация формата телефонов: должен начинаться с + и содержать от 7 до 15 цифр."""
        if v is None:
            return v
        import re

        from core.exceptions.base import ClientError

        pattern = r"^\+\d{7,15}$"
        for phone in v:
            if not re.match(pattern, phone):
                raise ClientError(
                    f"Неверный формат телефона: {phone}. "
                    "Телефон должен начинаться с + и содержать от 7 до 15 цифр"
                )
        return v
