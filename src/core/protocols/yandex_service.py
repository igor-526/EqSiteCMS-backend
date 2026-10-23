from typing import Protocol
from uuid import UUID

from clients.yandex_service.schemas import (
    YandexAccountOutDto,
    YandexAccountsOutDto,
    YandexAuthLinkOutDto,
    YandexMetricaConnectedCounterOutDto,
    YandexMetricaConnectionOutDto,
    YandexMetricaCountersOutDto,
)


class YandexServiceUnavailableError(Exception):
    """Безопасная ошибка транспорта или нарушения контракта peer."""

    def __init__(self) -> None:
        super().__init__("Yandex service unavailable")


class YandexServiceClientProtocol(Protocol):
    async def get_auth_link(self, *, equestrian_id: UUID) -> YandexAuthLinkOutDto: ...

    async def exchange_code(
        self, *, equestrian_id: UUID, code: str
    ) -> YandexAccountOutDto: ...

    async def list_accounts(
        self,
        *,
        equestrian_id: UUID,
        search: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> YandexAccountsOutDto: ...

    async def delete_account(self, *, account_id: UUID) -> None: ...

    async def list_counters(
        self,
        *,
        account_id: UUID,
        search: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> YandexMetricaCountersOutDto: ...

    async def get_connection(
        self, *, equestrian_id: UUID
    ) -> YandexMetricaConnectedCounterOutDto: ...

    async def set_connection(
        self,
        *,
        equestrian_id: UUID,
        yandex_account_id: UUID,
        counter_id: str,
    ) -> YandexMetricaConnectionOutDto: ...

    async def delete_connection(self, *, counter_record_id: UUID) -> None: ...
