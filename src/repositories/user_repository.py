from uuid import UUID

from sqlalchemy import Table, select

from core.entities.user import User, UserScope
from models.users import user_scopes, user_scopes_relations, users

from .abstract_repository import AbstractRepository


class UserRepository(AbstractRepository[User]):
    table: Table = users
    entity = User

    async def get_by_username(self, username: str) -> User | None:
        stmt = select(self.table).where(self.table.c.username == username)
        row = await self.session.execute(stmt)
        mapping = row.mappings().first()
        if mapping is None:
            return None
        return self.entity.model_validate(dict(mapping))

    async def get_user_scopes(self, user_id: UUID) -> list[UserScope]:
        """Получить группы доступа пользователя"""
        stmt = (
            select(user_scopes)
            .join(
                user_scopes_relations,
                user_scopes.c.id == user_scopes_relations.c.scope_id,
            )
            .where(user_scopes_relations.c.user_id == user_id)
        )
        rows = await self.session.execute(stmt)
        return [UserScope.model_validate(dict(row)) for row in rows.mappings().all()]

    async def get_users_paginated(
        self,
        *,
        equestrian_ids: list[UUID] | None = None,
        equestrian_service_keys: list[str] | None = None,
        roles: list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
        exclude_deleted: bool = False,
        exclude_blocked: bool = False,
    ) -> tuple[list[User], int]:
        """Get paginated users with filtering."""
        from sqlalchemy import and_, func

        from models.equestrian import equestrians

        # Base query
        query = select(self.table)
        count_query = select(func.count()).select_from(self.table)

        # Apply filters
        conditions = []

        # Exclude deleted users if requested
        if exclude_deleted:
            conditions.append(self.table.c.is_deleted.is_(False))

        # Exclude blocked users if requested
        if exclude_blocked:
            conditions.append(self.table.c.is_blocked.is_(False))

        # Filter by equestrian_ids (OR within filter)
        if equestrian_ids:
            conditions.append(self.table.c.equestrian_id.in_(equestrian_ids))

        # Filter by equestrian_service_keys (OR within filter)
        if equestrian_service_keys:
            query = query.join(
                equestrians, self.table.c.equestrian_id == equestrians.c.id
            )
            count_query = count_query.join(
                equestrians, self.table.c.equestrian_id == equestrians.c.id
            )
            conditions.append(equestrians.c.service_key.in_(equestrian_service_keys))

        # Filter by roles (OR within filter)
        if roles:
            # Subquery to get user_ids with matching roles
            role_subquery = (
                select(user_scopes_relations.c.user_id)
                .join(user_scopes, user_scopes.c.id == user_scopes_relations.c.scope_id)
                .where(user_scopes.c.scope_name.in_(roles))
                .distinct()
            )
            conditions.append(self.table.c.id.in_(role_subquery))

        # Apply all conditions with AND logic
        if conditions:
            query = query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))

        # Get total count
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination
        query = query.limit(limit).offset(offset)

        # Execute query
        result = await self.session.execute(query)
        users = [
            self.entity.model_validate(dict(row)) for row in result.mappings().all()
        ]

        return users, total
