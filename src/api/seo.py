from collections.abc import Awaitable
from typing import Annotated, TypeVar
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from clients.seo_service.schemas import (
    BlacklistItemInDto,
    BlacklistItemOutDto,
    PageOutDto,
    PaginatedEntities,
    SearchQueryOutDto,
)
from core.exceptions.auth import ForbiddenError
from core.exceptions.base import ClientError
from core.protocols.seo_service import SeoServiceUnavailableError
from core.schemas.users import UserOutDto
from core.services.seo_proxy import SeoProxyService
from depends.services import get_current_user, get_seo_proxy_service

router = APIRouter(prefix="/seo", tags=["SEO"])
T = TypeVar("T")


async def require_seo_admin(
    current_user: Annotated[UserOutDto, Depends(get_current_user)],
) -> UserOutDto:
    """Только ADMIN, без наследования повышенных ролей."""
    if not any(scope.scope_name == "ADMIN" for scope in current_user.scopes):
        raise ForbiddenError("Недостаточно прав для выполнения операции")
    return current_user


Actor = Annotated[UserOutDto, Depends(require_seo_admin)]
Service = Annotated[SeoProxyService, Depends(get_seo_proxy_service)]


async def _proxy(operation: Awaitable[T]) -> T:
    try:
        return await operation
    except SeoServiceUnavailableError as exc:
        raise HTTPException(502, "SEO service unavailable") from exc


def _item_uuid(value: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise ClientError("Некорректный item_id") from exc


@router.get("/search-queries", response_model=PaginatedEntities[SearchQueryOutDto])
async def list_search_queries(
    actor: Actor,
    service: Service,
    search: str | None = None,
    ordering: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> PaginatedEntities[SearchQueryOutDto]:
    return await _proxy(
        service.list_search_queries(
            actor=actor, search=search, ordering=ordering, limit=limit, offset=offset
        )
    )


@router.get("/pages", response_model=PaginatedEntities[PageOutDto])
async def list_pages(
    actor: Actor,
    service: Service,
    search: str | None = None,
    ordering: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> PaginatedEntities[PageOutDto]:
    return await _proxy(
        service.list_pages(
            actor=actor, search=search, ordering=ordering, limit=limit, offset=offset
        )
    )


@router.get(
    "/page-normalization/blacklisted-query-params",
    response_model=PaginatedEntities[BlacklistItemOutDto],
)
async def list_blacklisted_query_params(
    actor: Actor, service: Service
) -> PaginatedEntities[BlacklistItemOutDto]:
    return await _proxy(service.list_blacklisted_query_params(actor=actor))


@router.post(
    "/page-normalization/blacklisted-query-params",
    response_model=BlacklistItemOutDto,
    status_code=201,
)
async def create_blacklisted_query_params(
    data: BlacklistItemInDto, actor: Actor, service: Service
) -> BlacklistItemOutDto:
    return await _proxy(service.create_blacklisted_query_params(actor=actor, data=data))


@router.patch(
    "/page-normalization/blacklisted-query-params/{item_id}",
    response_model=BlacklistItemOutDto,
)
async def update_blacklisted_query_params(
    item_id: str, data: BlacklistItemInDto, actor: Actor, service: Service
) -> BlacklistItemOutDto:
    return await _proxy(
        service.update_blacklisted_query_params(
            actor=actor, item_id=_item_uuid(item_id), data=data
        )
    )


@router.delete(
    "/page-normalization/blacklisted-query-params/{item_id}", status_code=204
)
async def delete_blacklisted_query_params(
    item_id: str, actor: Actor, service: Service
) -> None:
    await _proxy(
        service.delete_blacklisted_query_params(
            actor=actor, item_id=_item_uuid(item_id)
        )
    )


@router.get(
    "/page-normalization/blacklisted-hashes",
    response_model=PaginatedEntities[BlacklistItemOutDto],
)
async def list_blacklisted_hashes(
    actor: Actor, service: Service
) -> PaginatedEntities[BlacklistItemOutDto]:
    return await _proxy(service.list_blacklisted_hashes(actor=actor))


@router.post(
    "/page-normalization/blacklisted-hashes",
    response_model=BlacklistItemOutDto,
    status_code=201,
)
async def create_blacklisted_hashes(
    data: BlacklistItemInDto, actor: Actor, service: Service
) -> BlacklistItemOutDto:
    return await _proxy(service.create_blacklisted_hashes(actor=actor, data=data))


@router.patch(
    "/page-normalization/blacklisted-hashes/{item_id}",
    response_model=BlacklistItemOutDto,
)
async def update_blacklisted_hashes(
    item_id: str, data: BlacklistItemInDto, actor: Actor, service: Service
) -> BlacklistItemOutDto:
    return await _proxy(
        service.update_blacklisted_hashes(
            actor=actor, item_id=_item_uuid(item_id), data=data
        )
    )


@router.delete("/page-normalization/blacklisted-hashes/{item_id}", status_code=204)
async def delete_blacklisted_hashes(
    item_id: str, actor: Actor, service: Service
) -> None:
    await _proxy(
        service.delete_blacklisted_hashes(actor=actor, item_id=_item_uuid(item_id))
    )
