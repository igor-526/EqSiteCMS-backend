from typing import Literal, Protocol
from uuid import UUID

from core.entities.horse_owner import HorseOwner

from .base_repository import TenantBaseRepositoryProtocol


class HorseOwnerRepositoryProtocol(TenantBaseRepositoryProtocol[HorseOwner], Protocol):
    async def get_filtered(
        self,
        *,
        equestrian_id: UUID,
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
