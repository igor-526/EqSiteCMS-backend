import re
from uuid import UUID

from sqlalchemy import Table, func, or_, select
from sqlalchemy.exc import IntegrityError

from core.entities.breed_groups import BreedGroup
from core.exceptions.base import ClientError
from core.protocols.repositories.breed_group_repository import BreedGroupSort
from models.breed_groups import breed_groups

from .abstract_repository import TenantScopedRepository


class BreedGroupRepository(TenantScopedRepository[BreedGroup]):
    table: Table = breed_groups
    entity = BreedGroup

    async def create(self, entity: BreedGroup) -> BreedGroup:
        try:
            return await super().create(entity)
        except IntegrityError as exc:
            raise ClientError(
                "Группа пород с таким name или slug уже существует"
            ) from exc

    async def update(self, entity: BreedGroup) -> BreedGroup:
        try:
            return await super().update(entity)
        except IntegrityError as exc:
            raise ClientError(
                "Группа пород с таким name или slug уже существует"
            ) from exc

    async def get_filtered(
        self,
        *,
        equestrian_id: UUID,
        name: str | None = None,
        slug: str | None = None,
        page_data: str | None = None,
        sort: list[BreedGroupSort] | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[list[BreedGroup], int]:
        predicate = self.table.c.equestrian_id == equestrian_id
        stmt = select(self.table).where(predicate)
        count_stmt = select(func.count()).select_from(self.table).where(predicate)
        conditions = []
        for column, value in (
            (self.table.c.name, name),
            (self.table.c.slug, slug),
            (self.table.c.page_data, page_data),
        ):
            if value:
                conditions.append(column.op("~*")(re.escape(value)))
        if conditions:
            text_predicate = or_(*conditions)
            stmt = stmt.where(text_predicate)
            count_stmt = count_stmt.where(text_predicate)
        ordering = []
        for value in sort or []:
            column = self.table.c[value.removeprefix("-")]
            ordering.append(column.desc() if value.startswith("-") else column.asc())
        if not ordering:
            ordering = [self.table.c.created_at.desc(), self.table.c.id.desc()]
        elif not any(value.removeprefix("-") == "id" for value in sort or []):
            ordering.append(self.table.c.id.asc())
        stmt = stmt.order_by(*ordering)
        if limit is not None:
            stmt = stmt.limit(limit)
        if offset is not None:
            stmt = stmt.offset(offset)
        rows = await self.session.execute(stmt)
        result = [
            self.entity.model_validate(dict(row)) for row in rows.mappings().all()
        ]
        total = (await self.session.execute(count_stmt)).scalar() or 0
        return result, total
