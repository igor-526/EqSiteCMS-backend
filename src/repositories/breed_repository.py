from typing import Literal

from sqlalchemy import Table, func, or_, select

from core.entities.breeds import Breed
from models.breeds import breeds

from .abstract_repository import AbstractRepository


class BreedRepository(AbstractRepository[Breed]):
    table: Table = breeds
    entity = Breed

    async def get_filtered(
        self,
        *,
        name: str | None = None,
        slug: str | None = None,
        description: str | None = None,
        page_data: str | None = None,
        sort: (
            list[
                Literal["name", "description", "slug", "-name", "-description", "-slug"]
            ]
            | None
        ) = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[list[Breed], int]:
        """Получить отфильтрованный список с подсчётом общего количества."""
        stmt = select(self.table)
        count_stmt = select(func.count()).select_from(self.table)

        conditions = []
        if name:
            conditions.append(self.table.c.name.ilike(f"%{name}%"))
        if slug:
            conditions.append(self.table.c.slug.ilike(f"%{slug}%"))
        if description:
            conditions.append(self.table.c.description.ilike(f"%{description}%"))
        if page_data:
            conditions.append(self.table.c.page_data.ilike(f"%{page_data}%"))

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
