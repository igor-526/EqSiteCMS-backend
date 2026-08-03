from uuid import UUID

from sqlalchemy import Table, select

from core.entities.horse_service import HorseServiceEntity, HorseServiceRelations
from models.horse_service import horse_service, horse_service_relations

from .abstract_repository import AbstractRepository


class HorseServiceRelationsRepository(AbstractRepository[HorseServiceRelations]):
    """Репозиторий для работы со связями лошадь-услуга."""

    table: Table = horse_service_relations
    entity = HorseServiceRelations

    async def get_list_by_horse(self, *, horse_id: UUID) -> list[HorseServiceRelations]:
        """Получить все связи для конкретной лошади."""
        stmt = select(self.table).where(self.table.c.horse_id == horse_id).order_by(self.table.c.id.asc())
        rows = await self.session.execute(stmt)
        return [self.entity.model_validate(dict(row)) for row in rows.mappings().all()]

    async def get_by_id_and_horse(
        self, *, relation_id: UUID, horse_id: UUID
    ) -> HorseServiceRelations | None:
        """Получить связь по id и horse_id."""
        stmt = select(self.table).where(
            self.table.c.id == relation_id,
            self.table.c.horse_id == horse_id,
        )
        row = await self.session.execute(stmt)
        mapping = row.mappings().first()
        if mapping is None:
            return None
        return self.entity.model_validate(dict(mapping))

    async def get_by_horse_and_service(
        self, *, horse_id: UUID, service_id: UUID
    ) -> HorseServiceRelations | None:
        """Получить связь по horse_id и service_id."""
        stmt = select(self.table).where(
            self.table.c.horse_id == horse_id,
            self.table.c.service_id == service_id,
        )
        row = await self.session.execute(stmt)
        mapping = row.mappings().first()
        if mapping is None:
            return None
        return self.entity.model_validate(dict(mapping))

    async def get_available_services(
        self, *, horse_id: UUID, equestrian_id: UUID, search: str | None = None
    ) -> list[HorseServiceEntity]:
        """Получить услуги, не привязанные к данной лошади, с фильтром search."""
        linked_subq = (
            select(horse_service_relations.c.service_id)
            .where(horse_service_relations.c.horse_id == horse_id)
            .scalar_subquery()
        )
        stmt = select(horse_service).where(
            horse_service.c.equestrian_id == equestrian_id,
            ~horse_service.c.id.in_(linked_subq),
        )
        if search:
            stmt = stmt.where(horse_service.c.name.ilike(f"%{search}%"))
        stmt = stmt.order_by(horse_service.c.name.asc())
        rows = await self.session.execute(stmt)
        return [
            HorseServiceEntity.model_validate(dict(row))
            for row in rows.mappings().all()
        ]
