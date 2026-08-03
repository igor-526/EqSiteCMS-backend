from unittest.mock import AsyncMock
from uuid import UUID

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from core.entities.equestrian import EquestrianContext
from depends.services import (
    get_current_user,
    get_horse_service,
    get_protected_equestrian_context,
    get_read_equestrian_context,
)
from main import app

TENANT_ID = UUID("11111111-1111-4111-8111-111111111111")
SERVICE_A = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
SERVICE_B = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")


def _client_with_public_read(service: AsyncMock) -> TestClient:
    service.get_filtered_horses.return_value = {"items": [], "total": 0}
    app.dependency_overrides[get_horse_service] = lambda: service
    app.dependency_overrides[get_read_equestrian_context] = lambda: EquestrianContext(
        id=TENANT_ID, source="unit-test"
    )
    return TestClient(app)


def _clear_overrides() -> None:
    app.dependency_overrides.pop(get_horse_service, None)
    app.dependency_overrides.pop(get_read_equestrian_context, None)


def test_api_accepts_one_service_uuid() -> None:
    service = AsyncMock()
    client = _client_with_public_read(service)
    try:
        response = client.get(f"/api/horses?services={SERVICE_A}")
    finally:
        _clear_overrides()

    assert response.status_code == 200
    assert service.get_filtered_horses.await_args.kwargs["services"] == [SERVICE_A]


def test_api_accepts_repeated_service_uuid_keys() -> None:
    service = AsyncMock()
    client = _client_with_public_read(service)
    try:
        response = client.get(f"/api/horses?services={SERVICE_A}&services={SERVICE_B}")
    finally:
        _clear_overrides()

    assert response.status_code == 200
    assert service.get_filtered_horses.await_args.kwargs["services"] == [
        SERVICE_A,
        SERVICE_B,
    ]


def test_malformed_service_uuid_returns_422_before_service() -> None:
    service = AsyncMock()
    client = _client_with_public_read(service)
    try:
        response = client.get("/api/horses?services=not-a-uuid")
    finally:
        _clear_overrides()

    assert response.status_code == 422
    service.get_filtered_horses.assert_not_awaited()


def test_horse_list_keeps_public_read_dependency() -> None:
    route = next(
        route
        for route in app.routes
        if isinstance(route, APIRoute)
        and route.path == "/api/horses"
        and "GET" in route.methods
    )
    dependency_calls = {dependency.call for dependency in route.dependant.dependencies}

    assert get_read_equestrian_context in dependency_calls
    assert get_current_user not in dependency_calls
    assert get_protected_equestrian_context not in dependency_calls


def test_openapi_documents_repeated_or_service_filter_and_public_read() -> None:
    operation = app.openapi()["paths"]["/api/horses"]["get"]
    services_parameter = next(
        parameter
        for parameter in operation["parameters"]
        if parameter["name"] == "services"
    )

    array_schema = next(
        schema
        for schema in services_parameter["schema"]["anyOf"]
        if schema.get("type") == "array"
    )
    assert array_schema["items"]["format"] == "uuid"
    assert "OR-семантику" in services_parameter["description"]
    assert "Public Read" in operation["description"]


def test_relation_writes_keep_authenticated_and_protected_dependencies() -> None:
    relation_write_routes = [
        route
        for route in app.routes
        if isinstance(route, APIRoute)
        and route.path.startswith("/api/horses/{horse_id}/services")
        and route.methods.intersection({"POST", "PATCH", "DELETE"})
    ]

    assert {next(iter(route.methods)) for route in relation_write_routes} >= {
        "POST",
        "PATCH",
        "DELETE",
    }
    for route in relation_write_routes:
        dependency_calls = {
            dependency.call for dependency in route.dependant.dependencies
        }
        assert get_current_user in dependency_calls
        assert get_protected_equestrian_context in dependency_calls
