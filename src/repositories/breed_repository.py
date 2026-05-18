import re
from typing import Literal
from uuid import UUID

from sqlalchemy import Table, func, or_, select

from core.entities.breeds import Breed
from core.entities.horse import HorseKindEnum
from models.breeds import breeds

from .abstract_repository import TenantScopedRepository


class BreedRepository(TenantScopedRepository[Breed]):
    table: Table = breeds
    entity = Breed

    async def get_filtered(
        self,
        *,
        equestrian_id: UUID,
        name: str | None = None,
        slug: str | None = None,
        description: str | None = None,
        page_data: str | None = None,
        kind: list[HorseKindEnum] | None = None,
        sort: (
            list[
                Literal[
                    "name",
                    "description",
                    "slug",
                    "kind",
                    "-name",
                    "-description",
                    "-slug",
                    "-kind",
                ]
            ]
            | None
        ) = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[list[Breed], int]:
        """Получить отфильтрованный список с подсчётом общего количества."""
        stmt = select(self.table).where(self.table.c.equestrian_id == equestrian_id)
        count_stmt = (
            select(func.count())
            .select_from(self.table)
            .where(self.table.c.equestrian_id == equestrian_id)
        )

        text_conditions = []
        if name:
            text_conditions.append(self.table.c.name.op("~*")(re.escape(name)))
        if slug:
            text_conditions.append(self.table.c.slug.op("~*")(re.escape(slug)))
        if description:
            text_conditions.append(
                self.table.c.description.op("~*")(re.escape(description))
            )
        if page_data:
            text_conditions.append(
                self.table.c.page_data.op("~*")(re.escape(page_data))
            )

        if text_conditions:
            where_clause = or_(*text_conditions)
            stmt = stmt.where(where_clause)
            count_stmt = count_stmt.where(where_clause)

        if kind:
            where_clause = self.table.c.kind.in_([item.value for item in kind])
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
