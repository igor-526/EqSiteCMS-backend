from typing import Literal, Protocol
from uuid import UUID

from core.entities.breed_groups import BreedGroup

from .base_repository import TenantBaseRepositoryProtocol

BreedGroupSort = Literal[
    "name",
    "slug",
    "created_at",
    "updated_at",
    "-name",
    "-slug",
    "-created_at",
    "-updated_at",
]


class BreedGroupRepositoryProtocol(TenantBaseRepositoryProtocol[BreedGroup], Protocol):
    async def get_by_slug_or_id(
        self, slug_or_id: str | UUID, *, equestrian_id: UUID
    ) -> BreedGroup | None: ...

    async def find_by_slug(
        self, slug: str, *, equestrian_id: UUID
    ) -> BreedGroup | None: ...

    async def find_by_name(
        self, name: str, *, equestrian_id: UUID
    ) -> BreedGroup | None: ...

    async def get_filtered(
        self,
        *,
        equestrian_id: UUID,
        name: str | None = None,
        slug: str | None = None,
        page_data: str | None = None,
        sort: list[BreedGroupSort] | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[list[BreedGroup], int]: ...
