from typing import TypeVar
from uuid import UUID

import httpx
from pydantic import BaseModel, ValidationError

from clients.yandex_service.schemas import (
    YandexAccountOutDto,
    YandexAccountsOutDto,
    YandexAuthLinkOutDto,
    YandexMetricaConnectedCounterOutDto,
    YandexMetricaConnectionOutDto,
    YandexMetricaCountersOutDto,
)
from core.exceptions.base import ClientError
from core.protocols.yandex_service import YandexServiceUnavailableError

ResponseDto = TypeVar("ResponseDto", bound=BaseModel)
REJECTED_DETAIL = "Запрос к сервису Яндекс отклонён"


class YandexServiceClient:
    """Приватный peer без credentials; тела и причины сбоев не логируются."""

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
        params: dict[str, str | int] | None = None,
        body: dict[str, str] | None = None,
        expected_status: int = 200,
    ) -> httpx.Response:
        try:
            async with httpx.AsyncClient(
                timeout=10.0, transport=self._transport
            ) as client:
                response = await client.request(
                    method, f"{self._base_url}{path}", params=params, json=body
                )
        except httpx.RequestError:
            raise YandexServiceUnavailableError() from None
        if response.status_code == 400:
            try:
                payload = response.json()
            except ValueError:
                payload = None
            detail = payload.get("detail") if isinstance(payload, dict) else None
            if not isinstance(detail, str) or len(detail) > 300:
                detail = REJECTED_DETAIL
            raise ClientError(detail)
        if response.status_code != expected_status:
            raise YandexServiceUnavailableError()
        return response

    @staticmethod
    def _parse(response: httpx.Response, schema: type[ResponseDto]) -> ResponseDto:
        try:
            return schema.model_validate(response.json())
        except (ValueError, ValidationError):
            raise YandexServiceUnavailableError() from None

    async def get_auth_link(self, *, equestrian_id: UUID) -> YandexAuthLinkOutDto:
        response = await self._request(
            "GET", "/api/auth/link", params={"equestrian_id": str(equestrian_id)}
        )
        return self._parse(response, YandexAuthLinkOutDto)

    async def exchange_code(
        self, *, equestrian_id: UUID, code: str
    ) -> YandexAccountOutDto:
        response = await self._request(
            "POST",
            "/api/auth/code",
            body={"equestrian_id": str(equestrian_id), "code": code},
        )
        return self._parse(response, YandexAccountOutDto)

    async def list_accounts(
        self,
        *,
        equestrian_id: UUID,
        search: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> YandexAccountsOutDto:
        params: dict[str, str | int] = {
            "equestrian_id": str(equestrian_id),
            "limit": limit,
            "offset": offset,
        }
        if search is not None:
            params["search"] = search
        response = await self._request("GET", "/api/accounts/", params=params)
        return self._parse(response, YandexAccountsOutDto)

    async def delete_account(self, *, account_id: UUID) -> None:
        await self._request(
            "DELETE", f"/api/accounts/{account_id}", expected_status=204
        )

    async def list_counters(
        self,
        *,
        account_id: UUID,
        search: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> YandexMetricaCountersOutDto:
        params: dict[str, str | int] = {
            "account_id": str(account_id),
            "limit": limit,
            "offset": offset,
        }
        if search is not None:
            params["search"] = search
        response = await self._request("GET", "/api/metrica/counters", params=params)
        return self._parse(response, YandexMetricaCountersOutDto)

    async def get_connection(
        self, *, equestrian_id: UUID
    ) -> YandexMetricaConnectedCounterOutDto:
        response = await self._request(
            "GET", f"/api/connections/metrica/{equestrian_id}"
        )
        return self._parse(response, YandexMetricaConnectedCounterOutDto)

    async def set_connection(
        self,
        *,
        equestrian_id: UUID,
        yandex_account_id: UUID,
        counter_id: str,
    ) -> YandexMetricaConnectionOutDto:
        response = await self._request(
            "POST",
            "/api/connections/metrica",
            body={
                "equestrian_id": str(equestrian_id),
                "yandex_account_id": str(yandex_account_id),
                "counter_id": counter_id,
            },
        )
        return self._parse(response, YandexMetricaConnectionOutDto)

    async def delete_connection(self, *, counter_record_id: UUID) -> None:
        await self._request(
            "DELETE",
            f"/api/connections/metrica/{counter_record_id}",
            expected_status=204,
        )
