from typing import Literal
from uuid import UUID

from core.entities.horse_owner import HorseOwner
from core.exceptions.base import ClientError
from core.protocols.repositories.horse_owner_repository import (
    HorseOwnerRepositoryProtocol,
)
from core.schemas.horse_owner import HorseOwnerCreateInDto, HorseOwnerUpdateDto


class HorseOwnerService:
    def __init__(self, horse_owner_repository: HorseOwnerRepositoryProtocol):
        self.horse_owner_repository = horse_owner_repository

    async def create(self, data: HorseOwnerCreateInDto) -> HorseOwner:
        """Создать нового владельца."""
        horse_owner = HorseOwner(**data.model_dump())
        return await self.horse_owner_repository.create(horse_owner)

    async def update(self, id: UUID, data: HorseOwnerUpdateDto) -> HorseOwner:
        """Обновить владельца."""
        horse_owner = await self.horse_owner_repository.get_by_id(id)
        if horse_owner is None:
            raise ClientError("Владелец не найден")

        update_data = data.model_dump(exclude_none=True)
        for key, value in update_data.items():
            setattr(horse_owner, key, value)

        return await self.horse_owner_repository.update(horse_owner)

    async def get_by_id(self, id: UUID) -> HorseOwner | None:
        """Получить владельца по UUID."""
        return await self.horse_owner_repository.get_by_id(id)

    async def delete(self, id: UUID) -> None:
        """Удалить владельца."""
        horse_owner = await self.horse_owner_repository.get_by_id(id)
        if horse_owner is None:
            raise ClientError("Владелец не найден")
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
