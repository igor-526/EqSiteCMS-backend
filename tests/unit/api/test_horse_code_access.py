from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from core.entities.equestrian import EquestrianContext
from core.schemas import UserOutDto
from core.services.horse import HorseService
from depends.services import (
    get_current_user,
    get_horse_service,
    get_protected_equestrian_context,
)
from main import app


def test_anonymous_horse_code_writes_return_401_before_service_mutation() -> None:
    service = AsyncMock()
    app.dependency_overrides[get_horse_service] = lambda: service
    client = TestClient(app)
    try:
        post = client.post("/api/horses", json={"name": "Буран", "code": "X"})
        patch = client.patch(
            "/api/horses/11111111-1111-4111-8111-111111111111",
            json={"code": "X"},
        )
    finally:
        app.dependency_overrides.pop(get_horse_service, None)

    assert post.status_code == patch.status_code == 401
    service.create_horse.assert_not_awaited()
    service.update_horse.assert_not_awaited()


def test_authenticated_no_scope_horse_code_write_returns_403_without_mutation() -> None:
    tenant_id = UUID("11111111-1111-4111-8111-111111111111")
    current_user = UserOutDto(
        id=uuid4(),
        equestrian_id=tenant_id,
        username="no-scope",
        created_at=datetime.now(timezone.utc),
        scopes=[],
    )
    repository = AsyncMock()
    service = HorseService(
        horse_repository=repository,
        horse_children_repository=AsyncMock(),
        breed_repository=AsyncMock(),
        coat_color_repository=AsyncMock(),
        horse_owner_repository=AsyncMock(),
    )
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_protected_equestrian_context] = lambda: (
        EquestrianContext(id=tenant_id, source="unit")
    )
    app.dependency_overrides[get_horse_service] = lambda: service
    client = TestClient(app)
    try:
        response = client.post("/api/horses", json={"name": "Буран", "code": "X"})
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_protected_equestrian_context, None)
        app.dependency_overrides.pop(get_horse_service, None)

    assert response.status_code == 403
    repository.create.assert_not_awaited()
    repository.update.assert_not_awaited()
