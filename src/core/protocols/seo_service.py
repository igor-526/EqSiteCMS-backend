from typing import Protocol
from uuid import UUID

from clients.seo_service.schemas import (
    BlacklistItemInDto,
    BlacklistItemOutDto,
    PageOutDto,
    PaginatedEntities,
    SearchQueryOutDto,
)


class SeoServiceUnavailableError(Exception):
    """Безопасная ошибка транспорта или нарушения контракта peer."""

    def __init__(self) -> None:
        super().__init__("SEO service unavailable")


class SeoServiceClientProtocol(Protocol):
    async def list_search_queries(
        self,
        *,
        equestrian_id: UUID,
        search: str | None = None,
        ordering: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> PaginatedEntities[SearchQueryOutDto]: ...

    async def list_pages(
        self,
        *,
        equestrian_id: UUID,
        search: str | None = None,
        ordering: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> PaginatedEntities[PageOutDto]: ...

    async def list_blacklisted_query_params(
        self, *, equestrian_id: UUID
    ) -> PaginatedEntities[BlacklistItemOutDto]: ...

    async def create_blacklisted_query_params(
        self, *, equestrian_id: UUID, data: BlacklistItemInDto
    ) -> BlacklistItemOutDto: ...

    async def update_blacklisted_query_params(
        self, *, equestrian_id: UUID, item_id: UUID, data: BlacklistItemInDto
    ) -> BlacklistItemOutDto: ...

    async def delete_blacklisted_query_params(
        self, *, equestrian_id: UUID, item_id: UUID
    ) -> None: ...

    async def list_blacklisted_hashes(
        self, *, equestrian_id: UUID
    ) -> PaginatedEntities[BlacklistItemOutDto]: ...

    async def create_blacklisted_hashes(
        self, *, equestrian_id: UUID, data: BlacklistItemInDto
    ) -> BlacklistItemOutDto: ...

    async def update_blacklisted_hashes(
        self, *, equestrian_id: UUID, item_id: UUID, data: BlacklistItemInDto
    ) -> BlacklistItemOutDto: ...

    async def delete_blacklisted_hashes(
        self, *, equestrian_id: UUID, item_id: UUID
    ) -> None: ...
