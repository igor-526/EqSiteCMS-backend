from typing import Literal, Protocol
from uuid import UUID

from core.entities.prices import Price, PriceGroup, PriceGroupsRelation, PricePhotos

from .base_repository import TenantBaseRepositoryProtocol


class PriceGroupRepositoryProtocol(TenantBaseRepositoryProtocol[PriceGroup], Protocol):
    async def find_by_name(
        self, name: str, *, equestrian_id: UUID
    ) -> PriceGroup | None: ...

    async def get_filtered(
        self,
        *,
        equestrian_id: UUID,
        name: str | None = None,
        description: str | None = None,
        sort: list[Literal["name", "-name"]] | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[list[PriceGroup], int]: ...


class PriceRepositoryProtocol(TenantBaseRepositoryProtocol[Price], Protocol):
    async def find_by_name(self, name: str, *, equestrian_id: UUID) -> Price | None: ...

    async def get_by_slug_or_id(
        self, slug_or_id: str | UUID, *, equestrian_id: UUID
    ) -> Price | None: ...

    async def get_filtered(
        self,
        *,
        equestrian_id: UUID,
        name: str | list[str] | None = None,
        description: str | None = None,
        groups: str | list[str] | None = None,
        sort: list[Literal["name", "-name"]] | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[list[Price], int]: ...

    async def get_price_groups(
        self, price_id: UUID, *, equestrian_id: UUID
    ) -> list[PriceGroupsRelation]: ...

    async def set_price_groups(
        self, price_id: UUID, group_ids: list[UUID], *, equestrian_id: UUID
    ) -> None: ...

    async def get_price_photos(
        self, price_id: UUID, *, equestrian_id: UUID
    ) -> list[PricePhotos]: ...

    async def set_price_photos(
        self,
        price_id: UUID,
        photo_ids: list[UUID] | None = None,
        main_photo_id: UUID | None = None,
        *,
        equestrian_id: UUID,
    ) -> None: ...
