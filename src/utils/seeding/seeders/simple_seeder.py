from sqlalchemy import Table, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.entities.base import Entity

from .base_seeder import BaseSeeder


class SimpleSeeder[T: Entity](BaseSeeder):
    table: Table
    entity_cls: type[T]
    seeds: list[T]

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def prepare(self) -> list[T]:
        return self.seeds

    async def fetch_existing(self, plan: list[T]) -> dict[str, T]:
        values = [getattr(entity, "id") for entity in plan]
        if not values:
            return {}
        column = getattr(self.table.c, "id")
        stmt = select(self.table).where(column.in_(values))
        rows = await self.session.execute(stmt)
        return {
            row["id"]: self.entity_cls.model_validate(dict(row))
            for row in rows.mappings().all()
        }

    def diff(self, plan: list[T], existing: dict[str, T]) -> list[T]:
        existing_values = set(existing.keys())
        return [e for e in plan if getattr(e, "id") not in existing_values]

    async def create_missing(
        self, missing: list[T], plan: list[T], existing: dict[str, T]
    ) -> int:
        if not missing:
            return 0
        values = [e.model_dump() for e in missing]
        stmt = insert(self.table)
        await self.session.execute(stmt, values)
        await self.session.flush()
        return len(missing)
