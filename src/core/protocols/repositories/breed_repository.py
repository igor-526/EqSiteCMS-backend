from typing import Literal, Protocol
from uuid import UUID

from core.entities.breeds import Breed
from core.entities.horse import HorseKindEnum

from .base_repository import TenantBaseRepositoryProtocol


class BreedRepositoryProtocol(TenantBaseRepositoryProtocol[Breed], Protocol):
    async def get_by_slug(self, slug: str, *, equestrian_id: UUID) -> Breed | None: ...

    async def get_by_slug_or_id(
        self, slug_or_id: str | UUID, *, equestrian_id: UUID
    ) -> Breed | None: ...

    async def find_by_slug(self, slug: str, *, equestrian_id: UUID) -> Breed | None: ...

    async def find_by_name(self, name: str, *, equestrian_id: UUID) -> Breed | None: ...

    async def get_filtered(
        self,
        *,
        equestrian_id: UUID,
        name: str | None = None,
        short_name: str | None = None,
        slug: str | None = None,
        description: str | None = None,
        page_data: str | None = None,
        kind: list[HorseKindEnum] | None = None,
        sort: (
            list[
                Literal[
                    "name",
                    "short_name",
                    "description",
                    "slug",
                    "kind",
                    "-name",
                    "-short_name",
                    "-description",
                    "-slug",
                    "-kind",
                ]
            ]
            | None
        ) = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[list[Breed], int]: ...
