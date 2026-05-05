from typing import Protocol
from uuid import UUID

from core.entities.user import User, UserScope, UserScopeRelation

from .base_repository import BaseRepositoryProtocol


class UserRepositoryProtocol(BaseRepositoryProtocol[User], Protocol):
    async def get_by_username(self, username: str) -> User | None: ...
    async def get_user_scopes(self, user_id: UUID) -> list[UserScope]: ...


class UserScopeRepositoryProtocol(BaseRepositoryProtocol[UserScope], Protocol): ...


class UserScopeRelationRepositoryProtocol(
    BaseRepositoryProtocol[UserScopeRelation], Protocol
):
    async def set_user_scopes(
        self, user_id: UUID, scope_ids: list[UserScope]
    ) -> list[UserScope]: ...

    """Устанавливает области доступа для пользователя"""
