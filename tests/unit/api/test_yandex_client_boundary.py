"""UT-YX-01..05: изолированная HTTP-граница без живого peer."""

import json
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError

from clients.yandex_service.client import REJECTED_DETAIL, YandexServiceClient
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
from core.exceptions.base import ClientError
from core.protocols.yandex_service import YandexServiceUnavailableError

TENANT, ACCOUNT, RECORD = uuid4(), uuid4(), uuid4()
ACCOUNT_BODY = {
    "id": str(ACCOUNT),
    "yandex_id": "123",
    "yandex_login": "test",
    "display_name": "Тест",
    "email": None,
    "yandex_phone": None,
}
CONNECTION_BODY = {
    "id": str(RECORD),
    "counter_id": "123",
    "yandex_account": ACCOUNT_BODY,
}
CASES = [
    (
        "get_auth_link",
        {"equestrian_id": TENANT},
        "GET",
        "/api/auth/link",
        {"equestrian_id": str(TENANT)},
        None,
        {"auth_link": "https://oauth.yandex.ru/"},
    ),
    (
        "exchange_code",
        {"equestrian_id": TENANT, "code": "test-code"},
        "POST",
        "/api/auth/code",
        {},
        {"equestrian_id": str(TENANT), "code": "test-code"},
        ACCOUNT_BODY,
    ),
    (
        "list_accounts",
        {"equestrian_id": TENANT, "search": "тест", "limit": 3, "offset": 2},
        "GET",
        "/api/accounts/",
        {"equestrian_id": str(TENANT), "search": "тест", "limit": "3", "offset": "2"},
        None,
        {"items": [ACCOUNT_BODY], "total": 5},
    ),
    (
        "delete_account",
        {"account_id": ACCOUNT},
        "DELETE",
        f"/api/accounts/{ACCOUNT}",
        {},
        None,
        None,
    ),
    (
        "list_counters",
        {"account_id": ACCOUNT, "search": "site", "limit": 4, "offset": 1},
        "GET",
        "/api/metrica/counters",
        {"account_id": str(ACCOUNT), "search": "site", "limit": "4", "offset": "1"},
        None,
        {"items": [{"counter_id": 123, "site": "https://example.invalid"}], "total": 2},
    ),
    (
        "get_connection",
        {"equestrian_id": TENANT},
        "GET",
        f"/api/connections/metrica/{TENANT}",
        {},
        None,
        {"counter": CONNECTION_BODY},
    ),
    (
        "set_connection",
        {"equestrian_id": TENANT, "yandex_account_id": ACCOUNT, "counter_id": "123"},
        "POST",
        "/api/connections/metrica",
        {},
        {
            "equestrian_id": str(TENANT),
            "yandex_account_id": str(ACCOUNT),
            "counter_id": "123",
        },
        CONNECTION_BODY,
    ),
    (
        "delete_connection",
        {"counter_record_id": RECORD},
        "DELETE",
        f"/api/connections/metrica/{RECORD}",
        {},
        None,
        None,
    ),
]


@pytest.mark.parametrize("method,kwargs,verb,path,query,body,response_body", CASES)
async def test_ut_yx_01_02_all_requests(
    method, kwargs, verb, path, query, body, response_body
):
    requests = []

    def handler(request):
        requests.append(request)
        assert request.method == verb
        assert request.url.host == "peer.invalid"
        assert request.url.path == path
        assert dict(request.url.params) == query
        assert (json.loads(request.content) if request.content else None) == body
        for header in ("X-Service-Key", "Authorization", "Cookie"):
            assert header not in request.headers
        assert request.extensions["timeout"] == dict.fromkeys(
            ("connect", "read", "write", "pool"), 10.0
        )
        if response_body is None:
            return httpx.Response(204)
        return httpx.Response(200, json=response_body)

    client = YandexServiceClient(
        base_url="http://peer.invalid/", transport=httpx.MockTransport(handler)
    )
    result = await getattr(client, method)(**kwargs)
    assert len(requests) == 1
    assert (
        result.model_dump(mode="json") if result is not None else None
    ) == response_body


