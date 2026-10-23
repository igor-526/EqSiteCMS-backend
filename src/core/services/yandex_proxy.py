import re
from uuid import UUID

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
from core.exceptions.base import ClientError, NotFoundError
from core.protocols.yandex_service import YandexServiceClientProtocol
from core.schemas.users import UserOutDto


class YandexProxyService:
    """Tenant-scoped use cases; ADMIN guard подключается browser API слоем."""

    def __init__(self, client: YandexServiceClientProtocol) -> None:
        self._client = client

    async def _require_account(self, *, actor: UserOutDto, account_id: UUID) -> None:
        offset = 0
        while True:
            page = await self._client.list_accounts(
                equestrian_id=actor.equestrian_id, limit=100, offset=offset
            )
            if any(account.id == account_id for account in page.items):
                return
            offset += len(page.items)
            if not page.items or offset >= page.total:
                raise NotFoundError("Аккаунт Яндекс не найден")

    async def get_auth_link(self, *, actor: UserOutDto) -> YandexAuthLinkOutDto:
        return await self._client.get_auth_link(equestrian_id=actor.equestrian_id)

    async def exchange_code(
        self, *, actor: UserOutDto, data: YandexAuthCodeInDto
    ) -> YandexAccountOutDto:
        if not data.code.strip() or not data.state.strip():
            raise ClientError("Код и state авторизации Яндекс не должны быть пустыми")
        if data.state != str(actor.equestrian_id):
            raise ForbiddenError("Некорректный state авторизации Яндекс")
        return await self._client.exchange_code(
            equestrian_id=actor.equestrian_id, code=data.code
        )

    async def list_accounts(
        self,
        *,
        actor: UserOutDto,
        search: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> YandexAccountsOutDto:
        return await self._client.list_accounts(
            equestrian_id=actor.equestrian_id,
            search=search,
            limit=max(1, min(100, limit)),
            offset=max(0, offset),
        )

    async def delete_account(self, *, actor: UserOutDto, account_id: UUID) -> None:
        await self._require_account(actor=actor, account_id=account_id)
        await self._client.delete_account(account_id=account_id)

    async def list_counters(
        self,
        *,
        actor: UserOutDto,
        account_id: UUID,
        search: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> YandexMetricaCountersOutDto:
        await self._require_account(actor=actor, account_id=account_id)
        return await self._client.list_counters(
            account_id=account_id,
            search=search,
            limit=max(1, min(100, limit)),
            offset=max(0, offset),
        )

    async def get_connection(
        self, *, actor: UserOutDto
    ) -> YandexMetricaConnectedCounterOutDto:
        return await self._client.get_connection(equestrian_id=actor.equestrian_id)

    async def set_connection(
        self, *, actor: UserOutDto, data: YandexMetricaSetConnectionInDto
    ) -> YandexMetricaConnectionOutDto:
        if re.fullmatch(r"[0-9]{1,31}", data.counter_id) is None:
            raise ClientError("counter_id должен содержать от 1 до 31 цифры")
        await self._require_account(actor=actor, account_id=data.yandex_account_id)
        return await self._client.set_connection(
            equestrian_id=actor.equestrian_id,
            yandex_account_id=data.yandex_account_id,
            counter_id=data.counter_id,
        )

    async def delete_connection(self, *, actor: UserOutDto) -> None:
        connection = await self._client.get_connection(
            equestrian_id=actor.equestrian_id
        )
        if connection.counter is not None:
            await self._client.delete_connection(
                counter_record_id=connection.counter.id
            )
