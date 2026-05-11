import re
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    ColumnElement,
    Table,
    and_,
    case,
    delete,
    func,
    insert,
    or_,
    select,
    update,
)

from core.entities.news import News, NewsPhoto, NewsStatus
from models.news import news, news_photos

from .abstract_repository import TenantScopedRepository


class NewsRepository(TenantScopedRepository[News]):
    table: Table = news
    entity = News

    async def get_cms_filtered(
        self,
        *,
        equestrian_id: UUID,
        name: str | None = None,
        snippet: str | None = None,
        content: str | None = None,
        published_at_from: datetime | None = None,
        published_at_to: datetime | None = None,
        status: list[NewsStatus] | None = None,
        sort: str = "-published_at",
        limit: int = 25,
        offset: int = 0,
    ) -> tuple[list[News], int]:
        base_where = self.table.c.equestrian_id == equestrian_id
        stmt = select(self.table).where(base_where)
        count_stmt = select(func.count()).select_from(self.table).where(base_where)

        conditions: list[ColumnElement[Any]] = []

        if name:
            conditions.append(self.table.c.name.op("~*")(re.escape(name)))
        if snippet:
            conditions.append(self.table.c.snippet.op("~*")(re.escape(snippet)))
        if content:
            conditions.append(self.table.c.content.op("~*")(re.escape(content)))
        if published_at_from:
            conditions.append(self.table.c.published_at >= published_at_from)
        if published_at_to:
            conditions.append(self.table.c.published_at <= published_at_to)

        if status:
            status_conditions = []
            for s in status:
                if s == NewsStatus.PUBLISHED:
                    status_conditions.append(
                        and_(
                            self.table.c.is_deleted == False,  # noqa: E712
                            self.table.c.published_at <= func.now(),
                        )
                    )
                elif s == NewsStatus.SCHEDULED:
                    status_conditions.append(
                        and_(
                            self.table.c.is_deleted == False,  # noqa: E712
                            self.table.c.published_at > func.now(),
                        )
                    )
                elif s == NewsStatus.DELETED:
                    status_conditions.append(
                        self.table.c.is_deleted == True  # noqa: E712
                    )
            if status_conditions:
                conditions.append(or_(*status_conditions))

        if conditions:
            where_clause = and_(*conditions)
            stmt = stmt.where(where_clause)
            count_stmt = count_stmt.where(where_clause)

        status_case = case(
            (self.table.c.is_deleted == True, 3),  # noqa: E712
            (self.table.c.published_at > func.now(), 2),
            else_=1,
        )

        sort_map = {
            "name": self.table.c.name.asc(),
            "-name": self.table.c.name.desc(),
            "published_at": self.table.c.published_at.asc(),
            "-published_at": self.table.c.published_at.desc(),
            "status": status_case.asc(),
            "-status": status_case.desc(),
            "created_at": self.table.c.created_at.asc(),
            "-created_at": self.table.c.created_at.desc(),
        }
        order_clause = sort_map.get(sort, self.table.c.published_at.desc())
        stmt = stmt.order_by(order_clause)

        stmt = stmt.limit(limit).offset(offset)

        rows = await self.session.execute(stmt)
        entities = [
            self.entity.model_validate(dict(row)) for row in rows.mappings().all()
        ]

        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        return entities, total

    async def get_public_filtered(
        self,
        *,
        equestrian_id: UUID,
        limit: int = 25,
        offset: int = 0,
    ) -> tuple[list[News], int]:
        where_clause = and_(
            self.table.c.equestrian_id == equestrian_id,
            self.table.c.is_deleted == False,  # noqa: E712
            self.table.c.published_at <= func.now(),
        )
        stmt = (
            select(self.table)
            .where(where_clause)
            .order_by(self.table.c.published_at.desc())
            .limit(limit)
            .offset(offset)
        )
        count_stmt = select(func.count()).select_from(self.table).where(where_clause)

        rows = await self.session.execute(stmt)
        entities = [
            self.entity.model_validate(dict(row)) for row in rows.mappings().all()
        ]

        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        return entities, total

    async def get_public_by_id(self, id: UUID, *, equestrian_id: UUID) -> News | None:
        stmt = select(self.table).where(
            self.table.c.id == id,
            self.table.c.equestrian_id == equestrian_id,
            self.table.c.is_deleted == False,  # noqa: E712
            self.table.c.published_at <= func.now(),
        )
        row = await self.session.execute(stmt)
        mapping = row.mappings().first()
        if mapping is None:
            return None
        return self.entity.model_validate(dict(mapping))

    async def get_news_photos(
        self, news_id: UUID, *, equestrian_id: UUID
    ) -> list[NewsPhoto]:
        stmt = (
            select(news_photos)
            .join(news, news_photos.c.news_id == news.c.id)
            .where(
                news_photos.c.news_id == news_id,
                news.c.equestrian_id == equestrian_id,
            )
        )
        rows = await self.session.execute(stmt)
        return [NewsPhoto.model_validate(dict(row)) for row in rows.mappings().all()]

    async def set_news_photos(
        self,
        news_id: UUID,
        photo_ids: list[UUID] | None = None,
        main_photo_id: UUID | None = None,
        *,
        equestrian_id: UUID,
    ) -> None:
        if photo_ids is not None:
            delete_stmt = delete(news_photos).where(
                news_photos.c.news_id == news_id,
                news_photos.c.news_id.in_(
                    select(news.c.id).where(news.c.equestrian_id == equestrian_id)
                ),
            )
            await self.session.execute(delete_stmt)

            if photo_ids:
                values = [
                    {"news_id": news_id, "photo_id": photo_id, "is_main": False}
                    for photo_id in photo_ids
                ]
                await self.session.execute(insert(news_photos).values(values))

        if main_photo_id is not None:
            await self.session.execute(
                update(news_photos)
                .where(
                    news_photos.c.news_id == news_id,
                    news_photos.c.news_id.in_(
                        select(news.c.id).where(news.c.equestrian_id == equestrian_id)
                    ),
                )
                .values(is_main=False)
            )
            check = await self.session.execute(
                select(news_photos).where(
                    and_(
                        news_photos.c.news_id == news_id,
                        news_photos.c.photo_id == main_photo_id,
                    )
                )
            )
            if check.mappings().first():
                await self.session.execute(
                    update(news_photos)
                    .where(
                        and_(
                            news_photos.c.news_id == news_id,
                            news_photos.c.photo_id == main_photo_id,
                        )
                    )
                    .values(is_main=True)
                )
            else:
                await self.session.execute(
                    insert(news_photos).values(
                        news_id=news_id, photo_id=main_photo_id, is_main=True
                    )
                )

        await self.session.flush()
