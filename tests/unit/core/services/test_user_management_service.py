"""Unit tests for UserManagementService business rules."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from core.entities.user import User, UserScope
from core.exceptions.base import ClientError, NotFoundError
from core.protocols.security import SecurityProtocol
from core.schemas.user_management import (
    ChangePasswordByAdminIn,
    CreateUserIn,
    UpdateUserIn,
    UserManagementFilters,
)
from core.schemas.users import UserOutDto
from core.services.user_management import UserManagementService

# Test constants
TEST_USER_ID = uuid4()
TEST_SUPERUSER_ID = uuid4()
TEST_UM_ID = uuid4()
TEST_EQUESTRIAN_ID = uuid4()

SUPERUSER_SCOPE = UserScope(
    id=uuid4(),
    scope_name="SUPERUSER",
    scope_description="Все права",
)

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


def create_user_dto(
    user_id: UUID | None = None,
    scopes: list[UserScope] | None = None,
    is_blocked: bool = False,
    is_deleted: bool = False,
) -> UserOutDto:
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
        scopes=scopes or [],
    )


def create_user_entity(
    user_id: UUID | None = None,
    is_blocked: bool = False,
    is_deleted: bool = False,
) -> User:
    """Create a test User entity."""
    return User(
        id=user_id or uuid4(),
        equestrian_id=TEST_EQUESTRIAN_ID,
        username="testuser",
        password="$2b$12$hashed_password",
        first_name="Test",
        last_name="User",
        is_blocked=is_blocked,
        is_deleted=is_deleted,
    )


class TestUserManagementService:
    """Tests for UserManagementService."""

    @pytest.fixture
    def mock_repository(self):
        """Mock repository."""
        return AsyncMock()

    @pytest.fixture
    def mock_security(self):
        """Mock security protocol."""
        security = AsyncMock(spec=SecurityProtocol)
        security.hash_password.return_value = "$2b$12$hashed_password"
        security.verify_password.return_value = True
        return security

    @pytest.fixture
    def service(self, mock_repository, mock_security):
        """Create service instance."""
        return UserManagementService(
            repository=mock_repository,
            security=mock_security,
        )

    # ===== Business Rule Tests =====

    async def test_um_cannot_delete_self(self, service, mock_repository):
        """UM не может удалить самого себя."""
        # Arrange
        um_user = create_user_dto(
            user_id=TEST_UM_ID,
            scopes=[USER_MANAGER_SCOPE],
        )

        # Act & Assert
        with pytest.raises(ClientError, match="Нельзя удалить самого себя"):
            await service.soft_delete_user(um_user, TEST_UM_ID)

    async def test_um_cannot_block_self(self, service, mock_repository):
        """UM не может заблокировать самого себя."""
        # Arrange
        um_user = create_user_dto(
            user_id=TEST_UM_ID,
            scopes=[USER_MANAGER_SCOPE],
        )

        # Act & Assert
        with pytest.raises(ClientError, match="Нельзя заблокировать самого себя"):
            await service.block_user(um_user, TEST_UM_ID)

    async def test_um_cannot_delete_superuser(self, service, mock_repository):
        """UM не может удалить SUPERUSER."""
        # Arrange
        um_user = create_user_dto(
            user_id=TEST_UM_ID,
            scopes=[USER_MANAGER_SCOPE],
        )
        su_user = create_user_entity(user_id=TEST_SUPERUSER_ID)

        mock_repository.get_user_by_id.return_value = su_user
        mock_repository.get_user_scopes.return_value = [SUPERUSER_SCOPE]

        # Act & Assert
        with pytest.raises(
            ClientError, match="USER_MANAGER не может удалить SUPERUSER"
        ):
            await service.soft_delete_user(um_user, TEST_SUPERUSER_ID)

    async def test_um_cannot_block_superuser(self, service, mock_repository):
        """UM не может заблокировать SUPERUSER."""
        # Arrange
        um_user = create_user_dto(
            user_id=TEST_UM_ID,
            scopes=[USER_MANAGER_SCOPE],
        )
        su_user = create_user_entity(user_id=TEST_SUPERUSER_ID)

        mock_repository.get_user_by_id.return_value = su_user
        mock_repository.get_user_scopes.return_value = [SUPERUSER_SCOPE]

        # Act & Assert
        with pytest.raises(
            ClientError, match="USER_MANAGER не может заблокировать SUPERUSER"
        ):
            await service.block_user(um_user, TEST_SUPERUSER_ID)

    async def test_um_cannot_remove_own_um_role(self, service, mock_repository):
        """UM не может снять с себя роль UM."""
        # Arrange
        um_user = create_user_dto(
            user_id=TEST_UM_ID,
            scopes=[USER_MANAGER_SCOPE],
        )
        target_user = create_user_entity(user_id=TEST_UM_ID)

        mock_repository.get_user_by_id.return_value = target_user
        mock_repository.get_user_scopes.return_value = [USER_MANAGER_SCOPE]
        mock_repository.get_all_roles.return_value = [USER_MANAGER_SCOPE, ADMIN_SCOPE]

        data = UpdateUserIn(scope_ids=[ADMIN_SCOPE.id])  # Без USER_MANAGER

        # Act & Assert
        with pytest.raises(ClientError, match="Нельзя снять с себя роль USER_MANAGER"):
            await service.update_user(um_user, TEST_UM_ID, data)

    async def test_su_cannot_remove_own_su_role(self, service, mock_repository):
        """SU не может снять с себя роль SU."""
        # Arrange
        su_user = create_user_dto(
            user_id=TEST_SUPERUSER_ID,
            scopes=[SUPERUSER_SCOPE],
        )
        target_user = create_user_entity(user_id=TEST_SUPERUSER_ID)

        mock_repository.get_user_by_id.return_value = target_user
        mock_repository.get_user_scopes.return_value = [SUPERUSER_SCOPE]
        mock_repository.get_all_roles.return_value = [SUPERUSER_SCOPE, ADMIN_SCOPE]

        data = UpdateUserIn(scope_ids=[ADMIN_SCOPE.id])  # Без SUPERUSER

        # Act & Assert
        with pytest.raises(ClientError, match="Нельзя снять с себя роль SUPERUSER"):
            await service.update_user(su_user, TEST_SUPERUSER_ID, data)

    async def test_um_cannot_assign_superuser(self, service, mock_repository):
        """UM не может назначить SUPERUSER."""
        # Arrange
        um_user = create_user_dto(
            user_id=TEST_UM_ID,
            scopes=[USER_MANAGER_SCOPE],
        )
        target_user = create_user_entity(user_id=TEST_USER_ID)

        mock_repository.get_user_by_id.return_value = target_user
        mock_repository.get_user_scopes.return_value = [ADMIN_SCOPE]
        mock_repository.get_all_roles.return_value = [
            SUPERUSER_SCOPE,
            USER_MANAGER_SCOPE,
            ADMIN_SCOPE,
        ]

        data = UpdateUserIn(scope_ids=[SUPERUSER_SCOPE.id])

        # Act & Assert
        with pytest.raises(
            ClientError, match="USER_MANAGER не может назначать роль SUPERUSER"
        ):
            await service.update_user(um_user, TEST_USER_ID, data)

    async def test_um_cannot_act_on_superuser(self, service, mock_repository):
        """UM не может редактировать SUPERUSER."""
        # Arrange
        um_user = create_user_dto(
            user_id=TEST_UM_ID,
            scopes=[USER_MANAGER_SCOPE],
        )
        su_user = create_user_entity(user_id=TEST_SUPERUSER_ID)

        mock_repository.get_user_by_id.return_value = su_user
        mock_repository.get_user_scopes.return_value = [SUPERUSER_SCOPE]

        data = UpdateUserIn(first_name="New Name")

        # Act & Assert
        with pytest.raises(
            ClientError, match="USER_MANAGER не может редактировать SUPERUSER"
        ):
            await service.update_user(um_user, TEST_SUPERUSER_ID, data)

    async def test_su_can_delete_other_user(self, service, mock_repository):
        """SU может удалить другого пользователя."""
        # Arrange
        su_user = create_user_dto(
            user_id=TEST_SUPERUSER_ID,
            scopes=[SUPERUSER_SCOPE],
        )
        target_user = create_user_entity(user_id=TEST_USER_ID)

        mock_repository.get_user_by_id.return_value = target_user
        mock_repository.get_user_scopes.return_value = [ADMIN_SCOPE]
        mock_repository.soft_delete_user.return_value = True

        # Act
        await service.soft_delete_user(su_user, TEST_USER_ID)

        # Assert
        mock_repository.soft_delete_user.assert_called_once_with(TEST_USER_ID)

    async def test_um_cannot_change_superuser_password(self, service, mock_repository):
        """UM не может менять пароль SUPERUSER."""
        # Arrange
        um_user = create_user_dto(
            user_id=TEST_UM_ID,
            scopes=[USER_MANAGER_SCOPE],
        )
        su_user = create_user_entity(user_id=TEST_SUPERUSER_ID)

        mock_repository.get_user_by_id.return_value = su_user
        mock_repository.get_user_scopes.return_value = [SUPERUSER_SCOPE]

        data = ChangePasswordByAdminIn(
            new_password="NewPass123",
            confirm_password="NewPass123",
        )

        # Act & Assert
        with pytest.raises(
            ClientError, match="USER_MANAGER не может менять пароль SUPERUSER"
        ):
            await service.change_password(um_user, TEST_SUPERUSER_ID, data)

    async def test_get_users_excludes_deleted(self, service, mock_repository):
        """Удалённые пользователи исключаются из списка."""
        # Arrange
        um_user = create_user_dto(
            user_id=TEST_UM_ID,
            scopes=[USER_MANAGER_SCOPE],
        )
        mock_repository.get_users_with_filters.return_value = ([], 0)
        mock_repository.get_user_scopes.return_value = []

        filters = UserManagementFilters()

        # Act
        result = await service.get_users(um_user, filters)

        # Assert
        assert result["total"] == 0
        assert result["items"] == []

    async def test_create_user_hashes_password(
        self, service, mock_repository, mock_security
    ):
        """Пароль хешируется при создании пользователя."""
        # Arrange
        um_user = create_user_dto(
            user_id=TEST_UM_ID,
            scopes=[USER_MANAGER_SCOPE],
        )

        mock_repository.get_by_username.return_value = None
        mock_repository.get_all_roles.return_value = [ADMIN_SCOPE]
        created_user = create_user_entity()
        mock_repository.create_user.return_value = created_user
        mock_repository.get_user_scopes.return_value = [ADMIN_SCOPE]

        data = CreateUserIn(
            equestrian_id=TEST_EQUESTRIAN_ID,
            username="newuser",
            password="SecurePass123",
            confirm_password="SecurePass123",
            scope_ids=[ADMIN_SCOPE.id],
        )

        # Act
        await service.create_user(um_user, data)

        # Assert
        mock_security.hash_password.assert_called_once_with("SecurePass123")

    async def test_create_user_duplicate_username_raises_error(
        self, service, mock_repository
    ):
        """Создание пользователя с существующим username вызывает ошибку."""
        # Arrange
        um_user = create_user_dto(
            user_id=TEST_UM_ID,
            scopes=[USER_MANAGER_SCOPE],
        )

        existing_user = create_user_entity()
        mock_repository.get_by_username.return_value = existing_user

        data = CreateUserIn(
            equestrian_id=TEST_EQUESTRIAN_ID,
            username="existinguser",
            password="SecurePass123",
            confirm_password="SecurePass123",
        )

        # Act & Assert
        with pytest.raises(ClientError, match="уже существует"):
            await service.create_user(um_user, data)

    async def test_user_not_found_raises_error(self, service, mock_repository):
        """Получение несуществующего пользователя вызывает ошибку."""
        # Arrange
        um_user = create_user_dto(
            user_id=TEST_UM_ID,
            scopes=[USER_MANAGER_SCOPE],
        )
        mock_repository.get_user_by_id.return_value = None

        # Act & Assert
        with pytest.raises(NotFoundError, match="Пользователь не найден"):
            await service.get_user_by_id(um_user, uuid4())
