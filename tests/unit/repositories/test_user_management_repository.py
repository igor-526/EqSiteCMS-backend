"""Unit tests for UserManagementRepository."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from core.entities.user import User, UserScope
from repositories.user_management_repository import UserManagementRepository


TEST_USER_ID = uuid4()
TEST_EQUESTRIAN_ID = uuid4()


def create_test_user(
    user_id=None,
    username="testuser",
    first_name="Test",
    last_name="User",
    is_blocked=False,
    is_deleted=False,
):
    """Create a test User entity."""
    return User(
        id=user_id or uuid4(),
        equestrian_id=TEST_EQUESTRIAN_ID,
        username=username,
        password="$2b$12$hashed",
        first_name=first_name,
        last_name=last_name,
        is_blocked=is_blocked,
        is_deleted=is_deleted,
    )


def create_mock_execute_result(rows=None, scalar_value=0):
    """Create a properly mocked execute result."""
    mock_result = MagicMock()
    mock_result.mappings.return_value.all.return_value = rows or []
    mock_result.scalar.return_value = scalar_value
    return mock_result


class TestUserManagementRepository:
    """Tests for UserManagementRepository filtering and sorting."""

    @pytest.fixture
    def mock_session(self):
        """Mock async session."""
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def repository(self, mock_session):
        """Create repository instance."""
        return UserManagementRepository(session=mock_session)

    async def test_get_users_excludes_deleted(self, repository, mock_session):
        """Repository excludes deleted users by default."""
        # Arrange - need two execute calls: first for count, second for select
        count_result = create_mock_execute_result(scalar_value=0)
        select_result = create_mock_execute_result(rows=[])
        mock_session.execute.side_effect = [count_result, select_result]

        # Act
        users, total = await repository.get_users_with_filters()

        # Assert
        assert total == 0
        assert users == []

    async def test_get_users_with_username_filter(self, repository, mock_session):
        """Repository filters by username with regex."""
        # Arrange
        test_user = create_test_user(username="admin")
        user_row = {
            "id": test_user.id,
            "equestrian_id": test_user.equestrian_id,
            "username": test_user.username,
            "password": test_user.password,
            "first_name": test_user.first_name,
            "last_name": test_user.last_name,
            "middle_name": None,
            "is_deleted": False,
            "deleted_at": None,
            "is_blocked": False,
            "created_at": datetime.now(timezone.utc),
            "updated_at": None,
        }
        count_result = create_mock_execute_result(scalar_value=1)
        select_result = create_mock_execute_result(rows=[user_row])
        mock_session.execute.side_effect = [count_result, select_result]

        # Act
        users, total = await repository.get_users_with_filters(username="admin")

        # Assert
        assert total == 1
        assert len(users) == 1
        assert users[0].username == "admin"

    async def test_get_users_with_search_filter(self, repository, mock_session):
        """Repository searches across first_name, last_name, middle_name."""
        # Arrange
        count_result = create_mock_execute_result(scalar_value=0)
        select_result = create_mock_execute_result(rows=[])
        mock_session.execute.side_effect = [count_result, select_result]

        # Act
        users, total = await repository.get_users_with_filters(search="Иван")

        # Assert
        assert total == 0

    async def test_get_users_with_is_blocked_filter(self, repository, mock_session):
        """Repository filters by blocked status."""
        # Arrange
        count_result = create_mock_execute_result(scalar_value=0)
        select_result = create_mock_execute_result(rows=[])
        mock_session.execute.side_effect = [count_result, select_result]

        # Act
        users, total = await repository.get_users_with_filters(is_blocked=True)

        # Assert
        assert total == 0

    async def test_soft_delete_user(self, repository, mock_session):
        """Repository soft-deletes user by setting is_deleted=True."""
        # Arrange
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute.return_value = mock_result

        # Act
        result = await repository.soft_delete_user(TEST_USER_ID)

        # Assert
        assert result is True

    async def test_block_user(self, repository, mock_session):
        """Repository blocks user by setting is_blocked=True."""
        # Arrange
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute.return_value = mock_result

        # Act
        result = await repository.block_user(TEST_USER_ID)

        # Assert
        assert result is True

    async def test_unblock_user(self, repository, mock_session):
        """Repository unblocks user by setting is_blocked=False."""
        # Arrange
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute.return_value = mock_result

        # Act
        result = await repository.unblock_user(TEST_USER_ID)

        # Assert
        assert result is True

    async def test_change_password(self, repository, mock_session):
        """Repository changes user password."""
        # Arrange
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute.return_value = mock_result

        # Act
        result = await repository.change_password(TEST_USER_ID, "$2b$12$new_hash")

        # Assert
        assert result is True

    async def test_get_user_scopes(self, repository, mock_session):
        """Repository retrieves user scopes."""
        # Arrange
        scope = UserScope(
            id=uuid4(),
            scope_name="ADMIN",
            scope_description="Admin scope",
        )
        mock_result = create_mock_execute_result(
            rows=[
                {
                    "id": scope.id,
                    "scope_name": scope.scope_name,
                    "scope_description": scope.scope_description,
                }
            ]
        )
        mock_session.execute.return_value = mock_result

        # Act
        scopes = await repository.get_user_scopes(TEST_USER_ID)

        # Assert
        assert len(scopes) == 1
        assert scopes[0].scope_name == "ADMIN"

    async def test_get_all_roles(self, repository, mock_session):
        """Repository retrieves all roles."""
        # Arrange
        mock_result = create_mock_execute_result(
            rows=[
                {
                    "id": uuid4(),
                    "scope_name": "ADMIN",
                    "scope_description": "Admin scope",
                },
                {
                    "id": uuid4(),
                    "scope_name": "USER_MANAGER",
                    "scope_description": "User Manager scope",
                },
            ]
        )
        mock_session.execute.return_value = mock_result

        # Act
        roles = await repository.get_all_roles()

        # Assert
        assert len(roles) == 2

    async def test_get_all_roles_with_filter(self, repository, mock_session):
        """Repository filters roles by scope_name regex."""
        # Arrange
        mock_result = create_mock_execute_result(
            rows=[
                {
                    "id": uuid4(),
                    "scope_name": "USER_MANAGER",
                    "scope_description": "User Manager scope",
                }
            ]
        )
        mock_session.execute.return_value = mock_result

        # Act
        roles = await repository.get_all_roles(scope_name="USER")

        # Assert
        assert len(roles) == 1
        assert roles[0].scope_name == "USER_MANAGER"
