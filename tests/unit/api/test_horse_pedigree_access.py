from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from core.entities import UserScope
from core.entities.equestrian import EquestrianContext
from core.schemas import UserOutDto
from depends.services import (
    get_current_user,
    get_horse_service,
    get_protected_equestrian_context,
)
from main import app


HORSE_ID = UUID("11111111-1111-4111-8111-111111111111")
TENANT_ID = UUID("22222222-2222-4222-8222-222222222222")


def make_user(scope_name: str) -> UserOutDto:
    return UserOutDto(
        id=uuid4(),
        equestrian_id=TENANT_ID,
        username=scope_name.lower(),
        created_at=datetime.now(timezone.utc),
        scopes=[UserScope(scope_name=scope_name, scope_description=scope_name)],
    )


def test_anonymous_pedigree_post_returns_401_before_service() -> None:
    service = AsyncMock()
    app.dependency_overrides[get_horse_service] = lambda: service
    client = TestClient(app)
    try:
        response = client.post(
            f"/api/horses/{HORSE_ID}/pedigree", json={"sire_id": None}
        )
    finally:
        app.dependency_overrides.pop(get_horse_service, None)

    assert response.status_code == 401
    service.set_horse_pedigree.assert_not_awaited()


@pytest.mark.parametrize("scope_name", ["SUPERUSER", "ADMIN", "DEVELOPER"])
def test_allowed_scope_reaches_pedigree_service(scope_name: str) -> None:
    service = AsyncMock()
    service.set_horse_pedigree.return_value = None
    app.dependency_overrides[get_horse_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: make_user(scope_name)
    app.dependency_overrides[get_protected_equestrian_context] = lambda: (
        EquestrianContext(id=TENANT_ID, source="authenticated")
    )
    client = TestClient(app)
    try:
        response = client.post(
            f"/api/horses/{HORSE_ID}/pedigree", json={"sire_id": None}
        )
    finally:
        app.dependency_overrides.pop(get_horse_service, None)
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_protected_equestrian_context, None)

    assert response.status_code == 204
    service.set_horse_pedigree.assert_awaited_once()
