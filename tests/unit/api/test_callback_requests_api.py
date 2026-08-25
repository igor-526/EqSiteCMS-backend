from uuid import uuid4

import pytest
from pydantic import ValidationError
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock

from core.entities.callback_request import CallbackRequest
from core.schemas.callbackrequest import (
    CallbackRequestDeliveryInDto,
    CallbackRequestOutDto,
    CallbackRequestSpamInDto,
    CallbackRequestStatusInDto,
)
from main import app
from core.entities.equestrian import EquestrianContext
from core.exceptions.base import UnprocessableEntityError
from depends.services import (
    get_callback_request_service,
    get_current_user,
    get_read_equestrian_context,
)


def _route_methods() -> set[tuple[str, str]]:
    return {
        (method, route.path)
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }


def test_all_callback_routes_registered() -> None:
    routes = _route_methods()
    expected = {
        ("POST", "/api/callback_requests"),
        ("GET", "/api/callback_requests/statuses"),
        ("GET", "/api/callback_requests"),
        ("GET", "/api/callback_requests/{id}"),
        ("PATCH", "/api/callback_requests/{id}/status"),
        ("PATCH", "/api/callback_requests/{id}/spam"),
        ("PATCH", "/api/service/callback_requests/{id}/status"),
        ("PATCH", "/api/service/callback_requests/{id}/spam"),
        ("PATCH", "/api/service/callback_requests/{id}/notifications-delivered"),
    }
    assert expected <= routes


@pytest.mark.parametrize(
    "schema,body",
    [
        (CallbackRequestStatusInDto, {"status": 2, "name": "hack"}),
        (CallbackRequestSpamInDto, {"is_spam": True, "phone": "hack"}),
        (
            CallbackRequestDeliveryInDto,
            {"notifications_delivered": True, "tenant": str(uuid4())},
        ),
    ],
)
def test_narrow_mutations_forbid_extra_fields(schema, body) -> None:
    with pytest.raises(ValidationError):
        schema.model_validate(body)


def test_public_response_does_not_expose_tenant() -> None:
    entity = CallbackRequest(equestrian_id=uuid4(), phone="123")
    response = CallbackRequestOutDto.model_validate(
        entity.model_dump(exclude={"equestrian_id"})
    )
    payload = response.model_dump()
    assert (
        "equestrian_id" not in payload
        and "tenant" not in payload
        and "service_key" not in payload
    )
    assert payload["created_at"].tzinfo is not None


def test_openapi_documents_access_boundaries() -> None:
    schema = app.openapi()
    paths = schema["paths"]
    assert paths["/api/callback_requests"]["post"].get("security") in (None, [])
    assert "/api/callback_requests/{id}" in paths
    assert "/api/service/callback_requests/{id}/notifications-delivered" in paths


@pytest.fixture
def callback_client():
    service = AsyncMock()
    user = AsyncMock()
    user.equestrian_id = uuid4()
    user.scopes = []
    app.dependency_overrides[get_callback_request_service] = lambda: service
    app.dependency_overrides[get_read_equestrian_context] = lambda: EquestrianContext(
        id=uuid4(), source="test"
    )
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        yield TestClient(app), service
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"phone": ""},
        {"phone": "x" * 64},
        {"phone": "1", "name": "x" * 128},
        {"phone": "1", "comment": "x" * 2001},
    ],
)
def test_callback_create_validation_returns_422(callback_client, body) -> None:
    client, service = callback_client
    response = client.post("/api/callback_requests", json=body)
    assert response.status_code == 422
    service.create.assert_not_awaited()


@pytest.mark.parametrize("query", ["sort_by=invalid", "name=" + "x" * 129])
def test_callback_query_validation_returns_422(callback_client, query) -> None:
    client, service = callback_client
    response = client.get(f"/api/callback_requests?{query}")
    assert response.status_code == 422


def test_callback_regex_domain_error_returns_422(callback_client) -> None:
    client, service = callback_client
    service.list.side_effect = UnprocessableEntityError("Опасное выражение")
    response = client.get("/api/callback_requests?name=%28a%2B%29%2B")
    assert response.status_code == 422
