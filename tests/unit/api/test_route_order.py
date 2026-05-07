from __future__ import annotations

from fastapi.routing import APIRoute

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
