from collections.abc import Awaitable
from typing import Annotated, TypeVar
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from clients.yandex_service.schemas import (
    YandexAccountOutDto,
    YandexAccountsOutDto,
    YandexAuthCodeInDto,
    YandexAuthLinkOutDto,
    YandexMetricaConnectedCounterOutDto,
    YandexMetricaConnectionOutDto,
    YandexMetricaCountersOutDto,
    YandexMetricaSetConnectionInDto,
)
from core.exceptions.auth import ForbiddenError
from core.exceptions.base import ClientError
from core.protocols.yandex_service import YandexServiceUnavailableError
from core.schemas.users import UserOutDto
from core.services.yandex_proxy import YandexProxyService
from depends.services import get_current_user, get_yandex_proxy_service

router = APIRouter(prefix="/yandex", tags=["Yandex"])
T = TypeVar("T")


async def require_yandex_admin(
    current_user: Annotated[UserOutDto, Depends(get_current_user)],
) -> UserOutDto:
    """Только ADMIN, без наследования повышенных ролей и новых scopes."""
    if not any(scope.scope_name == "ADMIN" for scope in current_user.scopes):
        raise ForbiddenError("Недостаточно прав для выполнения операции")
    return current_user


Actor = Annotated[UserOutDto, Depends(require_yandex_admin)]
Service = Annotated[YandexProxyService, Depends(get_yandex_proxy_service)]


async def _proxy(operation: Awaitable[T]) -> T:
    try:
        return await operation
    except YandexServiceUnavailableError as exc:
        raise HTTPException(502, "Yandex service unavailable") from exc


def _account_uuid(value: str | None) -> UUID:
    if value is None:
        raise ClientError("Не указан account_id")
    try:
        return UUID(value)
    except ValueError as exc:
        raise ClientError("Некорректный account_id") from exc


@router.get("/auth/link", response_model=YandexAuthLinkOutDto)
async def get_auth_link(actor: Actor, service: Service) -> YandexAuthLinkOutDto:
    return await _proxy(service.get_auth_link(actor=actor))


@router.post("/auth/code", response_model=YandexAccountOutDto)
async def exchange_code(
    data: YandexAuthCodeInDto, actor: Actor, service: Service
) -> YandexAccountOutDto:
    return await _proxy(service.exchange_code(actor=actor, data=data))


@router.get("/accounts", response_model=YandexAccountsOutDto)
async def list_accounts(
    actor: Actor,
    service: Service,
    search: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> YandexAccountsOutDto:
    return await _proxy(
        service.list_accounts(actor=actor, search=search, limit=limit, offset=offset)
    )


@router.delete("/accounts/{account_id}", status_code=204)
async def delete_account(account_id: str, actor: Actor, service: Service) -> None:
    await _proxy(
        service.delete_account(actor=actor, account_id=_account_uuid(account_id))
    )


@router.get("/metrica/counters", response_model=YandexMetricaCountersOutDto)
async def list_counters(
    actor: Actor,
    service: Service,
    account_id: str | None = None,
    search: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> YandexMetricaCountersOutDto:
    return await _proxy(
        service.list_counters(
            actor=actor,
            account_id=_account_uuid(account_id),
            search=search,
            limit=limit,
            offset=offset,
        )
    )


@router.get("/metrica/connection", response_model=YandexMetricaConnectedCounterOutDto)
async def get_connection(
    actor: Actor, service: Service
) -> YandexMetricaConnectedCounterOutDto:
    return await _proxy(service.get_connection(actor=actor))


@router.post("/metrica/connection", response_model=YandexMetricaConnectionOutDto)
async def set_connection(
    data: YandexMetricaSetConnectionInDto, actor: Actor, service: Service
) -> YandexMetricaConnectionOutDto:
    return await _proxy(service.set_connection(actor=actor, data=data))


@router.delete("/metrica/connection", status_code=204)
async def delete_connection(actor: Actor, service: Service) -> None:
    await _proxy(service.delete_connection(actor=actor))
