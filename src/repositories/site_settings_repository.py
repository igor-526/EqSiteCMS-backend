from typing import Literal

from sqlalchemy import Table, func, or_, select

from core.entities.site_settings import SiteSetting
from models.site_settings import site_settings

from .abstract_repository import AbstractRepository


class SiteSettingsRepository(AbstractRepository[SiteSetting]):
    table: Table = site_settings
    entity = SiteSetting

    async def get_filtered(
        self,
        *,
        key: list[str] | None = None,
        name: str | None = None,
        value: str | None = None,
        description: str | None = None,
        type: (
            list[
                Literal[
                    "string",
                    "number",
                    "float",
                    "boolean",
                    "object",
                    "date",
                    "time",
                    "datetime",
                ]
            ]
            | None
        ) = None,
        sort: (
            list[Literal["key", "name", "type", "-key", "-name", "-type"]] | None
        ) = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[list[SiteSetting], int]:
        """Получить отфильтрованный список с подсчётом общего количества."""
        stmt = select(self.table)
        count_stmt = select(func.count()).select_from(self.table)

        conditions = []
        if key:
            conditions.append(self.table.c.key.in_(key))
        if name:
            conditions.append(self.table.c.name.ilike(f"%{name}%"))
        if value:
            conditions.append(self.table.c.value.ilike(f"%{value}%"))
        if description:
            conditions.append(self.table.c.description.ilike(f"%{description}%"))
        if type:
            conditions.append(self.table.c.type.in_(type))

        if conditions:
            where_clause = or_(*conditions)
            stmt = stmt.where(where_clause)
            count_stmt = count_stmt.where(where_clause)

        # Сортировка
        if sort:
            order_by_clauses = []
            for field in sort:
                if field.startswith("-"):
                    order_by_clauses.append(self.table.c[field[1:]].desc())
                else:
                    order_by_clauses.append(self.table.c[field].asc())
            stmt = stmt.order_by(*order_by_clauses)

        # Пагинация
        if limit is not None:
            stmt = stmt.limit(limit)
        if offset is not None:
            stmt = stmt.offset(offset)

        rows = await self.session.execute(stmt)
        entities = [
            self.entity.model_validate(dict(row)) for row in rows.mappings().all()
        ]

        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        return entities, total

    async def find_by_key(self, key: str) -> SiteSetting | None:
        """Проверить существование key."""
        stmt = select(self.table).where(self.table.c.key == key)
        row = await self.session.execute(stmt)
        mapping = row.mappings().first()
        if mapping is None:
            return None
        return self.entity.model_validate(dict(mapping))

    async def find_by_name(self, name: str) -> SiteSetting | None:
        """Проверить существование name."""
        return await super().find_by_name(name)
