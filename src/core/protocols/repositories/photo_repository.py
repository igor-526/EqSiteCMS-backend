from typing import Literal, Protocol
from uuid import UUID

from core.entities.photos import Photo

from .base_repository import BaseRepositoryProtocol


class PhotoRepositoryProtocol(BaseRepositoryProtocol[Photo], Protocol):
    async def find_by_name(self, name: str) -> Photo | None: ...
    async def get_filtered(
        self,
        *,
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
    async def batch_delete(self, ids: list[UUID]) -> None: ...
