from typing import Literal, Protocol

from core.entities.horse_owner import HorseOwner

from .base_repository import BaseRepositoryProtocol


class HorseOwnerRepositoryProtocol(BaseRepositoryProtocol[HorseOwner], Protocol):
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
    ) -> tuple[list[HorseOwner], int]: ...
