"""UT-GW-01: зарегистрированный route → реальный use case → Protocol."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from clients.ya_metrica_service.client import YaMetricaServiceClient
from clients.ya_metrica_service.schemas import MetricaTaskListOutDto
from core.entities.user import UserScope
from core.protocols.ya_metrica_service import (
    YaMetricaServiceClientProtocol,
    YaMetricaServiceUnavailableError,
)
from core.schemas.users import UserOutDto
from depends.services import (
    get_current_user,
    get_seo_service_client,
    get_ya_metrica_service_client,
)
from main import app

PATH = "/api/seo/metrica/tasks"


@pytest.fixture
def boundary():
    user = UserOutDto(
        id=uuid4(),
        equestrian_id=uuid4(),
        username="seo",
        created_at=datetime.now(UTC),
        scopes=[UserScope(scope_name="SEO", scope_description="test")],
    )
    peer = AsyncMock(spec=YaMetricaServiceClientProtocol)
    peer.list_tasks.return_value = MetricaTaskListOutDto(items=[], total=0)
    seo = AsyncMock()
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_ya_metrica_service_client] = lambda: peer
    app.dependency_overrides[get_seo_service_client] = seo
    try:
        yield TestClient(app), peer, user, seo
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("query", ["", "?limit=bad&offset=-1"])
def test_anonymous_before_query_and_peer(boundary, query):
    client, peer, _, seo = boundary
    del app.dependency_overrides[get_current_user]
    assert client.get(PATH + query).status_code == 401
    assert not peer.mock_calls and not seo.mock_calls


@pytest.mark.parametrize(
    "roles",
    [
        (),
        ("ADMIN",),
        ("SUPERUSER",),
        ("DEVELOPER",),
        ("USER_MANAGER",),
        ("ADMIN", "SUPERUSER", "DEVELOPER"),
    ],
)
@pytest.mark.parametrize("query", ["", "?limit=bad&offset=-1"])
def test_non_seo_before_query_and_peer(boundary, roles, query):
    client, peer, user, seo = boundary
    user.scopes = [
        UserScope(scope_name=role, scope_description="test") for role in roles
    ]
    assert client.get(PATH + query).status_code == 403
    assert not peer.mock_calls and not seo.mock_calls


@pytest.mark.parametrize("roles", [("SEO",), ("SEO", "ADMIN")])
@pytest.mark.parametrize(
    "query,limit,offset",
    [("", 20, 0), ("?limit=1&offset=0", 1, 0), ("?limit=100&offset=999", 100, 999)],
)
def test_seo_pagination_and_tenant_spoof(boundary, roles, query, limit, offset):
    client, peer, user, seo = boundary
    user.scopes = [
        UserScope(scope_name=role, scope_description="test") for role in roles
    ]
    query += ("&" if query else "?") + f"equestrian_id={uuid4()}"
    response = client.get(PATH + query, headers={"X-Equestrian-Id": str(uuid4())})
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}
    peer.list_tasks.assert_awaited_once_with(
        equestrian_id=user.equestrian_id, limit=limit, offset=offset
    )
    assert not seo.mock_calls


@pytest.mark.parametrize(
    "query",
    [
        "limit=0",
        "limit=101",
        "limit=-1",
        "limit=1.0",
        "limit=bad",
        "limit=",
        "offset=-1",
        "offset=1.5",
        "offset=true",
        "offset=",
        "limit=%2B1",
        "offset=%201",
    ],
)
def test_invalid_query_is_400_without_peer(boundary, query):
    client, peer, _, seo = boundary
    assert client.get(PATH + "?" + query).status_code == 400
    assert not peer.mock_calls and not seo.mock_calls


def test_safe_502_not_false_empty_success(boundary):
    client, peer, _, _ = boundary
    peer.list_tasks.side_effect = YaMetricaServiceUnavailableError()
    response = client.get(PATH)
    assert response.status_code == 502
    assert response.json() == {"detail": "Metrica service unavailable"}
    peer.list_tasks.assert_awaited_once()


def test_real_client_through_di_does_not_forward_credentials(boundary):
    client, _, user, seo = boundary
    calls = []

    def handler(request):
        calls.append(request)
        assert request.url.path == "/api/metrica/tasks"
        assert dict(request.url.params) == {"limit": "20", "offset": "20"}
        assert request.headers["X-Equestrian-Id"] == str(user.equestrian_id)
        assert (
            "cookie" not in request.headers and "authorization" not in request.headers
        )
        return httpx.Response(200, json={"items": [], "total": 15})

    app.dependency_overrides[get_ya_metrica_service_client] = lambda: (
        YaMetricaServiceClient(
            base_url="http://metrica.test", transport=httpx.MockTransport(handler)
        )
    )
    response = client.get(
        PATH + "?offset=20&equestrian_id=" + str(uuid4()),
        headers={
            "Cookie": "session=browser-private",
            "Authorization": "Bearer browser-private",
            "X-Equestrian-Id": str(uuid4()),
        },
    )
    assert response.status_code == 200 and response.json() == {"items": [], "total": 15}
    assert len(calls) == 1 and not seo.mock_calls


def test_numeric_peer_created_at_is_safe_502(boundary):
    client, _, _, _ = boundary
    payload = {
        "items": [
            {
                "id": "parsing:synthetic",
                "type": "parsing",
                "status": "queued",
                "is_active": True,
                "created_at": 0,
            }
        ],
        "total": 1,
    }
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=payload)

    app.dependency_overrides[get_ya_metrica_service_client] = lambda: (
        YaMetricaServiceClient(
            base_url="http://metrica.test", transport=httpx.MockTransport(handler)
        )
    )
    response = client.get(PATH)
    assert response.status_code == 502
    assert response.json() == {"detail": "Metrica service unavailable"}
    assert len(calls) == 1
