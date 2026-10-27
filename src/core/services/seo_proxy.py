import re
from datetime import date
from uuid import UUID

from clients.seo_service.schemas import (
    BlacklistItemInDto,
    BlacklistItemOutDto,
    PagesOutDto,
    PaginatedEntities,
    SearchQueriesOutDto,
)
from core.exceptions.base import ClientError
from core.protocols.seo_service import SeoServiceClientProtocol
from core.schemas.metrics_table import MetricsMetric, MetricsMode
from core.schemas.users import UserOutDto


class SeoProxyService:
    """Tenant из сессии; проверка роли ADMIN принадлежит API-слою."""

    def __init__(self, client: SeoServiceClientProtocol) -> None:
        self._client = client

    @staticmethod
    def _query_date(value: str | None) -> date | None:
        if value is None:
            return None
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
            raise ValueError
        return date.fromisoformat(value)

    async def list_search_queries(
        self,
        *,
        actor: UserOutDto,
        search: str | None = None,
        ordering: str | None = None,
        limit: int = 20,
        offset: int = 0,
        mode: str | None = None,
        metric: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> SearchQueriesOutDto:
        try:
            parsed_mode = MetricsMode(mode) if mode is not None else None
            parsed_metric = MetricsMetric(metric) if metric is not None else None
            parsed_from = self._query_date(date_from)
            parsed_to = self._query_date(date_to)
            if ordering is not None and ordering not in {
                "query",
                "-query",
                "created_at",
                "-created_at",
            }:
                field = ordering.removeprefix("-")
                if not field.startswith("metric:"):
                    raise ValueError
                self._query_date(field.removeprefix("metric:"))
        except ValueError:
            raise ClientError("Некорректные параметры метрик или сортировки") from None
        if (parsed_from is None) != (parsed_to is None):
            raise ClientError("Нужно указать обе даты")
        if (
            parsed_from is not None
            and parsed_to is not None
            and parsed_from > parsed_to
        ):
            raise ClientError("Начало периода позже окончания")
        return await self._client.list_search_queries(
            equestrian_id=actor.equestrian_id,
            search=search,
            ordering=ordering,
            limit=max(1, min(100, limit)),
            offset=max(0, offset),
            mode=parsed_mode,
            metric=parsed_metric,
            date_from=parsed_from,
            date_to=parsed_to,
        )

    async def list_pages(
        self,
        *,
        actor: UserOutDto,
        search: str | None = None,
        ordering: str | None = None,
        limit: int = 20,
        offset: int = 0,
        mode: MetricsMode | None = None,
        metric: MetricsMetric | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> PagesOutDto:
        if (date_from is None) != (date_to is None):
            raise ClientError("Нужно указать обе даты")
        if date_from is not None and date_to is not None and date_from > date_to:
            raise ClientError("Начало периода позже окончания")
        return await self._client.list_pages(
            equestrian_id=actor.equestrian_id,
            search=search,
            ordering=ordering,
            limit=max(1, min(100, limit)),
            offset=max(0, offset),
            mode=mode,
            metric=metric,
            date_from=date_from,
            date_to=date_to,
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
