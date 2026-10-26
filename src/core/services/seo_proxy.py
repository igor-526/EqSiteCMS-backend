from uuid import UUID

from clients.seo_service.schemas import (
    BlacklistItemInDto,
    BlacklistItemOutDto,
    PageOutDto,
    PaginatedEntities,
    SearchQueryOutDto,
)
from core.protocols.seo_service import SeoServiceClientProtocol
from core.schemas.users import UserOutDto


class SeoProxyService:
    """Tenant из сессии; проверка роли ADMIN принадлежит API-слою."""

    def __init__(self, client: SeoServiceClientProtocol) -> None:
        self._client = client

    async def list_search_queries(
        self,
        *,
        actor: UserOutDto,
        search: str | None = None,
        ordering: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> PaginatedEntities[SearchQueryOutDto]:
        return await self._client.list_search_queries(
            equestrian_id=actor.equestrian_id,
            search=search,
            ordering=ordering,
            limit=max(1, min(100, limit)),
            offset=max(0, offset),
        )

    async def list_pages(
        self,
        *,
        actor: UserOutDto,
        search: str | None = None,
        ordering: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> PaginatedEntities[PageOutDto]:
        return await self._client.list_pages(
            equestrian_id=actor.equestrian_id,
            search=search,
            ordering=ordering,
            limit=max(1, min(100, limit)),
            offset=max(0, offset),
        )

    async def list_blacklisted_query_params(
        self, *, actor: UserOutDto
    ) -> PaginatedEntities[BlacklistItemOutDto]:
        return await self._client.list_blacklisted_query_params(
            equestrian_id=actor.equestrian_id
        )

    async def create_blacklisted_query_params(
        self, *, actor: UserOutDto, data: BlacklistItemInDto
    ) -> BlacklistItemOutDto:
        return await self._client.create_blacklisted_query_params(
            equestrian_id=actor.equestrian_id, data=data
        )

    async def update_blacklisted_query_params(
        self, *, actor: UserOutDto, item_id: UUID, data: BlacklistItemInDto
    ) -> BlacklistItemOutDto:
        return await self._client.update_blacklisted_query_params(
            equestrian_id=actor.equestrian_id, item_id=item_id, data=data
        )

    async def delete_blacklisted_query_params(
        self, *, actor: UserOutDto, item_id: UUID
    ) -> None:
        await self._client.delete_blacklisted_query_params(
            equestrian_id=actor.equestrian_id, item_id=item_id
        )

    async def list_blacklisted_hashes(
        self, *, actor: UserOutDto
    ) -> PaginatedEntities[BlacklistItemOutDto]:
        return await self._client.list_blacklisted_hashes(
            equestrian_id=actor.equestrian_id
        )

    async def create_blacklisted_hashes(
        self, *, actor: UserOutDto, data: BlacklistItemInDto
    ) -> BlacklistItemOutDto:
        return await self._client.create_blacklisted_hashes(
            equestrian_id=actor.equestrian_id, data=data
        )

    async def update_blacklisted_hashes(
        self, *, actor: UserOutDto, item_id: UUID, data: BlacklistItemInDto
    ) -> BlacklistItemOutDto:
        return await self._client.update_blacklisted_hashes(
            equestrian_id=actor.equestrian_id, item_id=item_id, data=data
        )

    async def delete_blacklisted_hashes(
        self, *, actor: UserOutDto, item_id: UUID
    ) -> None:
        await self._client.delete_blacklisted_hashes(
            equestrian_id=actor.equestrian_id, item_id=item_id
        )
