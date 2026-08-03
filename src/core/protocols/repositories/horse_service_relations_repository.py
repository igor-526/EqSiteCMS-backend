from typing import Protocol
from uuid import UUID

from core.entities.horse_service import HorseServiceEntity, HorseServiceRelations

from .base_repository import BaseRepositoryProtocol


class HorseServiceRelationsRepositoryProtocol(
    BaseRepositoryProtocol[HorseServiceRelations], Protocol
):
    async def get_list_by_horse(
        self,
        *,
        horse_id: UUID,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[list[HorseServiceRelations], int]: ...

    async def get_by_id_and_horse(
        self, *, relation_id: UUID, horse_id: UUID
    ) -> HorseServiceRelations | None: ...

    async def get_by_horse_and_service(
        self, *, horse_id: UUID, service_id: UUID
    ) -> HorseServiceRelations | None: ...

    async def get_available_services(
        self, *, horse_id: UUID, equestrian_id: UUID, search: str | None = None
    ) -> list[HorseServiceEntity]: ...
