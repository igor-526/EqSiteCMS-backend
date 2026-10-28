"""UT-YX-11..22: HTTP boundary + настоящий use-case, без живого peer."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from clients.yandex_service.schemas import (
    YandexAccountOutDto,
    YandexAccountsOutDto,
    YandexMetricaConnectedCounterOutDto,
    YandexMetricaConnectionOutDto,
)
from core.entities.user import UserScope
from core.exceptions.auth import InvalidCredentials
from core.exceptions.base import ClientError
from core.protocols.yandex_service import (
    YandexServiceClientProtocol,
    YandexServiceUnavailableError,
)
from core.schemas.users import UserOutDto
from core.services.yandex_proxy import YandexProxyService
from depends.services import get_current_user, get_yandex_proxy_service
from main import app

ACCOUNT_ID = uuid4()
ROUTES = [
    ("GET", "/auth/link", "get_auth_link"),
    ("POST", "/auth/code", "exchange_code"),
    ("GET", "/accounts", "list_accounts"),
    ("DELETE", f"/accounts/{ACCOUNT_ID}", "delete_account"),
    ("GET", "/metrica/counters", "list_counters"),
    ("GET", "/metrica/connection", "get_connection"),
    ("POST", "/metrica/connection", "set_connection"),
    ("DELETE", "/metrica/connection", "delete_connection"),
]


def actor(*scopes):
    return UserOutDto(
        id=uuid4(),
        equestrian_id=uuid4(),
        username="seo-specialist",
        created_at=datetime.now(UTC),
        scopes=[
            UserScope(scope_name=scope, scope_description="test") for scope in scopes
        ],
    )


@pytest.fixture
def boundary():
    user = actor("SEO")
    peer = AsyncMock(spec=YandexServiceClientProtocol)
    account = YandexAccountOutDto(
        id=ACCOUNT_ID,
        yandex_id="123",
        yandex_login="test",
        display_name="Test",
        email="test@example.invalid",
        yandex_phone="+70000000000",
    )
    connection = YandexMetricaConnectionOutDto(
        id=uuid4(),
        counter_id="123",
        yandex_account=account,
    )
    peer.get_auth_link.return_value = {
        "auth_link": f"https://oauth.yandex.ru/?state={user.equestrian_id}"
    }
    peer.exchange_code.return_value = account
    peer.list_accounts.return_value = YandexAccountsOutDto(items=[account], total=1)
    peer.list_counters.return_value = {
        "items": [{"counter_id": 123, "site": "https://example.invalid"}],
        "total": 1,
    }
    peer.get_connection.return_value = YandexMetricaConnectedCounterOutDto(
        counter=connection
    )
    peer.set_connection.return_value = connection
    peer.delete_account.return_value = None
    peer.delete_connection.return_value = None
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_yandex_proxy_service] = lambda: YandexProxyService(
        peer
    )
    try:
        yield TestClient(app), peer, user, account, connection
    finally:
        app.dependency_overrides.clear()


def request(boundary, method, path, **kwargs):
    client, _, user, _, _ = boundary
    if method == "POST":
        kwargs.setdefault(
            "json",
            {"code": "test-code", "state": str(user.equestrian_id)}
            if path == "/auth/code"
            else {"yandex_account_id": str(ACCOUNT_ID), "counter_id": "123"},
        )
    if path == "/metrica/counters":
        kwargs.setdefault("params", {"account_id": str(ACCOUNT_ID)})
    return client.request(method, "/api/yandex" + path, **kwargs)


@pytest.mark.parametrize("method,path,_", ROUTES)
def test_ut11_anonymous_denied_before_peer(boundary, method, path, _):
    async def anonymous():
        raise InvalidCredentials("Отсутствуют учетные данные")

    app.dependency_overrides[get_current_user] = anonymous
    assert request(boundary, method, path).status_code == 401
    assert not boundary[1].mock_calls


@pytest.mark.parametrize(
    "scopes",
    [
        (),
        ("ADMIN",),
        ("SUPERUSER",),
        ("DEVELOPER",),
        ("USER_MANAGER",),
        ("UNKNOWN",),
        ("SUPERUSER", "DEVELOPER"),
    ],
)
@pytest.mark.parametrize("method,path,_", ROUTES)
def test_ut12_without_seo_denied_before_peer(boundary, scopes, method, path, _):
    app.dependency_overrides[get_current_user] = lambda: actor(*scopes)
    assert request(boundary, method, path).status_code == 403
    assert not boundary[1].mock_calls


@pytest.mark.parametrize("method,path,operation", ROUTES)
@pytest.mark.parametrize("extra_scopes", [(), ("ADMIN",)])
def test_ut13_seo_success(boundary, method, path, operation, extra_scopes):
    boundary[2].scopes.extend(
        UserScope(scope_name=scope, scope_description="test") for scope in extra_scopes
    )
    response = request(boundary, method, path)
    assert response.status_code == (204 if method == "DELETE" else 200)
    getattr(boundary[1], operation).assert_awaited_once()
    if method == "DELETE":
        assert response.content == b""
    elif path == "/auth/link":
        assert str(boundary[2].equestrian_id) in response.json()["auth_link"]
    elif path == "/auth/code":
        assert response.json() == boundary[3].model_dump(mode="json")
    elif path == "/accounts":
        assert response.json() == {
            "items": [boundary[3].model_dump(mode="json")],
            "total": 1,
        }
    elif path == "/metrica/counters":
        assert response.json() == {
            "items": [{"counter_id": 123, "site": "https://example.invalid"}],
            "total": 1,
        }
    elif method == "GET":
        assert response.json() == {"counter": boundary[4].model_dump(mode="json")}
    else:
        assert response.json() == boundary[4].model_dump(mode="json")


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"code": "x"},
        {"state": "x"},
        {"code": "", "state": "x"},
        {"code": "x", "state": ""},
        {"code": " ", "state": "x"},
        {"code": "x", "state": " "},
        {"code": None, "state": "x"},
        [],
        None,
    ],
)
def test_ut14_invalid_auth_body_is_400(boundary, body):
    response = boundary[0].post("/api/yandex/auth/code", json=body)
    assert response.status_code == 400
    assert not boundary[1].mock_calls


def test_ut14_malformed_json_is_400(boundary):
    assert (
        boundary[0]
        .post(
            "/api/yandex/auth/code",
            content="{broken",
            headers={"Content-Type": "application/json"},
        )
        .status_code
        == 400
    )
    assert not boundary[1].mock_calls


@pytest.mark.parametrize("state", [str(uuid4()), "not-a-uuid"])
def test_ut15_foreign_state_denied(boundary, state):
    assert (
        request(
            boundary, "POST", "/auth/code", json={"code": "x", "state": state}
        ).status_code
        == 403
    )
    assert not boundary[1].mock_calls


def test_ut15_tenant_in_body_is_ignored(boundary):
    _, peer, user, _, _ = boundary
    assert (
        request(
            boundary,
            "POST",
            "/auth/code",
            json={
                "code": "x",
                "state": str(user.equestrian_id),
                "equestrian_id": str(uuid4()),
            },
        ).status_code
        == 200
    )
    peer.exchange_code.assert_awaited_once_with(
        code="x", equestrian_id=user.equestrian_id
    )


@pytest.mark.parametrize(
    "path,operation",
    [("/accounts", "list_accounts"), ("/metrica/counters", "list_counters")],
)
@pytest.mark.parametrize(
    "params,expected",
    [
        ({"limit": "abc"}, None),
        ({"offset": "abc"}, None),
        ({"offset": -1}, (20, 0)),
        ({"limit": 1000}, (100, 0)),
        ({"limit": 0}, (1, 0)),
        ({"limit": 1, "offset": 1}, (1, 1)),
        ({}, (20, 0)),
    ],
)
def test_ut16_pagination(boundary, path, operation, params, expected):
    params = {
        **params,
        "account_id": str(ACCOUNT_ID),
        "search": "test",
        "equestrian_id": str(uuid4()),
    }
    response = request(boundary, "GET", path, params=params)
    if expected is None:
        assert response.status_code == 400
        assert not boundary[1].mock_calls
    else:
        assert response.status_code == 200
        kwargs = getattr(boundary[1], operation).await_args.kwargs
        assert (kwargs["limit"], kwargs["offset"], kwargs["search"]) == (
            *expected,
            "test",
        )
        if path == "/accounts":
            assert kwargs["equestrian_id"] == boundary[2].equestrian_id


@pytest.mark.parametrize(
    "method,path", [("DELETE", "/accounts/not-a-uuid"), ("GET", "/metrica/counters")]
)
@pytest.mark.parametrize("params", [{}, {"account_id": "broken"}])
def test_ut17_18_invalid_account_is_400(boundary, method, path, params):
    assert request(boundary, method, path, params=params).status_code == 400
    assert not boundary[1].mock_calls


@pytest.mark.parametrize("method,path,operation", [ROUTES[3], ROUTES[4], ROUTES[6]])
def test_ut17_18_19_foreign_or_missing_account_is_404(
    boundary, method, path, operation
):
    peer = boundary[1]
    peer.list_accounts.return_value = YandexAccountsOutDto(items=[], total=0)
    response = request(boundary, method, path)
    assert response.status_code == 404
    assert response.json() == {"detail": "Аккаунт Яндекс не найден"}
    getattr(peer, operation).assert_not_awaited()
    peer.list_accounts.assert_awaited_once_with(
        equestrian_id=boundary[2].equestrian_id, limit=100, offset=0
    )


@pytest.mark.parametrize(
    "counter",
    ["", " ", "12a", "1" * 32, "123\n", "１２３", None, True, -1, 1.2, [], {}],
)
def test_ut19_invalid_counter_is_400(boundary, counter):
    assert (
        request(
            boundary,
            "POST",
            "/metrica/connection",
            json={"yandex_account_id": str(ACCOUNT_ID), "counter_id": counter},
        ).status_code
        == 400
    )
    assert not boundary[1].mock_calls


@pytest.mark.parametrize(
    "body", [{}, {"yandex_account_id": "bad", "counter_id": "1"}, {"counter_id": "1"}]
)
def test_ut19_invalid_connection_body_is_400(boundary, body):
    assert (
        request(boundary, "POST", "/metrica/connection", json=body).status_code == 400
    )
    assert not boundary[1].mock_calls


@pytest.mark.parametrize("counter", [0, 123, "0", "9" * 31])
def test_ut19_numeric_counter_and_session_tenant(boundary, counter):
    assert (
        request(
            boundary,
            "POST",
            "/metrica/connection",
            json={
                "yandex_account_id": str(ACCOUNT_ID),
                "counter_id": counter,
                "equestrian_id": str(uuid4()),
            },
        ).status_code
        == 200
    )
    boundary[1].set_connection.assert_awaited_once_with(
        equestrian_id=boundary[2].equestrian_id,
        yandex_account_id=ACCOUNT_ID,
        counter_id=str(counter),
    )
    boundary[1].list_counters.assert_not_awaited()


def test_ut20_delete_connection_is_idempotent(boundary):
    peer = boundary[1]
    peer.get_connection.side_effect = [
        YandexMetricaConnectedCounterOutDto(counter=boundary[4]),
        YandexMetricaConnectedCounterOutDto(counter=None),
    ]
    assert request(boundary, "DELETE", "/metrica/connection").status_code == 204
    assert request(boundary, "DELETE", "/metrica/connection").status_code == 204
    peer.delete_connection.assert_awaited_once_with(counter_record_id=boundary[4].id)


def test_empty_gets(boundary):
    boundary[1].get_connection.return_value = YandexMetricaConnectedCounterOutDto(
        counter=None
    )
    assert request(boundary, "GET", "/metrica/connection").json() == {"counter": None}
    boundary[1].list_accounts.return_value = YandexAccountsOutDto(items=[], total=0)
    assert request(boundary, "GET", "/accounts").json() == {"items": [], "total": 0}


@pytest.mark.parametrize(
    "method,path,operation", [route for route in ROUTES if route[0] != "DELETE"]
)
def test_ut21_response_whitelist(boundary, method, path, operation):
    peer = boundary[1]
    raw = getattr(peer, operation).return_value
    if hasattr(raw, "model_dump"):
        raw = raw.model_dump(mode="json")
    secrets = {
        "enc_access_token": "SECRET",
        "access_token": "SECRET",
        "token_expires_at": "SECRET",
        "avatar": "SECRET",
        "equestrian_id": "SECRET",
    }

    def inject(value):
        if isinstance(value, dict):
            return {**{key: inject(item) for key, item in value.items()}, **secrets}
        if isinstance(value, list):
            return [inject(item) for item in value]
        return value

    getattr(peer, operation).return_value = inject(raw)
    response = request(boundary, method, path)
    assert response.status_code == 200
    assert "SECRET" not in response.text
    assert all(key not in response.text for key in secrets)


@pytest.mark.parametrize("method,path,operation", ROUTES)
@pytest.mark.parametrize("unavailable", [False, True])
def test_ut22_downstream_errors(boundary, method, path, operation, unavailable):
    # DELETE connection first reads connection; exercise its delete as well.
    getattr(boundary[1], operation).side_effect = (
        YandexServiceUnavailableError()
        if unavailable
        else ClientError("Запрос отклонён")
    )
    response = request(boundary, method, path)
    assert response.status_code == (502 if unavailable else 400)
    assert response.json() == {
        "detail": "Yandex service unavailable" if unavailable else "Запрос отклонён"
    }
    assert "http" not in response.text
    assert "eqsitecms-yandex-service" not in response.text


@pytest.mark.parametrize("method,path,_", ROUTES)
@pytest.mark.parametrize(
    "scopes,status",
    [
        (None, 401),
        ((), 403),
        (("ADMIN",), 403),
        (("SUPERUSER",), 403),
        (("DEVELOPER",), 403),
        (("USER_MANAGER",), 403),
        (("ADMIN", "SUPERUSER", "DEVELOPER"), 403),
    ],
)
@pytest.mark.parametrize("body", [b"{broken", b"{}", b"[]"])
def test_ut_access_denied_before_body_and_peer(
    boundary, method, path, _, scopes, status, body, monkeypatch
):
    from starlette.requests import Request

    async def unread_body(self):
        pytest.fail("body read before access check")

    monkeypatch.setattr(Request, "body", unread_body)
    if scopes is None:
        app.dependency_overrides.pop(get_current_user)
    else:
        app.dependency_overrides[get_current_user] = lambda: actor(*scopes)
    response = boundary[0].request(
        method,
        "/api/yandex" + path,
        content=body,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == status
    assert not boundary[1].mock_calls


@pytest.mark.parametrize("method,path,_", ROUTES)
@pytest.mark.parametrize("token", ["invalid-session", "expired"])
def test_ut_access_invalid_or_expired_cookie(boundary, method, path, _, token):
    import jwt

    # Synthetic expired JWT: never use or print a real session/signing secret.
    if token == "expired":
        token = jwt.encode(
            {"sub": str(boundary[2].id), "exp": 0}, "unit-test-only", algorithm="HS256"
        )
    app.dependency_overrides.pop(get_current_user)
    response = boundary[0].request(
        method,
        "/api/yandex" + path,
        content=b"{broken",
        headers={"Content-Type": "application/json", "Cookie": "access_token=" + token},
    )
    assert response.status_code == 401
    assert not boundary[1].mock_calls


def test_ut_access_openapi_body_schemas():
    from fastapi import FastAPI
    from api.yandex import router

    schema_app = FastAPI()
    schema_app.include_router(router, prefix="/api")
    paths = schema_app.openapi()["paths"]
    for method, path, _ in ROUTES:
        operation = paths[
            "/api/yandex" + path.replace(str(ACCOUNT_ID), "{account_id}")
        ][method.lower()]
        if method in {"POST", "PATCH"}:
            body = operation["requestBody"]
            assert body["required"] is True
            assert body["content"]["application/json"]["schema"]["type"] == "object"
        else:
            assert "requestBody" not in operation
