from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from core.entities.base import PaginatedEntities
from core.entities.equestrian import EquestrianContext
from core.entities.user import UserScope
from core.schemas.horse_service_relations import (
    HorseServiceAvailableOutDto,
    HorseServiceRelationOutDto,
)
from core.schemas.users import UserOutDto
from core.services.horse_service_relations import HorseServiceRelationsService
from depends.services import (
    get_current_user,
    get_horse_service_relations_service,
    get_protected_equestrian_context,
    get_read_equestrian_context,
)
from main import app

TENANT_ID = UUID("11111111-1111-4111-8111-111111111111")
HORSE_ID = UUID("22222222-2222-4222-8222-222222222222")
RELATION_ID = UUID("33333333-3333-4333-8333-333333333333")
SERVICE_ID = UUID("44444444-4444-4444-8444-444444444444")
CONTEXT = EquestrianContext(id=TENANT_ID, source="unit")


def _user(*, scope: str | None) -> UserOutDto:
    scopes = (
        [UserScope(scope_name=scope, scope_description=f"{scope} scope")]
        if scope
        else []
    )
    return UserOutDto(
        id=uuid4(),
        equestrian_id=TENANT_ID,
        username=scope or "no-scope",
        created_at=datetime.now(timezone.utc),
        scopes=scopes,
    )


def _dto() -> HorseServiceRelationOutDto:
    return HorseServiceRelationOutDto(
        id=RELATION_ID,
        created_at=datetime.now(timezone.utc),
        service_id=SERVICE_ID,
        name="Подковка",
        slug="podkovka",
        price=1000,
        price_formatter="equal",
    )


def _clear_overrides() -> None:
    for dependency in (
        get_current_user,
        get_horse_service_relations_service,
        get_protected_equestrian_context,
        get_read_equestrian_context,
    ):
        app.dependency_overrides.pop(dependency, None)


def test_relation_get_returns_paginated_contract_and_forwards_limit_offset() -> None:
    service = AsyncMock()
    service.get_list_by_horse.return_value = PaginatedEntities(items=[_dto()], total=3)
    app.dependency_overrides[get_horse_service_relations_service] = lambda: service
    app.dependency_overrides[get_read_equestrian_context] = lambda: CONTEXT
    try:
        response = TestClient(app).get(
            f"/api/horses/{HORSE_ID}/services?limit=1&offset=2"
        )
    finally:
        _clear_overrides()

    assert response.status_code == 200
    assert response.json()["total"] == 3
    assert len(response.json()["items"]) == 1
    service.get_list_by_horse.assert_awaited_once_with(
        HORSE_ID, equestrian_context=CONTEXT, limit=1, offset=2
    )


def test_available_services_anonymous_returns_401() -> None:
    service = AsyncMock()
    app.dependency_overrides[get_horse_service_relations_service] = lambda: service
    try:
        response = TestClient(app).get(f"/api/horses/{HORSE_ID}/available-services")
    finally:
        _clear_overrides()

    assert response.status_code == 401
    service.get_available_services.assert_not_awaited()


def test_available_services_no_scope_returns_403_before_repositories() -> None:
    relations_repository = AsyncMock()
    service = HorseServiceRelationsService(
        relations_repository=relations_repository,
        horse_repository=AsyncMock(),
        horse_service_repository=AsyncMock(),
    )
    app.dependency_overrides[get_current_user] = lambda: _user(scope=None)
    app.dependency_overrides[get_protected_equestrian_context] = lambda: CONTEXT
    app.dependency_overrides[get_horse_service_relations_service] = lambda: service
    try:
        response = TestClient(app).get(f"/api/horses/{HORSE_ID}/available-services")
    finally:
        _clear_overrides()

    assert response.status_code == 403
    assert relations_repository.mock_calls == []


