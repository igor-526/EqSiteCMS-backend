from typing import Literal, Protocol
from uuid import UUID

from core.entities.photos import Photo

from .base_repository import TenantBaseRepositoryProtocol


class PhotoRepositoryProtocol(TenantBaseRepositoryProtocol[Photo], Protocol):
    async def find_by_name(self, name: str, *, equestrian_id: UUID) -> Photo | None: ...

    async def get_filtered(
        self,
        *,
        equestrian_id: UUID,
        name: str | None = None,
        description: str | None = None,
        price_ids: list[UUID] | None = None,
        horse_ids: list[UUID] | None = None,
        sort: (
            list[
                Literal[
                    "name",
                    "description",
                    "created_at",
                    "-name",
                    "-description",
                    "-created_at",
                ]
            ]
            | None
        ) = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[list[Photo], int]: ...

    async def batch_delete(self, ids: list[UUID], *, equestrian_id: UUID) -> None: ...
