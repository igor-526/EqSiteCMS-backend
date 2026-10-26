import logging
from contextvars import ContextVar
from typing import TypeVar
from uuid import UUID

import httpx
from pydantic import BaseModel, ValidationError

from clients.seo_service.schemas import (
    BlacklistItemInDto,
    BlacklistItemOutDto,
    PageOutDto,
    PaginatedEntities,
    SearchQueryOutDto,
)
from core.exceptions.base import ClientError, ConflictError, NotFoundError
from core.protocols.seo_service import SeoServiceUnavailableError

ResponseDto = TypeVar("ResponseDto", bound=BaseModel)
REJECTED_DETAIL = "Запрос к SEO-сервису отклонён"
_seo_request_active: ContextVar[bool] = ContextVar("seo_request_active", default=False)


class _SeoRequestLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # HTTPX пишет полный URL (включая search) на INFO. Фильтр task-local:
        # параллельные запросы других клиентов не затрагиваются.
        return not _seo_request_active.get()


logging.getLogger("httpx").addFilter(_SeoRequestLogFilter())


class SeoServiceClient:
    """Приватный peer: только tenant selector, без credentials и логов ответов."""

    def __init__(
        self, *, base_url: str, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._transport = transport

    async def _request(
        self,
        method: str,
        path: str,
        *,
        equestrian_id: UUID,
        params: dict[str, str | int] | None = None,
        body: dict[str, str] | None = None,
        expected_status: int = 200,
    ) -> httpx.Response:
        token = _seo_request_active.set(True)
        try:
            async with httpx.AsyncClient(
                timeout=10.0, transport=self._transport, trust_env=False
            ) as client:
                response = await client.request(
                    method,
                    f"{self._base_url}{path}",
                    headers={"X-Equestrian-Id": str(equestrian_id)},
                    params=params,
                    json=body,
                )
        except httpx.RequestError:
            raise SeoServiceUnavailableError() from None
        finally:
            _seo_request_active.reset(token)
        if response.status_code == 400:
            try:
                payload = response.json()
            except ValueError:
                payload = None
            detail = payload.get("detail") if isinstance(payload, dict) else None
            if not isinstance(detail, str) or not detail.strip() or len(detail) > 300:
                detail = REJECTED_DETAIL
            raise ClientError(detail)
        if response.status_code == 404:
            raise NotFoundError("Элемент SEO не найден")
        if response.status_code == 409:
            raise ConflictError("Элемент SEO уже существует")
        if response.status_code != expected_status:
            raise SeoServiceUnavailableError()
        return response

    @staticmethod
    def _parse(response: httpx.Response, schema: type[ResponseDto]) -> ResponseDto:
        try:
            return schema.model_validate(response.json())
        except (ValueError, ValidationError):
            raise SeoServiceUnavailableError() from None

    async def list_search_queries(
        self,
        *,
        equestrian_id: UUID,
        search: str | None = None,
        ordering: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> PaginatedEntities[SearchQueryOutDto]:
        params: dict[str, str | int] = {"limit": limit, "offset": offset}
        if search is not None:
            params["search"] = search
        if ordering is not None:
            params["ordering"] = ordering
        response = await self._request(
            "GET", "/api/search-queries", equestrian_id=equestrian_id, params=params
        )
        return self._parse(response, PaginatedEntities[SearchQueryOutDto])

    async def list_pages(
        self,
        *,
        equestrian_id: UUID,
        search: str | None = None,
        ordering: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> PaginatedEntities[PageOutDto]:
        params: dict[str, str | int] = {"limit": limit, "offset": offset}
        if search is not None:
            params["search"] = search
        if ordering is not None:
            params["ordering"] = ordering
        response = await self._request(
            "GET", "/api/pages", equestrian_id=equestrian_id, params=params
        )
        return self._parse(response, PaginatedEntities[PageOutDto])

    async def list_blacklisted_query_params(
        self, *, equestrian_id: UUID
    ) -> PaginatedEntities[BlacklistItemOutDto]:
        response = await self._request(
            "GET",
            "/api/page-normalization/blacklisted-query-params",
            equestrian_id=equestrian_id,
            expected_status=200,
        )
        return self._parse(response, PaginatedEntities[BlacklistItemOutDto])

    async def create_blacklisted_query_params(
        self, *, equestrian_id: UUID, data: BlacklistItemInDto
    ) -> BlacklistItemOutDto:
        response = await self._request(
            "POST",
            "/api/page-normalization/blacklisted-query-params",
            equestrian_id=equestrian_id,
            body=data.model_dump(),
            expected_status=201,
        )
        return self._parse(response, BlacklistItemOutDto)

    async def update_blacklisted_query_params(
        self, *, equestrian_id: UUID, item_id: UUID, data: BlacklistItemInDto
    ) -> BlacklistItemOutDto:
        response = await self._request(
            "PATCH",
            f"/api/page-normalization/blacklisted-query-params/{item_id}",
            equestrian_id=equestrian_id,
            body=data.model_dump(),
            expected_status=200,
        )
        return self._parse(response, BlacklistItemOutDto)

    async def delete_blacklisted_query_params(
        self, *, equestrian_id: UUID, item_id: UUID
    ) -> None:
        await self._request(
            "DELETE",
            f"/api/page-normalization/blacklisted-query-params/{item_id}",
            equestrian_id=equestrian_id,
            expected_status=204,
        )

    async def list_blacklisted_hashes(
        self, *, equestrian_id: UUID
    ) -> PaginatedEntities[BlacklistItemOutDto]:
        response = await self._request(
            "GET",
            "/api/page-normalization/blacklisted-hashes",
            equestrian_id=equestrian_id,
            expected_status=200,
        )
        return self._parse(response, PaginatedEntities[BlacklistItemOutDto])

    async def create_blacklisted_hashes(
        self, *, equestrian_id: UUID, data: BlacklistItemInDto
    ) -> BlacklistItemOutDto:
        response = await self._request(
            "POST",
            "/api/page-normalization/blacklisted-hashes",
            equestrian_id=equestrian_id,
            body=data.model_dump(),
            expected_status=201,
        )
        return self._parse(response, BlacklistItemOutDto)

    async def update_blacklisted_hashes(
        self, *, equestrian_id: UUID, item_id: UUID, data: BlacklistItemInDto
    ) -> BlacklistItemOutDto:
        response = await self._request(
            "PATCH",
            f"/api/page-normalization/blacklisted-hashes/{item_id}",
            equestrian_id=equestrian_id,
            body=data.model_dump(),
            expected_status=200,
        )
        return self._parse(response, BlacklistItemOutDto)

    async def delete_blacklisted_hashes(
        self, *, equestrian_id: UUID, item_id: UUID
    ) -> None:
        await self._request(
            "DELETE",
            f"/api/page-normalization/blacklisted-hashes/{item_id}",
            equestrian_id=equestrian_id,
            expected_status=204,
        )
