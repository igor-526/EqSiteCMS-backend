"""UT-GW-02: production parser и изолированная HTTP-граница."""

import copy
import logging
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import httpx
import pytest

from clients.ya_metrica_service.client import YaMetricaServiceClient
from clients.ya_metrica_service.schemas import MetricaTaskListOutDto
from pydantic import ValidationError
from core.protocols.ya_metrica_service import YaMetricaServiceUnavailableError
from depends.services import get_ya_metrica_service_client
from settings import Settings

ITEM = {
    "id": "parsing:logical-id",
    "type": "parsing",
    "status": "queued",
    "is_active": True,
    "created_at": "2026-11-06T00:00:00Z",
}
PAYLOAD: dict[str, Any] = {"items": [ITEM], "total": 1}


@pytest.mark.parametrize("kind", ["parsing", "merge", "delete"])
@pytest.mark.parametrize(
    "status", ["queued", "running", "succeeded", "failed", "cancelled"]
)
def test_all_wire_enum_combinations(kind, status):
    payload = {
        "items": [
            {
                **ITEM,
                "type": kind,
                "status": status,
                "is_active": status in {"queued", "running"},
            }
        ],
        "total": 1,
    }
    assert (
        YaMetricaServiceClient.parse_response(
            httpx.Response(200, json=payload)
        ).model_dump(mode="json")
        == payload
    )


INVALID: list[Any] = [
    None,
    [],
    {},
    {"items": [], "total": -1},
    {"items": [], "total": "1"},
    {"items": [], "total": True},
    {"items": None, "total": 0},
    {**PAYLOAD, "token": "private"},
]
for field in ITEM:
    incomplete = copy.deepcopy(PAYLOAD)
    del incomplete["items"][0][field]
    INVALID.append(incomplete)
for field, value in [
    ("id", 123),
    ("type", "cleanup"),
    ("status", "awaiting_seo"),
    ("is_active", 1),
    ("is_active", "true"),
    ("created_at", "not-date"),
    ("created_at", "2026-01-01T00:00:00"),
    ("counter_id", 123),
    ("error", "private"),
    ("token", "private"),
]:
    INVALID.append({"items": [{**ITEM, field: value}], "total": 1})


@pytest.mark.parametrize("payload", INVALID)
def test_invalid_contract_rejected_without_private_details(payload):
    with pytest.raises(
        YaMetricaServiceUnavailableError, match="^Metrica service unavailable$"
    ):
        YaMetricaServiceClient.parse_response(httpx.Response(200, json=payload))


@pytest.mark.parametrize(
    "payload", [{"items": [], "total": 0}, {"items": [], "total": 15}]
)
def test_empty_and_beyond_offset(payload):
    assert (
        YaMetricaServiceClient.parse_response(httpx.Response(200, json=payload)).total
        == payload["total"]
    )


