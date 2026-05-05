from typing import Literal, Protocol
from uuid import UUID

from core.entities.coat_color import CoatColor

from .base_repository import BaseRepositoryProtocol


class CoatColorRepositoryProtocol(BaseRepositoryProtocol[CoatColor], Protocol):
    async def get_by_slug(self, slug: str) -> CoatColor | None: ...
    async def get_by_slug_or_id(self, slug_or_id: str | UUID) -> CoatColor | None: ...
    async def find_by_slug(self, slug: str) -> CoatColor | None: ...
    async def find_by_name(self, name: str) -> CoatColor | None: ...
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
    ) -> tuple[list[CoatColor], int]: ...
