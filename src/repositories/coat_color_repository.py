import re
from typing import Literal
from uuid import UUID

from sqlalchemy import Table, func, or_, select

from core.entities.coat_color import CoatColor
from models.coat_color import coat_color

from .abstract_repository import TenantScopedRepository


class CoatColorRepository(TenantScopedRepository[CoatColor]):
    table: Table = coat_color
    entity = CoatColor

    async def get_filtered(
        self,
        *,
        equestrian_id: UUID,
        name: str | None = None,
        short_name: str | None = None,
        slug: str | None = None,
        description: str | None = None,
        page_data: str | None = None,
        sort: (
            list[
                Literal[
                    "name",
                    "short_name",
                    "description",
                    "slug",
                    "-name",
                    "-short_name",
                    "-description",
                    "-slug",
                ]
            ]
            | None
        ) = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[list[CoatColor], int]:
        """Получить отфильтрованный список с подсчётом общего количества."""
        stmt = select(self.table).where(self.table.c.equestrian_id == equestrian_id)
        count_stmt = (
            select(func.count())
            .select_from(self.table)
            .where(self.table.c.equestrian_id == equestrian_id)
        )

        conditions = []
        if name:
            conditions.append(self.table.c.name.op("~*")(re.escape(name)))
        if short_name:
            conditions.append(self.table.c.short_name.op("~*")(re.escape(short_name)))
        if slug:
            conditions.append(self.table.c.slug.op("~*")(re.escape(slug)))
        if description:
            conditions.append(self.table.c.description.op("~*")(re.escape(description)))
        if page_data:
            conditions.append(self.table.c.page_data.op("~*")(re.escape(page_data)))

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