@pytest.mark.parametrize(
    "status",
    [201, 202, 204, 301, 302, 400, 401, 403, 404, 409, 422, 429, 500, 502, 503],
)
async def test_unexpected_status_safe_and_no_retry(status):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            status, json={"detail": "private"}, headers={"Location": "/other"}
        )

    client = YaMetricaServiceClient(
        base_url="http://peer", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(
        YaMetricaServiceUnavailableError, match="^Metrica service unavailable$"
    ):
        await client.list_tasks(equestrian_id=uuid4(), limit=20, offset=0)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "error_class",
    [
        httpx.ReadTimeout,
        httpx.ConnectTimeout,
        httpx.ConnectError,
        httpx.ReadError,
        httpx.RemoteProtocolError,
    ],
)
async def test_transport_safe_and_no_retry(error_class):
    calls = []

    def handler(request):
        calls.append(request)
        raise error_class("private transport detail", request=request)

    client = YaMetricaServiceClient(
        base_url="http://peer", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(
        YaMetricaServiceUnavailableError, match="^Metrica service unavailable$"
    ):
        await client.list_tasks(equestrian_id=uuid4(), limit=20, offset=0)
    assert len(calls) == 1


async def test_constructor_timeout_trust_env_headers_no_logs(caplog, monkeypatch):
    calls = []
    tenant = uuid4()
    monkeypatch.setenv("HTTP_PROXY", "http://invalid-proxy.test:9999")

    def handler(request):
        calls.append(request)
        assert request.extensions["timeout"] == {
            key: 4.0 for key in ("connect", "read", "write", "pool")
        }
        assert request.headers["X-Equestrian-Id"] == str(tenant)
        assert (
            "cookie" not in request.headers and "authorization" not in request.headers
        )
        assert dict(request.url.params) == {"limit": "100", "offset": "20"}
        return httpx.Response(200, json=PAYLOAD)

    original = httpx.AsyncClient
    with patch(
        "clients.ya_metrica_service.client.httpx.AsyncClient", wraps=original
    ) as factory:
        with caplog.at_level(logging.INFO, logger="httpx"):
            client = YaMetricaServiceClient(
                base_url="http://private-peer/", transport=httpx.MockTransport(handler)
            )
            result = await client.list_tasks(equestrian_id=tenant, limit=100, offset=20)
        assert factory.call_args.kwargs["trust_env"] is False
        assert factory.call_args.kwargs["timeout"] == 4.0
        assert factory.call_args.kwargs["follow_redirects"] is False
    assert result.total == 1 and len(calls) == 1
    assert "private-peer" not in caplog.text and "offset" not in caplog.text


@pytest.mark.parametrize(
    "body", [b"invalid json private", b"null", b'{"items":[],"total":"0"}']
)
async def test_invalid_json_dto_safe(body):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, content=body)

    client = YaMetricaServiceClient(
        base_url="http://peer", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(
        YaMetricaServiceUnavailableError, match="^Metrica service unavailable$"
    ):
        await client.list_tasks(equestrian_id=uuid4(), limit=20, offset=0)
    assert len(calls) == 1


async def test_settings_default_override_and_di_constructor(monkeypatch):
    monkeypatch.delenv("YA_METRICA_SERVICE_URL", raising=False)
    default = Settings(_env_file=None)
    assert default.ya_metrica_service_url == "http://eqsitecms-ya-metrica-service:8000"
    configured = Settings(
        _env_file=None, YA_METRICA_SERVICE_URL="http://configured-peer"
    )
    with (
        patch("depends.services.settings", configured),
        patch("depends.services.YaMetricaServiceClient") as factory,
    ):
        await get_ya_metrica_service_client()
    factory.assert_called_once_with(base_url="http://configured-peer")


@pytest.mark.parametrize(
    "value",
    [
        0,
        1.5,
        -1,
        True,
        False,
        None,
        "0",
        "1700000000",
        "invalid",
        "2026-11-06",
        "2026-11-06T00:00:00",
        "2026-11-06 00:00:00Z",
        "2026-13-06T00:00:00Z",
    ],
)
async def test_created_at_invalid_wire_type_schema_and_client(value):
    payload = {"items": [{**ITEM, "created_at": value}], "total": 1}
    with pytest.raises(ValidationError):
        MetricaTaskListOutDto.model_validate(payload)
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=payload)

    client = YaMetricaServiceClient(
        base_url="http://peer", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(
        YaMetricaServiceUnavailableError, match="^Metrica service unavailable$"
    ):
        await client.list_tasks(equestrian_id=uuid4(), limit=20, offset=0)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "value",
    [
        "2026-11-06T00:00:00Z",
        "2026-11-06T03:00:00+03:00",
        "2026-11-06T00:00:00.123456Z",
        "2026-11-05T19:00:00-05:00",
    ],
)
def test_created_at_valid_serialized_aware_datetime(value):
    payload = {"items": [{**ITEM, "created_at": value}], "total": 1}
    dto = YaMetricaServiceClient.parse_response(httpx.Response(200, json=payload))
    assert dto.items[0].created_at.tzinfo is not None
    # Повторный JSON из production DTO остаётся допустимым wire payload.
    assert (
        YaMetricaServiceClient.parse_response(
            httpx.Response(200, content=dto.model_dump_json())
        )
        == dto
    )
