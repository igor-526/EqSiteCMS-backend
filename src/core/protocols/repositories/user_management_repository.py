from typing import Protocol
from uuid import UUID

from core.entities.user import User, UserScope

from .base_repository import BaseRepositoryProtocol


class UserManagementRepositoryProtocol(BaseRepositoryProtocol[User], Protocol):
    """Протокол репозитория для управления пользователями."""

    async def get_users_with_filters(
        self,
        *,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        middle_name: str | None = None,
        scope_ids: list[UUID] | None = None,
        search: str | None = None,
        is_blocked: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[User], int]:
        """Получить пользователей с фильтрацией, пагинацией и сортировкой."""
        ...

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        """Получить пользователя по ID (исключая удалённых)."""
        ...

    async def create_user(
        self,
        user: User,
        scope_ids: list[UUID] | None = None,
    ) -> User:
        """Создать пользователя с указанными ролями."""
        ...

    async def update_user(
        self,
        user: User,
        scope_ids: list[UUID] | None = None,
    ) -> User:
        """Обновить пользователя и его роли."""
        ...

    async def soft_delete_user(self, user_id: UUID) -> bool:
        """Пометить пользователя как удалённого (soft-delete)."""
        ...

    async def block_user(self, user_id: UUID) -> bool:
        """Заблокировать пользователя."""
        ...

    async def unblock_user(self, user_id: UUID) -> bool:
        """Разблокировать пользователя."""
        ...

    async def change_password(self, user_id: UUID, hashed_password: str) -> bool:
        """Изменить пароль пользователя."""
        ...

    async def get_user_scopes(self, user_id: UUID) -> list[UserScope]:
        """Получить роли пользователя."""
        ...

    async def get_all_roles(
        self,
        *,
        scope_name: str | None = None,
    ) -> list[UserScope]:
        """Получить все роли с фильтрацией по scope_name (regex)."""
        ...
