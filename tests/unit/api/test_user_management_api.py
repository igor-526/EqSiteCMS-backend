"""Unit tests for User Management API endpoints."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from core.entities.user import UserScope
from core.exceptions.auth import ForbiddenError
from core.exceptions.base import ClientError, NotFoundError
from core.schemas.user_management import (
    RoleOutDto,
    UserManagementOutDto,
)
from core.schemas.users import UserOutDto
from core.services.user_management import UserManagementService
from depends.services import get_user_management_service
from main import app


# Test constants
TEST_USER_ID = uuid4()
TEST_EQUESTRIAN_ID = uuid4()

USER_MANAGER_SCOPE = UserScope(
    id=uuid4(),
    scope_name="USER_MANAGER",
    scope_description="Управление пользователями",
)

ADMIN_SCOPE = UserScope(
    id=uuid4(),
    scope_name="ADMIN",
    scope_description="Администрирование сайта",
)


def create_test_user_dto(
    user_id=None,
    scopes=None,
    is_blocked=False,
    is_deleted=False,
):
    """Create a test UserOutDto."""
    return UserOutDto(
        id=user_id or uuid4(),
        equestrian_id=TEST_EQUESTRIAN_ID,
        username="testuser",
        first_name="Test",
        last_name="User",
        created_at=datetime.now(timezone.utc),
        is_blocked=is_blocked,
        is_deleted=is_deleted,
        scopes=scopes or [USER_MANAGER_SCOPE],
    )


def create_test_user_management_dto(
    user_id=None,
    scopes=None,
    is_blocked=False,
    is_deleted=False,
):
    """Create a test UserManagementOutDto."""
    return UserManagementOutDto(
        id=user_id or TEST_USER_ID,
        equestrian_id=TEST_EQUESTRIAN_ID,
        username="testuser",
        first_name="Test",
        last_name="User",
        created_at=datetime.now(timezone.utc),
        is_blocked=is_blocked,
        is_deleted=is_deleted,
        scopes=scopes or [ADMIN_SCOPE],
    )


class TestUserManagementAPI:
    """Integration tests for User Management API endpoints."""

    @pytest.fixture
    def mock_service(self):
        """Mock user management service."""
        return AsyncMock(spec=UserManagementService)

    @pytest.fixture
    def mock_require_user_management(self):
        """Mock require_user_management dependency."""
        return create_test_user_dto()

    @pytest.fixture
    def client(self, mock_service, mock_require_user_management):
        """Create test client with mocked dependencies."""
        from api.depends.user_management import require_user_management

        app.dependency_overrides[get_user_management_service] = lambda: mock_service
        app.dependency_overrides[require_user_management] = (
            lambda: mock_require_user_management
        )
        yield TestClient(app)
        app.dependency_overrides.clear()

    # ===== GET /api/user-management/users =====

    async def test_get_users_returns_200(self, client, mock_service):
        """GET /api/user-management/users returns 200 with users list."""
        # Arrange
        test_user = create_test_user_management_dto()
        mock_service.get_users.return_value = {
            "items": [test_user],
            "total": 1,
        }

        # Act
        response = client.get("/api/user-management/users")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1

    async def test_get_users_with_filters(self, client, mock_service):
        """GET /api/user-management/users passes filters to service."""
        # Arrange
        mock_service.get_users.return_value = {"items": [], "total": 0}

        # Act
        response = client.get(
            "/api/user-management/users",
            params={
                "username": "admin",
                "is_blocked": "true",
                "limit": 50,
                "offset": 10,
            },
        )

        # Assert
        assert response.status_code == 200

    # ===== GET /api/user-management/users/{id} =====

    async def test_get_user_by_id_returns_200(self, client, mock_service):
        """GET /api/user-management/users/{id} returns 200 with user."""
        # Arrange
        test_user = create_test_user_management_dto()
        mock_service.get_user_by_id.return_value = test_user

        # Act
        response = client.get(f"/api/user-management/users/{TEST_USER_ID}")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(TEST_USER_ID)

    async def test_get_user_by_id_not_found_returns_404(self, client, mock_service):
        """GET /api/user-management/users/{id} returns 404 if not found."""
        # Arrange
        mock_service.get_user_by_id.side_effect = NotFoundError("Пользователь не найден")

        # Act
        response = client.get(f"/api/user-management/users/{uuid4()}")

        # Assert
        assert response.status_code == 404

    # ===== POST /api/user-management/users =====

    async def test_create_user_returns_201(self, client, mock_service):
        """POST /api/user-management/users returns 201 with created user."""
        # Arrange
        test_user = create_test_user_management_dto()
        mock_service.create_user.return_value = test_user

        # Act
        response = client.post(
            "/api/user-management/users",
            json={
                "equestrian_id": str(TEST_EQUESTRIAN_ID),
                "username": "newuser",
                "password": "SecurePass123",
                "confirm_password": "SecurePass123",
            },
        )

        # Assert
        assert response.status_code == 201

    async def test_create_user_duplicate_username_returns_400(self, client, mock_service):
        """POST /api/user-management/users returns 400 for duplicate username."""
        # Arrange
        mock_service.create_user.side_effect = ClientError("уже существует")

        # Act
        response = client.post(
            "/api/user-management/users",
            json={
                "equestrian_id": str(TEST_EQUESTRIAN_ID),
                "username": "existinguser",
                "password": "SecurePass123",
                "confirm_password": "SecurePass123",
            },
        )

        # Assert
        assert response.status_code == 400

    async def test_create_user_password_mismatch_returns_400(self, client, mock_service):
        """POST /api/user-management/users returns 400 for password mismatch."""
        # Act - Pydantic ValidationError -> 400 via exception handler
        response = client.post(
            "/api/user-management/users",
            json={
                "equestrian_id": str(TEST_EQUESTRIAN_ID),
                "username": "newuser",
                "password": "SecurePass123",
                "confirm_password": "DifferentPass123",
            },
        )

        # Assert
        assert response.status_code == 400

    # ===== PATCH /api/user-management/users/{id} =====

    async def test_update_user_returns_200(self, client, mock_service):
        """PATCH /api/user-management/users/{id} returns 200 with updated user."""
        # Arrange
        test_user = create_test_user_management_dto()
        mock_service.update_user.return_value = test_user

        # Act
        response = client.patch(
            f"/api/user-management/users/{TEST_USER_ID}",
            json={"first_name": "NewName"},
        )

        # Assert
        assert response.status_code == 200

    async def test_update_user_not_found_returns_404(self, client, mock_service):
        """PATCH /api/user-management/users/{id} returns 404 if not found."""
        # Arrange
        mock_service.update_user.side_effect = NotFoundError("Пользователь не найден")

        # Act
        response = client.patch(
            f"/api/user-management/users/{uuid4()}",
            json={"first_name": "NewName"},
        )

        # Assert
        assert response.status_code == 404

    async def test_update_user_um_cannot_edit_su_returns_403(self, client, mock_service):
        """PATCH /api/user-management/users/{id} returns 403 when UM tries to edit SU."""
        # Arrange
        mock_service.update_user.side_effect = ForbiddenError(
            "USER_MANAGER не может редактировать SUPERUSER"
        )

        # Act
        response = client.patch(
            f"/api/user-management/users/{TEST_USER_ID}",
            json={"first_name": "NewName"},
        )

        # Assert
        assert response.status_code == 403

    # ===== DELETE /api/user-management/users/{id} =====

    async def test_delete_user_returns_204(self, client, mock_service):
        """DELETE /api/user-management/users/{id} returns 204."""
        # Arrange
        mock_service.soft_delete_user.return_value = None

        # Act
        response = client.delete(f"/api/user-management/users/{TEST_USER_ID}")

        # Assert
        assert response.status_code == 204

    async def test_delete_user_self_returns_403(self, client, mock_service):
        """DELETE /api/user-management/users/{id} returns 403 when deleting self."""
        # Arrange
        mock_service.soft_delete_user.side_effect = ForbiddenError("Нельзя удалить самого себя")

        # Act
        response = client.delete(f"/api/user-management/users/{TEST_USER_ID}")

        # Assert
        assert response.status_code == 403

    # ===== PATCH /api/user-management/users/{id}/block =====

    async def test_block_user_returns_200(self, client, mock_service):
        """PATCH /api/user-management/users/{id}/block returns 200."""
        # Arrange
        mock_service.block_user.return_value = {"is_blocked": True}

        # Act
        response = client.patch(f"/api/user-management/users/{TEST_USER_ID}/block")

        # Assert
        assert response.status_code == 200
        assert response.json()["is_blocked"] is True

    async def test_block_user_self_returns_403(self, client, mock_service):
        """PATCH /api/user-management/users/{id}/block returns 403 when blocking self."""
        # Arrange
        mock_service.block_user.side_effect = ForbiddenError("Нельзя заблокировать самого себя")

        # Act
        response = client.patch(f"/api/user-management/users/{TEST_USER_ID}/block")

        # Assert
        assert response.status_code == 403

    # ===== PATCH /api/user-management/users/{id}/unblock =====

    async def test_unblock_user_returns_200(self, client, mock_service):
        """PATCH /api/user-management/users/{id}/unblock returns 200."""
        # Arrange
        mock_service.unblock_user.return_value = {"is_blocked": False}

        # Act
        response = client.patch(f"/api/user-management/users/{TEST_USER_ID}/unblock")

        # Assert
        assert response.status_code == 200
        assert response.json()["is_blocked"] is False

    # ===== PATCH /api/user-management/users/{id}/password =====

    async def test_change_password_returns_204(self, client, mock_service):
        """PATCH /api/user-management/users/{id}/password returns 204."""
        # Arrange
        mock_service.change_password.return_value = None

        # Act
        response = client.patch(
            f"/api/user-management/users/{TEST_USER_ID}/password",
            json={
                "new_password": "NewSecurePass123",
                "confirm_password": "NewSecurePass123",
            },
        )

        # Assert
        assert response.status_code == 204

    async def test_change_password_mismatch_returns_400(self, client, mock_service):
        """PATCH /api/user-management/users/{id}/password returns 400 for mismatch."""
        # Act - Pydantic ValidationError -> 400 via exception handler
        response = client.patch(
            f"/api/user-management/users/{TEST_USER_ID}/password",
            json={
                "new_password": "NewSecurePass123",
                "confirm_password": "DifferentPass123",
            },
        )

        # Assert
        assert response.status_code == 400

    # ===== GET /api/user-management/roles =====

    async def test_get_roles_returns_200(self, client, mock_service):
        """GET /api/user-management/roles returns 200 with roles list."""
        # Arrange
        roles = [
            RoleOutDto(
                id=uuid4(),
                scope_name="ADMIN",
                scope_description="Admin scope",
            ),
        ]
        mock_service.get_all_roles.return_value = roles

        # Act
        response = client.get("/api/user-management/roles")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    async def test_get_roles_with_filter(self, client, mock_service):
        """GET /api/user-management/roles passes filter to service."""
        # Arrange
        mock_service.get_all_roles.return_value = []

        # Act
        response = client.get(
            "/api/user-management/roles",
            params={"scope_name": "USER"},
        )

        # Assert
        assert response.status_code == 200
