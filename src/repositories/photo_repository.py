from typing import Literal
from uuid import UUID

from sqlalchemy import Table, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.entities.photos import Photo
from models.horse import horse_photos
from models.photos import photos
from models.prices import price_photos

from .abstract_repository import AbstractRepository


class PhotoRepository(AbstractRepository[Photo]):
    table: Table = photos
    entity = Photo

    async def find_by_name(self, name: str) -> Photo | None:
        stmt = select(self.table).where(self.table.c.name == name)
        row = await self.session.execute(stmt)
        mapping = row.mappings().first()
        if mapping is None:
            return None
        return self.entity.model_validate(dict(mapping))

    async def get_filtered(
        self,
        *,
        name: str | None = None,
        description: str | None = None,
        price_ids: list[UUID] | None = None,
        horse_ids: list[UUID] | None = None,
        sort: (
            list[
                Literal[
                    "name",
                    "description",
                    "created_at",
                    "-name",
                    "-description",
                    "-created_at",
                ]
            ]
            | None
        ) = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[list[Photo], int]:
        base_table = self.table
        conditions = []

        if price_ids or horse_ids:
            photo_ids_conditions = []
            if price_ids:
                price_photo_ids_stmt = (
                    select(price_photos.c.photo_id)
                    .where(price_photos.c.price_id.in_(price_ids))
                    .distinct()
                )
                photo_ids_conditions.append(self.table.c.id.in_(price_photo_ids_stmt))

            if horse_ids:
                horse_photo_ids_stmt = (
                    select(horse_photos.c.photo_id)
                    .where(horse_photos.c.horse_id.in_(horse_ids))
                    .distinct()
                )
                photo_ids_conditions.append(self.table.c.id.in_(horse_photo_ids_stmt))

            if photo_ids_conditions:
                from sqlalchemy import or_ as sql_or

                conditions.append(sql_or(*photo_ids_conditions))

        if name:
            conditions.append(self.table.c.name.ilike(f"%{name}%"))
        if description:
            conditions.append(self.table.c.description.ilike(f"%{description}%"))

        stmt = select(self.table).distinct()
        count_stmt = select(func.count(func.distinct(self.table.c.id)))

        if conditions:
            where_clause = or_(*conditions)
            stmt = stmt.where(where_clause)
            count_stmt = count_stmt.where(where_clause)

        order_by_clauses = []

        if sort:
            for field in sort:
                if field.startswith("-"):
                    order_by_clauses.append(self.table.c[field[1:]].desc())
                else:
                    order_by_clauses.append(self.table.c[field].asc())

        user_sorts_by_created_at = sort and any(
            field in ("created_at", "-created_at") for field in sort
        )
        if not user_sorts_by_created_at:
            order_by_clauses.append(self.table.c.created_at.desc())

        if order_by_clauses:
            stmt = stmt.order_by(*order_by_clauses)

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

    async def batch_delete(self, ids: list[UUID]) -> None:
        if not ids:
            return

        stmt = self.table.delete().where(self.table.c.id.in_(ids))
        await self.session.execute(stmt)
        await self.session.commit()
