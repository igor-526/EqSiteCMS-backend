from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.callback_request import callback_request_statuses

from .base_seeder import BaseSeeder


CALLBACK_REQUEST_STATUSES = (
    {"id": 1, "name": "Новая", "color": "#1677FF"},
    {"id": 2, "name": "Обработана", "color": "#52C41A"},
)


class CallbackRequestStatusesSeeder(BaseSeeder):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def run(self) -> None:
        await self.session.execute(
            delete(callback_request_statuses).where(
                callback_request_statuses.c.id.not_in((1, 2))
            )
        )
        stmt = insert(callback_request_statuses).values(list(CALLBACK_REQUEST_STATUSES))
        stmt = stmt.on_conflict_do_update(
            index_elements=[callback_request_statuses.c.id],
            set_={"name": stmt.excluded.name, "color": stmt.excluded.color},
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def prepare(self) -> list[dict[str, object]]:
        return list(CALLBACK_REQUEST_STATUSES)

    async def fetch_existing(
        self, plan: list[dict[str, object]]
    ) -> dict[object, object]:
        return {}

    def diff(
        self, plan: list[dict[str, object]], existing: dict[object, object]
    ) -> list[dict[str, object]]:
        return plan

    async def create_missing(
        self,
        missing: list[dict[str, object]],
        plan: list[dict[str, object]],
        existing: dict[object, object],
    ) -> int:
        return 0
