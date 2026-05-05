from typing import Literal
from uuid import UUID

from sqlalchemy import Table, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.entities.horse_owner import HorseOwner
from models.horse_owner import horse_owner

from .abstract_repository import AbstractRepository


class HorseOwnerRepository(AbstractRepository[HorseOwner]):
    table: Table = horse_owner
    entity = HorseOwner

    async def get_filtered(
        self,
        *,
        name: str | None = None,
        description: str | None = None,
        type: list[str] | None = None,
        address: str | None = None,
        phone_numbers: str | None = None,
        sort: (
            list[
                Literal["name", "description", "type", "-name", "-description", "-type"]
            ]
            | None
        ) = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[list[HorseOwner], int]:
        """Получить отфильтрованный список с подсчётом общего количества."""
        stmt = select(self.table)
        count_stmt = select(func.count()).select_from(self.table)

        conditions = []
        if name:
            conditions.append(self.table.c.name.ilike(f"%{name}%"))
        if description:
            conditions.append(self.table.c.description.ilike(f"%{description}%"))
        if type:
            conditions.append(self.table.c.type.in_(type))
        if address:
            conditions.append(self.table.c.address.ilike(f"%{address}%"))
        if phone_numbers:
            # Поиск в JSONB массиве phone_numbers
            conditions.append(
                self.table.c.phone_numbers.astext.ilike(f"%{phone_numbers}%")
            )

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