@pytest.mark.parametrize(
    "schema,payload",
    [
        (YandexAccountOutDto, ACCOUNT_BODY),
        (YandexAccountsOutDto, {"items": [ACCOUNT_BODY], "total": 1}),
        (YandexAuthLinkOutDto, {"auth_link": "https://oauth.yandex.ru/"}),
        (
            YandexMetricaCountersOutDto,
            {"items": [{"counter_id": 1, "site": "site"}], "total": 1},
        ),
        (YandexMetricaConnectionOutDto, CONNECTION_BODY),
        (YandexMetricaConnectedCounterOutDto, {"counter": CONNECTION_BODY}),
    ],
)
def test_ut_yx_03_nested_whitelists(schema, payload):
    def contaminate(value):
        if isinstance(value, dict):
            return {
                **{k: contaminate(v) for k, v in value.items()},
                "enc_access_token": "test-secret",
                "token_expires_at": "expiry",
                "equestrian_id": str(TENANT),
                "avatar": "hidden",
            }
        if isinstance(value, list):
            return [contaminate(v) for v in value]
        return value

    assert (
        schema.model_validate(contaminate(payload)).model_dump(mode="json") == payload
    )


@pytest.mark.parametrize(
    "counter", [1, "1", "0" * 31, "", "12a", "1" * 32, -1, 1.2, "123\n"]
)
def test_ut_yx_03_request_coercion_and_extra_ignored(counter):
    data = YandexMetricaSetConnectionInDto.model_validate(
        {
            "yandex_account_id": str(ACCOUNT),
            "counter_id": counter,
            "equestrian_id": str(TENANT),
        }
    )
    assert data.counter_id == str(counter)
    assert "equestrian_id" not in data.model_dump()
    assert YandexAuthCodeInDto.model_validate(
        {
            "code": "code",
            "state": "state",
            "equestrian_id": str(TENANT),
        }
    ).model_dump() == {"code": "code", "state": "state"}


@pytest.mark.parametrize("code,state", [("", ""), (" ", "\t"), ("code", "not-a-uuid")])
def test_auth_dto_leaves_business_validation_to_service(code, state):
    data = YandexAuthCodeInDto(code=code, state=state)
    assert data.model_dump() == {"code": code, "state": state}


@pytest.mark.parametrize("counter", [True, None, [], {}])
def test_ut_yx_03_structurally_invalid_counter(counter):
    with pytest.raises(ValidationError):
        YandexMetricaSetConnectionInDto.model_validate(
            {
                "yandex_account_id": ACCOUNT,
                "counter_id": counter,
            }
        )


@pytest.mark.parametrize(
    "payload,expected",
    [
        ({"detail": "Аккаунт не найден"}, "Аккаунт не найден"),
        ({"detail": "x" * 300}, "x" * 300),
        ({"detail": "x" * 301}, REJECTED_DETAIL),
        ({"detail": []}, REJECTED_DETAIL),
        ({}, REJECTED_DETAIL),
        (["error"], REJECTED_DETAIL),
    ],
)
async def test_ut_yx_04_peer_rejection(payload, expected):
    client = YandexServiceClient(
        base_url="http://peer.invalid",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(400, json=payload)
        ),
    )
    with pytest.raises(ClientError) as exc:
        await client.get_auth_link(equestrian_id=TENANT)
    assert str(exc.value) == expected


@pytest.mark.parametrize(
    "kind", ["connect", "timeout", "500", "404", "201", "json", "schema"]
)
async def test_ut_yx_05_unavailable(kind, caplog):
    def handler(request):
        if kind == "connect":
            raise httpx.ConnectError("private-host test-secret", request=request)
        if kind == "timeout":
            raise httpx.ReadTimeout("private-host test-secret", request=request)
        if kind.isdigit():
            return httpx.Response(int(kind), json={"detail": "test-secret"})
        if kind == "json":
            return httpx.Response(200, content=b"not-json test-secret")
        return httpx.Response(200, json={"unexpected": "test-secret"})

    client = YandexServiceClient(
        base_url="http://peer.invalid", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(YandexServiceUnavailableError) as exc:
        await client.get_auth_link(equestrian_id=TENANT)
    assert str(exc.value) == "Yandex service unavailable"
    assert exc.value.__suppress_context__ or exc.value.__context__ is None
    assert "test-secret" not in caplog.text


async def test_ut_yx_04_malformed_error_body():
    client = YandexServiceClient(
        base_url="http://peer.invalid",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(400, content=b"not-json")
        ),
    )
    with pytest.raises(ClientError, match=REJECTED_DETAIL):
        await client.get_auth_link(equestrian_id=TENANT)
