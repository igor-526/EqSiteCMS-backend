import re
from typing import Literal
from uuid import UUID

from pydantic import ValidationError

from core.entities.horse_owner import HorseOwner
from core.exceptions.base import ClientError
from core.protocols.repositories.horse_owner_repository import (
    HorseOwnerRepositoryProtocol,
)
from core.schemas.horse_owner import HorseOwnerCreateInDto, HorseOwnerUpdateDto

_PHONE_PATTERN = re.compile(r"^\+\d{7,15}$")


class HorseOwnerService:
    def __init__(self, horse_owner_repository: HorseOwnerRepositoryProtocol):
        self.horse_owner_repository = horse_owner_repository

    def _validate_phone_numbers(self, phones: list[str]) -> None:
        """Проверить формат каждого телефонного номера."""
        for phone in phones:
            if not _PHONE_PATTERN.match(phone):
                raise ClientError(
                    f"Неверный формат телефона: {phone}. "
                    "Телефон должен начинаться с + и содержать от 7 до 15 цифр"
                )

    async def create(self, data: HorseOwnerCreateInDto) -> HorseOwner:
        """Создать нового владельца."""
        if data.phone_numbers:
            self._validate_phone_numbers(data.phone_numbers)
        try:
            horse_owner = HorseOwner(**data.model_dump())
        except ValidationError as e:
            raise ClientError(str(e)) from e
        return await self.horse_owner_repository.create(horse_owner)

    async def update(self, id: UUID, data: HorseOwnerUpdateDto) -> HorseOwner:
        """Обновить владельца."""
        horse_owner = await self.get_by_id_or_raise(id)

        if data.phone_numbers is not None:
            self._validate_phone_numbers(data.phone_numbers)

        update_data = data.model_dump(exclude_none=True)
        if not update_data:
            raise ClientError("Нет данных для обновления")

        for key, value in update_data.items():
            setattr(horse_owner, key, value)

        return await self.horse_owner_repository.update(horse_owner)

    async def get_by_id(self, id: UUID) -> HorseOwner | None:
        """Получить владельца по UUID."""
        return await self.horse_owner_repository.get_by_id(id)

    async def get_by_id_or_raise(self, id: UUID) -> HorseOwner:
        """Получить владельца по UUID или бросить ClientError."""
        horse_owner = await self.horse_owner_repository.get_by_id(id)
        if horse_owner is None:
            raise ClientError("Владелец не найден")
        return horse_owner

    async def delete(self, id: UUID) -> None:
        """Удалить владельца."""
        await self.get_by_id_or_raise(id)
        await self.horse_owner_repository.delete(id)

    async def get_filtered(
        self,
        *,
        name: str | None = None,
        description: str | None = None,
        type: list[str] | None = None,
        address: str | None = None,
        phone_numbers: str | None = None,
        sort: (
            list[
                Literal["name", "description", "type", "-name", "-description", "-type"]
            ]
            | None
        ) = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[list[HorseOwner], int]:
        """Получить отфильтрованный список владельцев."""
        return await self.horse_owner_repository.get_filtered(
            name=name,
            description=description,
            type=type,
            address=address,
            phone_numbers=phone_numbers,
            sort=sort,
            limit=limit,
            offset=offset,
        )
