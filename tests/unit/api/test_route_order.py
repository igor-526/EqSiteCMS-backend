from __future__ import annotations

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


def test_breeds_routes_are_registered_before_horse_slug_catch_all() -> None:
    route_paths = [
        route.path
        for route in app.routes
        if isinstance(route, APIRoute)
        and route.path
        in {
            "/api/horses/breeds",
            "/api/horses/breeds/{slug_or_id}",
            "/api/horses/{slug_or_id}",
        }
    ]

    assert route_paths.index("/api/horses/breeds") < route_paths.index(
        "/api/horses/{slug_or_id}"
    )
    assert route_paths.index("/api/horses/breeds/{slug_or_id}") < route_paths.index(
        "/api/horses/{slug_or_id}"
    )


def test_coat_color_routes_are_registered_before_horse_slug_catch_all() -> None:
    route_paths = [
        route.path
        for route in app.routes
        if isinstance(route, APIRoute)
        and route.path
        in {
            "/api/horses/coat_colors",
            "/api/horses/coat_colors/{slug_or_id}",
            "/api/horses/{slug_or_id}",
        }
    ]

    assert route_paths.index("/api/horses/coat_colors") < route_paths.index(
        "/api/horses/{slug_or_id}"
    )
    assert route_paths.index(
        "/api/horses/coat_colors/{slug_or_id}"
    ) < route_paths.index("/api/horses/{slug_or_id}")


def test_horse_service_routes_are_registered_before_horse_slug_catch_all() -> None:
    route_paths = [
        route.path
        for route in app.routes
        if isinstance(route, APIRoute)
        and route.path
        in {
            "/api/horses/services",
            "/api/horses/services/{slug_or_id}",
            "/api/horses/{slug_or_id}",
        }
    ]

    assert route_paths.index("/api/horses/services") < route_paths.index(
        "/api/horses/{slug_or_id}"
    )
    assert route_paths.index("/api/horses/services/{slug_or_id}") < route_paths.index(
        "/api/horses/{slug_or_id}"
    )


def test_horse_pedigree_route_registered_with_path_separator() -> None:
    pedigree_paths = [
        route.path
        for route in app.routes
        if isinstance(route, APIRoute) and "pedigree" in route.path
    ]

    assert "/api/horses/{horse_id}/pedigree/{mode}" in pedigree_paths


def test_horse_pedigree_mode_contract_uses_dam() -> None:
    openapi = app.openapi()
    mode_schema = openapi["paths"]["/api/horses/{horse_id}/pedigree/{mode}"]["get"][
        "parameters"
    ][1]["schema"]

    assert mode_schema["enum"] == ["sire", "dam", "children"]


def test_horse_pedigree_invalid_mode_returns_structural_422() -> None:
    client = TestClient(app)
    app.dependency_overrides[get_read_equestrian_context] = lambda: EquestrianContext(
        id=UUID("11111111-1111-4111-8111-111111111111"),
        source="unit-test",
    )

    try:
        response = client.get(
            "/api/horses/11111111-1111-4111-8111-111111111111/pedigree/badmode"
        )
    finally:
        app.dependency_overrides.pop(get_read_equestrian_context, None)

    assert response.status_code == 422
    assert "path -> mode" in response.json()["detail"]


def test_horse_create_extra_kind_returns_structural_422() -> None:
    client = TestClient(app)
    app.dependency_overrides[get_current_user] = lambda: object()
    app.dependency_overrides[get_protected_equestrian_context] = (
        lambda: EquestrianContext(
            id=UUID("11111111-1111-4111-8111-111111111111"),
            source="unit-test",
        )
    )
    app.dependency_overrides[get_horse_service] = lambda: object()

    try:
        response = client.post("/api/horses", json={"name": "Test", "kind": "horse"})
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_protected_equestrian_context, None)
        app.dependency_overrides.pop(get_horse_service, None)

    assert response.status_code == 422
    assert "body -> kind" in response.json()["detail"]


def test_horse_update_extra_kind_returns_structural_422() -> None:
    client = TestClient(app)
    app.dependency_overrides[get_current_user] = lambda: object()
    app.dependency_overrides[get_protected_equestrian_context] = (
        lambda: EquestrianContext(
            id=UUID("11111111-1111-4111-8111-111111111111"),
            source="unit-test",
        )
    )
    app.dependency_overrides[get_horse_service] = lambda: object()

    try:
        response = client.patch(
            "/api/horses/11111111-1111-4111-8111-111111111111",
            json={"kind": "horse"},
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_protected_equestrian_context, None)
        app.dependency_overrides.pop(get_horse_service, None)

    assert response.status_code == 422
    assert "body -> kind" in response.json()["detail"]
