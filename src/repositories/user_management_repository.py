from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import Table, and_, func, or_, select

from core.entities.user import User, UserScope
from models.users import user_scopes, user_scopes_relations, users

from .abstract_repository import AbstractRepository


class UserManagementRepository(AbstractRepository[User]):
    """Репозиторий для управления пользователями."""

    table: Table = users
    entity = User

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

        # Базовые условия: исключаем удалённых
        conditions = [self.table.c.is_deleted.is_(False)]

        # Фильтр по username (регистронезависимый regex)
        if username:
            conditions.append(
                func.lower(self.table.c.username).op("~")(f"(?i).*{username}.*")
            )

        # Фильтр по first_name (регистронезависимый regex)
        if first_name:
            conditions.append(
                func.lower(self.table.c.first_name).op("~")(f"(?i).*{first_name}.*")
            )

        # Фильтр по last_name (регистронезависимый regex)
        if last_name:
            conditions.append(
                func.lower(self.table.c.last_name).op("~")(f"(?i).*{last_name}.*")
            )

        # Фильтр по middle_name (регистронезависимый regex)
        if middle_name:
            conditions.append(
                func.lower(self.table.c.middle_name).op("~")(f"(?i).*{middle_name}.*")
            )

        # Фильтр по scope_ids (логика ИЛИ)
        if scope_ids:
            # Получаем user_id с одной из указанных ролей
            scope_subquery = (
                select(user_scopes_relations.c.user_id)
                .where(user_scopes_relations.c.scope_id.in_(scope_ids))
                .distinct()
            )
            conditions.append(self.table.c.id.in_(scope_subquery))

        # Поиск по ФИО (логика ИЛИ для first_name, last_name, middle_name)
        if search:
            search_pattern = f"(?i).*{search}.*"
            search_conditions = [
                func.lower(self.table.c.first_name).op("~")(search_pattern),
                func.lower(self.table.c.last_name).op("~")(search_pattern),
                func.lower(self.table.c.middle_name).op("~")(search_pattern),
            ]
            conditions.append(or_(*search_conditions))

        # Фильтр по блокировке
        if is_blocked is not None:
            conditions.append(self.table.c.is_blocked == is_blocked)

        # Строим запрос
        query = select(self.table)
        count_query = select(func.count()).select_from(self.table)

        # Применяем условия
        if conditions:
            query = query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))

        # Сортировка: is_blocked ASC, затем last_name ASC
        query = query.order_by(
            self.table.c.is_blocked.asc(),
            self.table.c.last_name.asc().nullslast(),
            self.table.c.id.asc(),
        )

        # Получаем общее количество
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        # Применяем пагинацию
        query = query.limit(limit).offset(offset)

        # Выполняем запрос
        result = await self.session.execute(query)
        user_list = [
            self.entity.model_validate(dict(row)) for row in result.mappings().all()
        ]

        return user_list, total

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        """Получить пользователя по ID (исключая удалённых)."""
        stmt = select(self.table).where(
            and_(
                self.table.c.id == user_id,
                self.table.c.is_deleted.is_(False),
            )
        )
        row = await self.session.execute(stmt)
        mapping = row.mappings().first()
        if mapping is None:
            return None
        return self.entity.model_validate(dict(mapping))

    async def create_user(
        self,
        user: User,
        scope_ids: list[UUID] | None = None,
    ) -> User:
        """Создать пользователя с указанными ролями."""
        # Создаём пользователя
        created_user = await self.create(user)

        # Добавляем роли
        if scope_ids:
            await self._set_user_scopes(created_user.id, scope_ids)

        return created_user

    async def update_user(
        self,
        user: User,
        scope_ids: list[UUID] | None = None,
    ) -> User:
        """Обновить пользователя и его роли."""
        # Обновляем пользователя
        updated_user = await self.update(user)

        # Обновляем роли, если переданы
        if scope_ids is not None:
            await self._set_user_scopes(updated_user.id, scope_ids)

        return updated_user

    async def soft_delete_user(self, user_id: UUID) -> bool:
        """Пометить пользователя как удалённого (soft-delete)."""
        now = datetime.now(timezone.utc)
        stmt = (
            self.table.update()
            .where(
                and_(
                    self.table.c.id == user_id,
                    self.table.c.is_deleted.is_(False),
                )
            )
            .values(
                is_deleted=True,
                deleted_at=now,
                updated_at=now,
            )
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount > 0

    async def block_user(self, user_id: UUID) -> bool:
        """Заблокировать пользователя."""
        now = datetime.now(timezone.utc)
        stmt = (
            self.table.update()
            .where(
                and_(
                    self.table.c.id == user_id,
                    self.table.c.is_deleted.is_(False),
                )
            )
            .values(
                is_blocked=True,
                updated_at=now,
            )
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount > 0

    async def unblock_user(self, user_id: UUID) -> bool:
        """Разблокировать пользователя."""
        now = datetime.now(timezone.utc)
        stmt = (
            self.table.update()
            .where(
                and_(
                    self.table.c.id == user_id,
                    self.table.c.is_deleted.is_(False),
                )
            )
            .values(
                is_blocked=False,
                updated_at=now,
            )
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount > 0

    async def change_password(self, user_id: UUID, hashed_password: str) -> bool:
        """Изменить пароль пользователя."""
        now = datetime.now(timezone.utc)
        stmt = (
            self.table.update()
            .where(
                and_(
                    self.table.c.id == user_id,
                    self.table.c.is_deleted.is_(False),
                )
            )
            .values(
                password=hashed_password,
                updated_at=now,
            )
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount > 0

    async def get_user_scopes(self, user_id: UUID) -> list[UserScope]:
        """Получить роли пользователя."""
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

    async def get_all_roles(
        self,
        *,
        scope_name: str | None = None,
    ) -> list[UserScope]:
        """Получить все роли с фильтрацией по scope_name (regex)."""
        query = select(user_scopes)

        # Фильтр по scope_name (регистронезависимый regex)
        if scope_name:
            query = query.where(
                func.lower(user_scopes.c.scope_name).op("~")(f"(?i).*{scope_name}.*")
            )

        query = query.order_by(user_scopes.c.scope_name.asc())

        result = await self.session.execute(query)
        return [UserScope.model_validate(dict(row)) for row in result.mappings().all()]

    async def _set_user_scopes(self, user_id: UUID, scope_ids: list[UUID]) -> None:
        """Установить роли пользователя (удалить старые, добавить новые)."""
        # Удаляем все текущие связи
        delete_stmt = user_scopes_relations.delete().where(
            user_scopes_relations.c.user_id == user_id
        )
        await self.session.execute(delete_stmt)

        # Добавляем новые связи
        if scope_ids:
            for scope_id in scope_ids:
                insert_stmt = user_scopes_relations.insert().values(
                    user_id=user_id,
                    scope_id=scope_id,
                )
                await self.session.execute(insert_stmt)

        await self.session.flush()

    async def get_by_username(self, username: str) -> User | None:
        """Get user by username."""
        stmt = select(self.table).where(
            and_(
                self.table.c.username == username,
                self.table.c.is_deleted.is_(False),
            )
        )
        row = await self.session.execute(stmt)
        mapping = row.mappings().first()
        if mapping is None:
            return None
        return self.entity.model_validate(dict(mapping))
