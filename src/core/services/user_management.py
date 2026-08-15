from uuid import UUID

from core.entities.user import User
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
    UserManagementOutDto,
    RoleOutDto,
)
from core.schemas.users import UserOutDto


USER_MANAGER_SCOPE = "USER_MANAGER"
SUPERUSER_SCOPE = "SUPERUSER"


class UserManagementService:
    """Сервис для управления пользователями."""

    def __init__(
        self,
        repository: UserManagementRepositoryProtocol,
        security: SecurityProtocol,
    ) -> None:
        self.repository = repository
        self.security = security

    async def get_users(
        self,
        current_user: UserOutDto,
        filters: UserManagementFilters,
        limit: int = 100,
        offset: int = 0,
    ) -> dict:
        """Получить список пользователей с фильтрацией."""
        users, total = await self.repository.get_users_with_filters(
            username=filters.username,
            first_name=filters.first_name,
            last_name=filters.last_name,
            middle_name=filters.middle_name,
            scope_ids=filters.scope_ids,
            search=filters.search,
            is_blocked=filters.is_blocked,
            limit=limit,
            offset=offset,
        )

        # Получаем роли для каждого пользователя
        user_dtos = []
        for user in users:
            scopes = await self.repository.get_user_scopes(user.id)
            user_dto = UserManagementOutDto(
                id=user.id,
                equestrian_id=user.equestrian_id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                middle_name=user.middle_name,
                created_at=user.created_at,
                updated_at=user.updated_at,
                is_deleted=user.is_deleted,
                deleted_at=user.deleted_at,
                is_blocked=user.is_blocked,
                scopes=scopes,
            )
            user_dtos.append(user_dto)

        return {"items": user_dtos, "total": total}

    async def get_user_by_id(
        self,
        current_user: UserOutDto,
        user_id: UUID,
    ) -> UserManagementOutDto:
        """Получить пользователя по ID."""
        user = await self.repository.get_user_by_id(user_id)
        if user is None:
            raise NotFoundError("Пользователь не найден")

        scopes = await self.repository.get_user_scopes(user.id)
        return UserManagementOutDto(
            id=user.id,
            equestrian_id=user.equestrian_id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            middle_name=user.middle_name,
            created_at=user.created_at,
            updated_at=user.updated_at,
            is_deleted=user.is_deleted,
            deleted_at=user.deleted_at,
            is_blocked=user.is_blocked,
            scopes=scopes,
        )

    async def create_user(
        self,
        current_user: UserOutDto,
        data: CreateUserIn,
    ) -> UserManagementOutDto:
        """Создать нового пользователя."""
        current_scopes = [s.scope_name for s in current_user.scopes]
        is_um = USER_MANAGER_SCOPE in current_scopes

        # UM не может назначать SUPERUSER
        if is_um and data.scope_ids:
            target_scopes = await self._get_scope_names(data.scope_ids)
            if SUPERUSER_SCOPE in target_scopes:
                raise ForbiddenError("USER_MANAGER не может назначать роль SUPERUSER")

        # Проверяем уникальность username
        existing_user = await self.repository.get_by_username(data.username)
        if existing_user:
            raise ClientError(
                f"Пользователь с username '{data.username}' уже существует"
            )

        # Хешируем пароль
        hashed_password = self.security.hash_password(data.password)

        # Создаём пользователя
        user = User(
            equestrian_id=data.equestrian_id,
            username=data.username,
            password=hashed_password,
            first_name=data.first_name,
            last_name=data.last_name,
            middle_name=data.middle_name,
        )

        created_user = await self.repository.create_user(user, data.scope_ids)

        # Получаем роли
        scopes = await self.repository.get_user_scopes(created_user.id)

        return UserManagementOutDto(
            id=created_user.id,
            equestrian_id=created_user.equestrian_id,
            username=created_user.username,
            first_name=created_user.first_name,
            last_name=created_user.last_name,
            middle_name=created_user.middle_name,
            created_at=created_user.created_at,
            updated_at=created_user.updated_at,
            is_deleted=created_user.is_deleted,
            deleted_at=created_user.deleted_at,
            is_blocked=created_user.is_blocked,
            scopes=scopes,
        )

    async def update_user(
        self,
        current_user: UserOutDto,
        user_id: UUID,
        data: UpdateUserIn,
    ) -> UserManagementOutDto:
        """Обновить пользователя."""
        current_scopes = [s.scope_name for s in current_user.scopes]
        is_um = USER_MANAGER_SCOPE in current_scopes
        is_su = SUPERUSER_SCOPE in current_scopes

        # Получаем целевого пользователя
        target_user = await self.repository.get_user_by_id(user_id)
        if target_user is None:
            raise NotFoundError("Пользователь не найден")

        target_scopes = [
            s.scope_name for s in await self.repository.get_user_scopes(user_id)
        ]

        # UM не может действовать с SUPERUSER
        if is_um and not is_su and SUPERUSER_SCOPE in target_scopes:
            raise ForbiddenError("USER_MANAGER не может редактировать SUPERUSER")

        # UM не может снять с себя роль UM
        if is_um and user_id == current_user.id and data.scope_ids is not None:
            new_scope_names = await self._get_scope_names(data.scope_ids)
            if USER_MANAGER_SCOPE not in new_scope_names:
                raise ForbiddenError("Нельзя снять с себя роль USER_MANAGER")

        # SU не может снять с себя роль SU
        if is_su and user_id == current_user.id and data.scope_ids is not None:
            new_scope_names = await self._get_scope_names(data.scope_ids)
            if SUPERUSER_SCOPE not in new_scope_names:
                raise ForbiddenError("Нельзя снять с себя роль SUPERUSER")

        # UM не может назначать SUPERUSER
        if is_um and data.scope_ids is not None:
            new_scope_names = await self._get_scope_names(data.scope_ids)
            if SUPERUSER_SCOPE in new_scope_names:
                raise ForbiddenError("USER_MANAGER не может назначать роль SUPERUSER")

        # Проверяем уникальность username при изменении
        if data.username is not None and data.username != target_user.username:
            existing = await self.repository.get_by_username(data.username)
            if existing and existing.id != user_id:
                raise ClientError(
                    f"Пользователь с username '{data.username}' уже существует"
                )

        # Обновляем поля
        if data.username is not None:
            target_user.username = data.username
        if data.first_name is not None:
            target_user.first_name = data.first_name
        if data.last_name is not None:
            target_user.last_name = data.last_name
        if data.middle_name is not None:
            target_user.middle_name = data.middle_name

        updated_user = await self.repository.update_user(target_user, data.scope_ids)

        # Получаем обновлённые роли
        scopes = await self.repository.get_user_scopes(updated_user.id)

        return UserManagementOutDto(
            id=updated_user.id,
            equestrian_id=updated_user.equestrian_id,
            username=updated_user.username,
            first_name=updated_user.first_name,
            last_name=updated_user.last_name,
            middle_name=updated_user.middle_name,
            created_at=updated_user.created_at,
            updated_at=updated_user.updated_at,
            is_deleted=updated_user.is_deleted,
            deleted_at=updated_user.deleted_at,
            is_blocked=updated_user.is_blocked,
            scopes=scopes,
        )

    async def soft_delete_user(
        self,
        current_user: UserOutDto,
        user_id: UUID,
    ) -> None:
        """Удалить пользователя (soft-delete)."""
        current_scopes = [s.scope_name for s in current_user.scopes]
        is_um = USER_MANAGER_SCOPE in current_scopes
        is_su = SUPERUSER_SCOPE in current_scopes

        # Нельзя удалить самого себя
        if user_id == current_user.id:
            raise ForbiddenError("Нельзя удалить самого себя")

        # Получаем целевого пользователя
        target_user = await self.repository.get_user_by_id(user_id)
        if target_user is None:
            raise NotFoundError("Пользователь не найден")

        target_scopes = [
            s.scope_name for s in await self.repository.get_user_scopes(user_id)
        ]

        # UM не может удалить SUPERUSER
        if is_um and not is_su and SUPERUSER_SCOPE in target_scopes:
            raise ForbiddenError("USER_MANAGER не может удалить SUPERUSER")

        success = await self.repository.soft_delete_user(user_id)
        if not success:
            raise ClientError("Не удалось удалить пользователя")

    async def block_user(
        self,
        current_user: UserOutDto,
        user_id: UUID,
    ) -> dict:
        """Заблокировать пользователя."""
        current_scopes = [s.scope_name for s in current_user.scopes]
        is_um = USER_MANAGER_SCOPE in current_scopes
        is_su = SUPERUSER_SCOPE in current_scopes

        # Нельзя заблокировать самого себя
        if user_id == current_user.id:
            raise ForbiddenError("Нельзя заблокировать самого себя")

        # Получаем целевого пользователя
        target_user = await self.repository.get_user_by_id(user_id)
        if target_user is None:
            raise NotFoundError("Пользователь не найден")

        target_scopes = [
            s.scope_name for s in await self.repository.get_user_scopes(user_id)
        ]

        # UM не может заблокировать SUPERUSER
        if is_um and not is_su and SUPERUSER_SCOPE in target_scopes:
            raise ForbiddenError("USER_MANAGER не может заблокировать SUPERUSER")

        success = await self.repository.block_user(user_id)
        if not success:
            raise ClientError("Не удалось заблокировать пользователя")

        return {"is_blocked": True}

    async def unblock_user(
        self,
        current_user: UserOutDto,
        user_id: UUID,
    ) -> dict:
        """Разблокировать пользователя."""
        current_scopes = [s.scope_name for s in current_user.scopes]
        is_um = USER_MANAGER_SCOPE in current_scopes
        is_su = SUPERUSER_SCOPE in current_scopes

        # Получаем целевого пользователя
        target_user = await self.repository.get_user_by_id(user_id)
        if target_user is None:
            raise NotFoundError("Пользователь не найден")

        target_scopes = [
            s.scope_name for s in await self.repository.get_user_scopes(user_id)
        ]

        # UM не может разблокировать SUPERUSER
        if is_um and not is_su and SUPERUSER_SCOPE in target_scopes:
            raise ForbiddenError("USER_MANAGER не может разблокировать SUPERUSER")

        success = await self.repository.unblock_user(user_id)
        if not success:
            raise ClientError("Не удалось разблокировать пользователя")

        return {"is_blocked": False}

    async def change_password(
        self,
        current_user: UserOutDto,
        user_id: UUID,
        data: ChangePasswordByAdminIn,
    ) -> None:
        """Сменить пароль пользователя (администратором)."""
        current_scopes = [s.scope_name for s in current_user.scopes]
        is_um = USER_MANAGER_SCOPE in current_scopes
        is_su = SUPERUSER_SCOPE in current_scopes

        # Получаем целевого пользователя
        target_user = await self.repository.get_user_by_id(user_id)
        if target_user is None:
            raise NotFoundError("Пользователь не найден")

        target_scopes = [
            s.scope_name for s in await self.repository.get_user_scopes(user_id)
        ]

        # UM не может менять пароль SUPERUSER
        if is_um and not is_su and SUPERUSER_SCOPE in target_scopes:
            raise ForbiddenError("USER_MANAGER не может менять пароль SUPERUSER")

        # Хешируем новый пароль
        hashed_password = self.security.hash_password(data.new_password)

        success = await self.repository.change_password(user_id, hashed_password)
        if not success:
            raise ClientError("Не удалось изменить пароль")

    async def get_all_roles(
        self,
        current_user: UserOutDto,
        scope_name: str | None = None,
    ) -> list[RoleOutDto]:
        """Получить все роли."""
        roles = await self.repository.get_all_roles(scope_name=scope_name)
        return [
            RoleOutDto(
                id=role.id,
                scope_name=role.scope_name,
                scope_description=role.scope_description,
            )
            for role in roles
        ]

    async def _get_scope_names(self, scope_ids: list[UUID]) -> list[str]:
        """Получить имена ролей по их ID."""
        # Получаем все роли
        all_roles = await self.repository.get_all_roles()
        role_map = {role.id: role.scope_name for role in all_roles}

        return [role_map[sid] for sid in scope_ids if sid in role_map]
