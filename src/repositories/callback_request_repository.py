from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import asc, case, desc, func, select, update
from sqlalchemy.sql.dml import UpdateBase
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession

from core.entities.callback_request import CallbackRequest, CallbackRequestStatus
from models.callback_request import callback_request_statuses, callback_requests


class CallbackRequestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _entity(row: RowMapping) -> CallbackRequest:
        return CallbackRequest.model_validate(dict(row))

    async def create_and_commit(self, entity: CallbackRequest) -> CallbackRequest:
        await self.session.execute(
            callback_requests.insert().values(**entity.model_dump())
        )
        await self.session.commit()
        return entity

    async def get_statuses(self) -> list[CallbackRequestStatus]:
        rows = await self.session.execute(
            select(callback_request_statuses).order_by(callback_request_statuses.c.id)
        )
        return [
            CallbackRequestStatus.model_validate(dict(row))
            for row in rows.mappings().all()
        ]

    async def status_exists(self, status: int) -> bool:
        value = await self.session.scalar(
            select(callback_request_statuses.c.id).where(
                callback_request_statuses.c.id == status
            )
        )
        return value is not None

    async def get_by_id(
        self, id: UUID, *, equestrian_id: UUID
    ) -> CallbackRequest | None:
        row = await self.session.execute(
            select(callback_requests).where(
                callback_requests.c.id == id,
                callback_requests.c.equestrian_id == equestrian_id,
            )
        )
        mapping = row.mappings().first()
        return None if mapping is None else self._entity(mapping)

    async def list_page(
        self,
        *,
        equestrian_id: UUID,
        statuses: list[int] | None,
        spam: list[bool] | None,
        created_from: datetime | None,
        created_to: datetime | None,
        name: str | None,
        phone: str | None,
        comment: str | None,
        sort_by: str,
        direction: str,
        limit: int,
        offset: int,
    ) -> tuple[list[CallbackRequest], int]:
        conditions = [callback_requests.c.equestrian_id == equestrian_id]
        if statuses:
            conditions.append(callback_requests.c.status.in_(statuses))
        if spam is None:
            conditions.append(callback_requests.c.is_spam.is_(False))
        elif len(set(spam)) == 1:
            conditions.append(callback_requests.c.is_spam == spam[0])
        if created_from:
            conditions.append(callback_requests.c.created_at >= created_from)
        if created_to:
            conditions.append(callback_requests.c.created_at <= created_to)
        for value, column in (
            (name, callback_requests.c.name),
            (phone, callback_requests.c.phone),
            (comment, callback_requests.c.comment),
        ):
            if value:
                conditions.append(column.op("~*")(value))
        total = int(
            (
                await self.session.scalar(
                    select(func.count())
                    .select_from(callback_requests)
                    .where(*conditions)
                )
            )
            or 0
        )
        primary = (
            callback_requests.c.status
            if sort_by == "status"
            else callback_requests.c.created_at
        )
        ordering = asc(primary) if direction == "asc" else desc(primary)
        secondary = (
            desc(callback_requests.c.created_at)
            if sort_by == "status"
            else asc(callback_requests.c.status)
        )
        stmt = (
            select(callback_requests)
            .where(*conditions)
            .order_by(ordering, secondary, asc(callback_requests.c.id))
            .limit(limit)
            .offset(offset)
        )
        rows = await self.session.execute(stmt)
        return [self._entity(row) for row in rows.mappings().all()], total

    async def _updated(self, stmt: UpdateBase) -> CallbackRequest | None:
        row = await self.session.execute(stmt)
        mapping = row.mappings().first()
        await self.session.flush()
        return None if mapping is None else self._entity(mapping)

    async def set_status(
        self, *, id: UUID, equestrian_id: UUID | None, status: int
    ) -> CallbackRequest | None:
        conditions = [callback_requests.c.id == id]
        if equestrian_id is not None:
            conditions.append(callback_requests.c.equestrian_id == equestrian_id)
        stmt = (
            update(callback_requests)
            .where(*conditions)
            .values(
                status=case((callback_requests.c.is_spam.is_(True), 2), else_=status),
                updated_at=datetime.now(timezone.utc),
            )
            .returning(callback_requests)
        )
        return await self._updated(stmt)

    async def set_spam(
        self, *, id: UUID, equestrian_id: UUID | None, is_spam: bool
    ) -> CallbackRequest | None:
        values: dict[str, object] = {
            "is_spam": is_spam,
            "updated_at": datetime.now(timezone.utc),
        }
        if is_spam:
            values["status"] = 2
        conditions = [callback_requests.c.id == id]
        if equestrian_id is not None:
            conditions.append(callback_requests.c.equestrian_id == equestrian_id)
        stmt = (
            update(callback_requests)
            .where(*conditions)
            .values(**values)
            .returning(callback_requests)
        )
        return await self._updated(stmt)

    async def set_delivery(
        self, *, id: UUID, notifications_delivered: bool
    ) -> CallbackRequest | None:
        stmt = (
            update(callback_requests)
            .where(callback_requests.c.id == id)
            .values(
                notifications_delivered=notifications_delivered,
                updated_at=datetime.now(timezone.utc),
            )
            .returning(callback_requests)
        )
        return await self._updated(stmt)
