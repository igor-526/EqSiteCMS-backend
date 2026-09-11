"""Unit tests for UserManagementService business rules."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from core.entities.user import User, UserScope
from core.exceptions.auth import ForbiddenError
from core.exceptions.base import ClientError, NotFoundError
from core.protocols.repositories.user_management_repository import (
    UserManagementRepositoryProtocol,
)
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
FOREIGN_EQUESTRIAN_ID = uuid4()

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
    equestrian_id: UUID = TEST_EQUESTRIAN_ID,
) -> UserOutDto:
    """Create a test UserOutDto."""
    return UserOutDto(
        id=user_id or uuid4(),
        equestrian_id=equestrian_id,
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
    equestrian_id: UUID = TEST_EQUESTRIAN_ID,
    username: str = "testuser",
) -> User:
    """Create a test User entity."""
    return User(
        id=user_id or uuid4(),
        equestrian_id=equestrian_id,
        username=username,
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
        return AsyncMock(spec=UserManagementRepositoryProtocol)

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
        mock_repository.soft_delete_user.assert_called_once_with(
            TEST_USER_ID, equestrian_id=TEST_EQUESTRIAN_ID
        )

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
        mock_repository.get_users_with_filters.assert_awaited_once_with(
            equestrian_id=TEST_EQUESTRIAN_ID,
            username=None,
            first_name=None,
            last_name=None,
            middle_name=None,
            scope_ids=None,
            search=None,
            is_blocked=None,
            limit=100,
            offset=0,
        )

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

    async def test_get_users_returns_only_repository_tenant_response(
        self, service, mock_repository
    ):
        own_user = create_user_entity(username="own")
        mock_repository.get_users_with_filters.return_value = ([own_user], 1)
        mock_repository.get_user_scopes.return_value = [ADMIN_SCOPE]

        result = await service.get_users(
            create_user_dto(scopes=[USER_MANAGER_SCOPE]), UserManagementFilters()
        )

        assert result["total"] == 1
        assert [item.username for item in result["items"]] == ["own"]
        assert all(item.equestrian_id == TEST_EQUESTRIAN_ID for item in result["items"])

    async def test_get_own_tenant_user_passes_trusted_tenant(
        self, service, mock_repository
    ):
        target = create_user_entity(user_id=TEST_USER_ID)
        mock_repository.get_user_by_id.return_value = target
        mock_repository.get_user_scopes.return_value = [ADMIN_SCOPE]

        result = await service.get_user_by_id(
            create_user_dto(scopes=[SUPERUSER_SCOPE]), TEST_USER_ID
        )

        assert result.id == TEST_USER_ID
        mock_repository.get_user_by_id.assert_awaited_once_with(
            TEST_USER_ID, equestrian_id=TEST_EQUESTRIAN_ID
        )

    async def test_foreign_lookup_is_indistinguishable_from_missing(
        self, service, mock_repository
    ):
        mock_repository.get_user_by_id.return_value = None

        with pytest.raises(NotFoundError, match="Пользователь не найден"):
            await service.get_user_by_id(
                create_user_dto(scopes=[SUPERUSER_SCOPE]), TEST_USER_ID
            )

        mock_repository.get_user_scopes.assert_not_awaited()

    async def test_create_user_uses_trusted_tenant(self, service, mock_repository):
        created_user = create_user_entity(username="newuser")
        mock_repository.get_by_username.return_value = None
        mock_repository.create_user.return_value = created_user
        mock_repository.get_user_scopes.return_value = []
        data = CreateUserIn(
            equestrian_id=TEST_EQUESTRIAN_ID,
            username="newuser",
            password="SecurePass123",
            confirm_password="SecurePass123",
        )

        result = await service.create_user(
            create_user_dto(scopes=[SUPERUSER_SCOPE]), data
        )

        assert result.equestrian_id == TEST_EQUESTRIAN_ID
        mock_repository.get_by_username.assert_awaited_once_with(
            "newuser", equestrian_id=TEST_EQUESTRIAN_ID
        )
        assert mock_repository.create_user.await_args.kwargs["equestrian_id"] == (
            TEST_EQUESTRIAN_ID
        )

    async def test_cross_tenant_create_rejected_before_side_effects(
        self, service, mock_repository, mock_security
    ):
        data = CreateUserIn(
            equestrian_id=FOREIGN_EQUESTRIAN_ID,
            username="foreign",
            password="SecurePass123",
            confirm_password="SecurePass123",
        )

        with pytest.raises(ForbiddenError, match="другой конюшне"):
            await service.create_user(create_user_dto(scopes=[SUPERUSER_SCOPE]), data)

        mock_repository.get_by_username.assert_not_awaited()
        mock_repository.create_user.assert_not_awaited()
        mock_security.hash_password.assert_not_called()

    @pytest.mark.parametrize(
        ("method_name", "data", "side_effects"),
        [
            ("update_user", UpdateUserIn(first_name="Leaked"), ("update_user",)),
            ("soft_delete_user", None, ("soft_delete_user",)),
            ("block_user", None, ("block_user",)),
            ("unblock_user", None, ("unblock_user",)),
            (
                "change_password",
                ChangePasswordByAdminIn(
                    new_password="NewPass123", confirm_password="NewPass123"
                ),
                ("change_password",),
            ),
        ],
    )
    async def test_foreign_mutations_return_404_without_side_effects(
        self, service, mock_repository, mock_security, method_name, data, side_effects
    ):
        current_user = create_user_dto(scopes=[SUPERUSER_SCOPE])
        mock_repository.get_user_by_id.return_value = None

        args = (
            (current_user, TEST_USER_ID)
            if data is None
            else (current_user, TEST_USER_ID, data)
        )
        with pytest.raises(NotFoundError, match="Пользователь не найден"):
            await getattr(service, method_name)(*args)

        mock_repository.get_user_by_id.assert_awaited_once_with(
            TEST_USER_ID, equestrian_id=TEST_EQUESTRIAN_ID
        )
        mock_repository.get_user_scopes.assert_not_awaited()
        for side_effect in side_effects:
            getattr(mock_repository, side_effect).assert_not_awaited()
        if method_name == "change_password":
            mock_security.hash_password.assert_not_called()
