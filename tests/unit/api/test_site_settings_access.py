from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from core.entities.equestrian import EquestrianContext
from core.schemas import UserOutDto
from depends.services import (
    get_current_user,
    get_protected_equestrian_context,
    get_site_settings_service,
)
from main import app


def test_authenticated_no_scope_site_setting_write_returns_403_without_mutation() -> (
    None
):
    tenant_id = UUID("11111111-1111-4111-8111-111111111111")
    current_user = UserOutDto(
        id=uuid4(),
        equestrian_id=tenant_id,
        username="no-scope",
        created_at=datetime.now(timezone.utc),
        scopes=[],
    )
    service = AsyncMock()
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_protected_equestrian_context] = lambda: (
        EquestrianContext(id=tenant_id, source="unit")
    )
    app.dependency_overrides[get_site_settings_service] = lambda: service
    client = TestClient(app)
    try:
        response = client.post(
            "/api/site_settings",
            json={
                "key": "scope_denied",
                "value": "qa",
                "name": "Scope denied",
                "type": "string",
            },
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_protected_equestrian_context, None)
        app.dependency_overrides.pop(get_site_settings_service, None)

    assert response.status_code == 403
    service.create.assert_not_awaited()
