from typing import Literal, Protocol
from uuid import UUID

from core.entities.horse_service import HorseServiceEntity

from .base_repository import BaseRepositoryProtocol


class HorseServiceRepositoryProtocol(
    BaseRepositoryProtocol[HorseServiceEntity], Protocol
):
    async def get_by_slug(self, slug: str) -> HorseServiceEntity | None: ...
    async def get_by_slug_or_id(
        self, slug_or_id: str | UUID
    ) -> HorseServiceEntity | None: ...
    async def find_by_slug(self, slug: str) -> HorseServiceEntity | None: ...
    async def find_by_name(self, name: str) -> HorseServiceEntity | None: ...
    async def get_filtered(
        self,
        *,
        name: str | None = None,
        slug: str | None = None,
        description: str | None = None,
        page_data: str | None = None,
        sort: (
            list[
                Literal[
                    "name",
                    "description",
                    "slug",
                    "price",
                    "-name",
                    "-description",
                    "-slug",
                    "-price",
                ]
            ]
            | None
        ) = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[list[HorseServiceEntity], int]: ...
