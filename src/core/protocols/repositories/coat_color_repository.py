from typing import Literal, Protocol
from uuid import UUID

from core.entities.coat_color import CoatColor

from .base_repository import TenantBaseRepositoryProtocol


class CoatColorRepositoryProtocol(TenantBaseRepositoryProtocol[CoatColor], Protocol):
    async def get_by_slug(
        self, slug: str, *, equestrian_id: UUID
    ) -> CoatColor | None: ...

    async def get_by_slug_or_id(
        self, slug_or_id: str | UUID, *, equestrian_id: UUID
    ) -> CoatColor | None: ...

    async def find_by_slug(
        self, slug: str, *, equestrian_id: UUID
    ) -> CoatColor | None: ...

    async def find_by_name(
        self, name: str, *, equestrian_id: UUID
    ) -> CoatColor | None: ...

    async def get_filtered(
        self,
        *,
        equestrian_id: UUID,
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
    ) -> tuple[list[CoatColor], int]: ...
