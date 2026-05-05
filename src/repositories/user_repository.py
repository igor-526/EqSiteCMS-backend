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
