from datetime import datetime
from typing import Protocol
from uuid import UUID

from core.entities.news import News, NewsPhoto, NewsStatus

from .base_repository import TenantBaseRepositoryProtocol


class NewsRepositoryProtocol(TenantBaseRepositoryProtocol[News], Protocol):
    async def get_cms_filtered(
        self,
        *,
        equestrian_id: UUID,
        name: str | None = None,
        snippet: str | None = None,
        content: str | None = None,
        published_at_from: datetime | None = None,
        published_at_to: datetime | None = None,
        status: list[NewsStatus] | None = None,
        sort: str = "-published_at",
        limit: int = 25,
        offset: int = 0,
    ) -> tuple[list[News], int]: ...

    async def get_public_filtered(
        self,
        *,
        equestrian_id: UUID,
        limit: int = 25,
        offset: int = 0,
    ) -> tuple[list[News], int]: ...

    async def get_public_by_id(
        self, id: UUID, *, equestrian_id: UUID
    ) -> News | None: ...

    async def get_news_photos(
        self, news_id: UUID, *, equestrian_id: UUID
    ) -> list[NewsPhoto]: ...

    async def set_news_photos(
        self,
        news_id: UUID,
        photo_ids: list[UUID] | None = None,
        main_photo_id: UUID | None = None,
        *,
        equestrian_id: UUID,
    ) -> None: ...
