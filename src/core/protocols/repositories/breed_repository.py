from typing import Literal, Protocol
from uuid import UUID

from core.entities.breeds import Breed

from .base_repository import BaseRepositoryProtocol


class BreedRepositoryProtocol(BaseRepositoryProtocol[Breed], Protocol):
    async def get_by_slug(self, slug: str) -> Breed | None: ...
    async def get_by_slug_or_id(self, slug_or_id: str | UUID) -> Breed | None: ...
    async def find_by_slug(self, slug: str) -> Breed | None: ...
    async def find_by_name(self, name: str) -> Breed | None: ...
    async def get_filtered(
        self,
        *,
        name: str | None = None,
        slug: str | None = None,
        description: str | None = None,
        page_data: str | None = None,
        sort: (
            list[
                Literal["name", "description", "slug", "-name", "-description", "-slug"]
            ]
            | None
        ) = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[list[Breed], int]: ...
