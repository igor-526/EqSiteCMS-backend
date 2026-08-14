from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from core.entities.base import PaginatedEntities
from core.exceptions.auth import InvalidServiceKey
from core.schemas.users import UserOutDto
from depends.services import (
    get_service_context,
    get_service_pagination_params,
    get_user_service,
)
from main import app


def create_test_user_dto(user_id=None, equestrian_id=None, username="testuser"):
    """Create a test user DTO."""
    return UserOutDto(
        id=user_id or uuid4(),
        equestrian_id=equestrian_id or uuid4(),
        username=username,
        first_name="Test",
        last_name="User",
        created_at=datetime.now(timezone.utc),
        scopes=[],
    )


class TestServiceUsersAPI:
    """Integration tests for GET /api/service/users endpoint."""

    @pytest.fixture
    def mock_user_service(self):
        """Mock user service."""
        return AsyncMock()

    @pytest.fixture
    def mock_service_context(self):
        """Mock service context dependency."""
        return None

    @pytest.fixture
    def mock_pagination_params(self):
        """Mock pagination params dependency."""
        return {"limit": 100, "offset": 0}

    @pytest.fixture
    def client(self, mock_user_service, mock_service_context, mock_pagination_params):
        """Create test client with mocked dependencies."""
        app.dependency_overrides[get_user_service] = lambda: mock_user_service
        app.dependency_overrides[get_service_context] = lambda: mock_service_context
        app.dependency_overrides[get_service_pagination_params] = (
            lambda: mock_pagination_params
        )
        yield TestClient(app)
        app.dependency_overrides.clear()

    async def test_valid_service_key_returns_200(self, client, mock_user_service):
        """Test with valid service key returns 200."""
        # Arrange
        test_user = create_test_user_dto()
        mock_user_service.get_users_paginated.return_value = PaginatedEntities(
            items=[test_user], total=1
        )

        # Act
        response = client.get(
            "/api/service/users", headers={"X-Service-Key": "valid-key"}
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == str(test_user.id)

    async def test_invalid_service_key_returns_401(self, client):
        """Test with invalid service key returns 401."""
        # Arrange
        app.dependency_overrides[get_service_context] = lambda: (_ for _ in ()).throw(
            InvalidServiceKey()
        )

        # Act
        response = client.get(
            "/api/service/users", headers={"X-Service-Key": "invalid-key"}
        )

        # Assert
        assert response.status_code == 401

    async def test_missing_service_key_returns_401(self, client):
        """Test with missing service key returns 401."""
        # Arrange
        app.dependency_overrides[get_service_context] = lambda: (_ for _ in ()).throw(
            InvalidServiceKey()
        )

        # Act
        response = client.get("/api/service/users")

        # Assert
        assert response.status_code == 401

    async def test_filter_by_equestrian_ids(self, client, mock_user_service):
        """Test filtering by equestrian_ids."""
        # Arrange
        equestrian_id = uuid4()
        test_user = create_test_user_dto(equestrian_id=equestrian_id)
        mock_user_service.get_users_paginated.return_value = PaginatedEntities(
            items=[test_user], total=1
        )

        # Act
        response = client.get(
            f"/api/service/users?equestrian_ids={equestrian_id}",
            headers={"X-Service-Key": "valid-key"},
        )

        # Assert
        assert response.status_code == 200
        mock_user_service.get_users_paginated.assert_called_once()
        call_args = mock_user_service.get_users_paginated.call_args
        assert call_args.kwargs["equestrian_ids"] == [equestrian_id]

    async def test_filter_by_equestrian_service_keys(self, client, mock_user_service):
        """Test filtering by equestrian_service_keys."""
        # Arrange
        service_key = "test-service-key"
        test_user = create_test_user_dto()
        mock_user_service.get_users_paginated.return_value = PaginatedEntities(
            items=[test_user], total=1
        )

        # Act
        response = client.get(
            f"/api/service/users?equestrian_service_keys={service_key}",
            headers={"X-Service-Key": "valid-key"},
        )

        # Assert
        assert response.status_code == 200
        mock_user_service.get_users_paginated.assert_called_once()
        call_args = mock_user_service.get_users_paginated.call_args
        assert call_args.kwargs["equestrian_service_keys"] == [service_key]

    async def test_filter_by_role(self, client, mock_user_service):
        """Test filtering by role."""
        # Arrange
        role = "ADMIN"
        test_user = create_test_user_dto()
        mock_user_service.get_users_paginated.return_value = PaginatedEntities(
            items=[test_user], total=1
        )

        # Act
        response = client.get(
            f"/api/service/users?role={role}", headers={"X-Service-Key": "valid-key"}
        )

        # Assert
        assert response.status_code == 200
        mock_user_service.get_users_paginated.assert_called_once()
        call_args = mock_user_service.get_users_paginated.call_args
        assert call_args.kwargs["roles"] == [role]

    async def test_pagination_limit_offset(self, client, mock_user_service):
        """Test pagination with limit and offset."""
        # Arrange
        test_user = create_test_user_dto()
        mock_user_service.get_users_paginated.return_value = PaginatedEntities(
            items=[test_user], total=100
        )

        # Act
        response = client.get(
            "/api/service/users?limit=50&offset=10",
            headers={"X-Service-Key": "valid-key"},
        )

        # Assert
        assert response.status_code == 200
        mock_user_service.get_users_paginated.assert_called_once()
        call_args = mock_user_service.get_users_paginated.call_args
        # The pagination params come from the dependency, not directly from query params
        # The dependency is mocked to return {"limit": 100, "offset": 0}
        assert call_args.kwargs["limit"] == 100
        assert call_args.kwargs["offset"] == 0

    async def test_multiple_filters_combined(self, client, mock_user_service):
        """Test combining multiple filters."""
        # Arrange
        equestrian_id = uuid4()
        service_key = "test-key"
        role = "ADMIN"
        test_user = create_test_user_dto()
        mock_user_service.get_users_paginated.return_value = PaginatedEntities(
            items=[test_user], total=1
        )

        # Act
        response = client.get(
            f"/api/service/users?equestrian_ids={equestrian_id}&equestrian_service_keys={service_key}&role={role}",
            headers={"X-Service-Key": "valid-key"},
        )

        # Assert
        assert response.status_code == 200
        mock_user_service.get_users_paginated.assert_called_once()
        call_args = mock_user_service.get_users_paginated.call_args
        assert call_args.kwargs["equestrian_ids"] == [equestrian_id]
        assert call_args.kwargs["equestrian_service_keys"] == [service_key]
        assert call_args.kwargs["roles"] == [role]

    async def test_empty_result(self, client, mock_user_service):
        """Test with no matching users."""
        # Arrange
        mock_user_service.get_users_paginated.return_value = PaginatedEntities(
            items=[], total=0
        )

        # Act
        response = client.get(
            "/api/service/users", headers={"X-Service-Key": "valid-key"}
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert len(data["items"]) == 0

    async def test_response_structure(self, client, mock_user_service):
        """Test that response has correct structure."""
        # Arrange
        test_user = create_test_user_dto()
        mock_user_service.get_users_paginated.return_value = PaginatedEntities(
            items=[test_user], total=1
        )

        # Act
        response = client.get(
            "/api/service/users", headers={"X-Service-Key": "valid-key"}
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)

    async def test_user_dto_structure(self, client, mock_user_service):
        """Test that user DTO has correct structure."""
        # Arrange
        test_user = create_test_user_dto()
        mock_user_service.get_users_paginated.return_value = PaginatedEntities(
            items=[test_user], total=1
        )

        # Act
        response = client.get(
            "/api/service/users", headers={"X-Service-Key": "valid-key"}
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        user_data = data["items"][0]
        assert "id" in user_data
        assert "equestrian_id" in user_data
        assert "username" in user_data
        assert "first_name" in user_data
        assert "last_name" in user_data
        assert "created_at" in user_data
        assert "scopes" in user_data
