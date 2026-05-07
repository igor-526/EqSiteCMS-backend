from uuid import UUID

from sqlalchemy import Table, select

from core.entities.equestrian import Equestrian
from models.equestrian import equestrians

from .abstract_repository import AbstractRepository


class EquestrianRepository(AbstractRepository[Equestrian]):
    table: Table = equestrians
    entity = Equestrian

    async def get_by_id(self, id: UUID) -> Equestrian | None:
        return await super().get_by_id(id)

    async def get_by_service_key(self, service_key: str) -> Equestrian | None:
        stmt = select(self.table).where(self.table.c.service_key == service_key)
        row = await self.session.execute(stmt)
        mapping = row.mappings().first()
        if mapping is None:
            return None
        return self.entity.model_validate(dict(mapping))