def test_available_services_allowed_returns_complete_inheritance_fields() -> None:
    service = AsyncMock()
    available = HorseServiceAvailableOutDto(
        id=SERVICE_ID,
        name="Подковка",
        slug="podkovka",
        description="Полное описание",
        price=2500,
        price_formatter="gt",
    )
    service.get_available_services.return_value = [available]
    user = _user(scope="ADMIN")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_protected_equestrian_context] = lambda: CONTEXT
    app.dependency_overrides[get_horse_service_relations_service] = lambda: service
    try:
        response = TestClient(app).get(
            f"/api/horses/{HORSE_ID}/available-services?search=под"
        )
    finally:
        _clear_overrides()

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": str(SERVICE_ID),
            "name": "Подковка",
            "slug": "podkovka",
            "description": "Полное описание",
            "price": 2500,
            "price_formatter": "gt",
        }
    ]
    service.get_available_services.assert_awaited_once_with(
        HORSE_ID, equestrian_context=CONTEXT, user=user, search="под"
    )


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("post", f"/api/horses/{HORSE_ID}/services", {"service_id": str(SERVICE_ID)}),
        (
            "patch",
            f"/api/horses/{HORSE_ID}/services/{RELATION_ID}",
            {"price_override": 2000},
        ),
        ("delete", f"/api/horses/{HORSE_ID}/services/{RELATION_ID}", None),
    ],
)
def test_relation_writes_anonymous_return_401_without_mutation(
    method: str, path: str, body: dict | None
) -> None:
    service = AsyncMock()
    app.dependency_overrides[get_horse_service_relations_service] = lambda: service
    try:
        response = TestClient(app).request(method, path, json=body)
    finally:
        _clear_overrides()

    assert response.status_code == 401
    service.create.assert_not_awaited()
    service.update.assert_not_awaited()
    service.delete.assert_not_awaited()


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("post", f"/api/horses/{HORSE_ID}/services", {"service_id": str(SERVICE_ID)}),
        (
            "patch",
            f"/api/horses/{HORSE_ID}/services/{RELATION_ID}",
            {"price_override": 2000},
        ),
        ("delete", f"/api/horses/{HORSE_ID}/services/{RELATION_ID}", None),
    ],
)
def test_relation_writes_no_scope_return_403_before_repositories(
    method: str, path: str, body: dict | None
) -> None:
    relations_repository = AsyncMock()
    service = HorseServiceRelationsService(
        relations_repository=relations_repository,
        horse_repository=AsyncMock(),
        horse_service_repository=AsyncMock(),
    )
    app.dependency_overrides[get_current_user] = lambda: _user(scope=None)
    app.dependency_overrides[get_protected_equestrian_context] = lambda: CONTEXT
    app.dependency_overrides[get_horse_service_relations_service] = lambda: service
    try:
        response = TestClient(app).request(method, path, json=body)
    finally:
        _clear_overrides()

    assert response.status_code == 403
    assert relations_repository.mock_calls == []


@pytest.mark.parametrize(
    ("method", "path", "body", "expected_status", "service_method"),
    [
        (
            "post",
            f"/api/horses/{HORSE_ID}/services",
            {"service_id": str(SERVICE_ID)},
            201,
            "create",
        ),
        (
            "patch",
            f"/api/horses/{HORSE_ID}/services/{RELATION_ID}",
            {"price_override": 2000},
            200,
            "update",
        ),
        (
            "delete",
            f"/api/horses/{HORSE_ID}/services/{RELATION_ID}",
            None,
            204,
            "delete",
        ),
    ],
)
def test_relation_writes_allowed_scope_reach_service(
    method: str,
    path: str,
    body: dict | None,
    expected_status: int,
    service_method: str,
) -> None:
    service = AsyncMock()
    service.create.return_value = _dto()
    service.update.return_value = _dto()
    app.dependency_overrides[get_current_user] = lambda: _user(scope="ADMIN")
    app.dependency_overrides[get_protected_equestrian_context] = lambda: CONTEXT
    app.dependency_overrides[get_horse_service_relations_service] = lambda: service
    try:
        response = TestClient(app).request(method, path, json=body)
    finally:
        _clear_overrides()

    assert response.status_code == expected_status
    getattr(service, service_method).assert_awaited_once()
