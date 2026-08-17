from typing import Protocol
from uuid import UUID

from core.entities.user import User, UserScope, UserScopeRelation

from .base_repository import BaseRepositoryProtocol


class UserRepositoryProtocol(BaseRepositoryProtocol[User], Protocol):
    async def get_by_username(self, username: str) -> User | None: ...

    async def get_user_scopes(self, user_id: UUID) -> list[UserScope]: ...

    async def get_users_paginated(
        self,
        *,
        equestrian_ids: list[UUID] | None = None,
        equestrian_service_keys: list[str] | None = None,
        roles: list[str] | None = None,
        exclude_deleted: bool = False,
        exclude_blocked: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[User], int]: ...


class UserScopeRepositoryProtocol(BaseRepositoryProtocol[UserScope], Protocol):
    pass


class UserScopeRelationRepositoryProtocol(
    BaseRepositoryProtocol[UserScopeRelation], Protocol
):
    async def set_user_scopes(
        self, user_id: UUID, scope_ids: list[UserScope]
    ) -> list[UserScope]: ...
