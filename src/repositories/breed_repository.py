import re
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from sqlalchemy import Table, func, insert, or_, select, update
from sqlalchemy.engine import RowMapping

from core.entities.breeds import Breed
from core.entities.horse import HorseKindEnum
from models.breed_groups import breed_groups
from models.breeds import breeds

from .abstract_repository import TenantScopedRepository


class BreedRepository(TenantScopedRepository[Breed]):
    table: Table = breeds
    entity = Breed

    @staticmethod
    def _from_row(row: RowMapping) -> Breed:
        data = dict(row)
        group_id = data.pop("group_id")
        if group_id is not None:
            data["group"] = {
                "id": group_id,
                "name": data.pop("group_name"),
                "slug": data.pop("group_slug"),
            }
        else:
            data["group"] = None
            data.pop("group_name")
            data.pop("group_slug")
        return Breed.model_validate(data)

    def _joined_select(self, *, equestrian_id: UUID):
        join = self.table.outerjoin(
            breed_groups,
            (self.table.c.breed_group_id == breed_groups.c.id)
            & (breed_groups.c.equestrian_id == equestrian_id),
        )
        return select(
            self.table,
            breed_groups.c.id.label("group_id"),
            breed_groups.c.name.label("group_name"),
            breed_groups.c.slug.label("group_slug"),
        ).select_from(join)

    async def get_by_id(self, id: UUID, *, equestrian_id: UUID) -> Breed | None:
        row = await self.session.execute(
            self._joined_select(equestrian_id=equestrian_id).where(
                self.table.c.id == id,
                self.table.c.equestrian_id == equestrian_id,
            )
        )
        mapping = row.mappings().first()
        return None if mapping is None else self._from_row(mapping)

    async def get_by_slug(self, slug: str, *, equestrian_id: UUID) -> Breed | None:
        row = await self.session.execute(
            self._joined_select(equestrian_id=equestrian_id).where(
                self.table.c.slug == slug,
                self.table.c.equestrian_id == equestrian_id,
            )
        )
        mapping = row.mappings().first()
        return None if mapping is None else self._from_row(mapping)

    async def create(self, entity: Breed) -> Breed:
        values = entity.model_dump(exclude={"group"})
        await self.session.execute(insert(self.table).values(**values))
        await self.session.flush()
        return entity

    async def update(self, entity: Breed) -> Breed:
        now = datetime.now(timezone.utc)
        entity.updated_at = now
        values = entity.model_dump(exclude={"group"})
        await self.session.execute(
            update(self.table)
            .where(
                self.table.c.id == entity.id,
                self.table.c.equestrian_id == entity.equestrian_id,
            )
            .values(**values)
        )
        await self.session.flush()
        return entity

    async def get_filtered(
        self,
        *,
        equestrian_id: UUID,
        name: str | None = None,
        short_name: str | None = None,
        slug: str | None = None,
        description: str | None = None,
        page_data: str | None = None,
        kind: list[HorseKindEnum] | None = None,
        sort: (
            list[
                Literal[
                    "name",
                    "short_name",
                    "description",
                    "slug",
                    "kind",
                    "-name",
                    "-short_name",
                    "-description",
                    "-slug",
                    "-kind",
                    "created_at",
                    "-created_at",
                    "group_name",
                    "-group_name",
                ]
            ]
            | None
        ) = None,
        breed_group_ids: list[UUID] | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[list[Breed], int]:
        """Получить отфильтрованный список с подсчётом общего количества."""
        join = self.table.outerjoin(
            breed_groups,
            (self.table.c.breed_group_id == breed_groups.c.id)
            & (breed_groups.c.equestrian_id == equestrian_id),
        )
        stmt = (
            select(
                self.table,
                breed_groups.c.id.label("group_id"),
                breed_groups.c.name.label("group_name"),
                breed_groups.c.slug.label("group_slug"),
            )
            .select_from(join)
            .where(self.table.c.equestrian_id == equestrian_id)
        )
        count_stmt = (
            select(func.count())
            .select_from(join)
            .where(self.table.c.equestrian_id == equestrian_id)
        )

        text_conditions = []
        if name:
            text_conditions.append(self.table.c.name.op("~*")(re.escape(name)))
        if short_name:
            text_conditions.append(
                self.table.c.short_name.op("~*")(re.escape(short_name))
            )
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

        if breed_group_ids:
            group_clause = self.table.c.breed_group_id.in_(breed_group_ids)
            stmt = stmt.where(group_clause)
            count_stmt = count_stmt.where(group_clause)

        # Сортировка
        if sort:
            order_by_clauses = []
            for field in sort:
                descending = field.startswith("-")
                field_name = field.removeprefix("-")
                column = (
                    breed_groups.c.name
                    if field_name == "group_name"
                    else self.table.c[field_name]
                )
                if field_name == "group_name" and descending:
                    order_by_clauses.append(column.desc().nulls_last())
                elif field_name == "group_name":
                    order_by_clauses.append(column.asc().nulls_last())
                elif descending:
                    order_by_clauses.append(column.desc())
                else:
                    order_by_clauses.append(column.asc())
            order_by_clauses.append(self.table.c.id.asc())
            stmt = stmt.order_by(*order_by_clauses)
        else:
            stmt = stmt.order_by(self.table.c.created_at.desc(), self.table.c.id.desc())

        # Пагинация
        if limit is not None:
            stmt = stmt.limit(limit)
        if offset is not None:
            stmt = stmt.offset(offset)

        rows = await self.session.execute(stmt)
        entities = [self._from_row(row) for row in rows.mappings().all()]

        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        return entities, total
