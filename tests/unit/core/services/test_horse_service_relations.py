from __future__ import annotations

from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from core.entities.horse import Horse
from core.entities.horse_service import HorseServiceEntity, HorseServiceRelations
from core.entities.price import PriceFormatter
from core.exceptions.base import ClientError, ConflictError, NotFoundError
from core.schemas.horse_service_relations import (
    HorseServiceRelationCreateDto,
    HorseServiceRelationUpdateDto,
)
from core.services.horse_service_relations import HorseServiceRelationsService

pytestmark = pytest.mark.asyncio


class FakeRelationsRepository:
    def __init__(self) -> None:
        self.relations: dict[UUID, HorseServiceRelations] = {}
        self.available_services: list[HorseServiceEntity] = []
        self.calls: list[tuple[str, Any]] = []

    async def create(self, entity: HorseServiceRelations) -> HorseServiceRelations:
        self.calls.append(("create", entity))
        self.relations[entity.id] = entity
        return entity

    async def update(self, entity: HorseServiceRelations) -> HorseServiceRelations:
        self.calls.append(("update", entity))
        self.relations[entity.id] = entity
        return entity

    async def delete(self, id: UUID) -> None:
        self.calls.append(("delete", id))
        self.relations.pop(id, None)

    async def get_by_id(self, id: UUID) -> HorseServiceRelations | None:
        self.calls.append(("get_by_id", id))
        return self.relations.get(id)

    async def get_list_by_horse(
        self,
        *,
        horse_id: UUID,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[list[HorseServiceRelations], int]:
        self.calls.append(("get_list_by_horse", (horse_id, limit, offset)))
        relations = [r for r in self.relations.values() if r.horse_id == horse_id]
        total = len(relations)
        start = offset or 0
        end = None if limit is None else start + limit
        return relations[start:end], total

    async def get_by_id_and_horse(
        self, *, relation_id: UUID, horse_id: UUID
    ) -> HorseServiceRelations | None:
        self.calls.append(("get_by_id_and_horse", (relation_id, horse_id)))
        r = self.relations.get(relation_id)
        if r is not None and r.horse_id == horse_id:
            return r
        return None

    async def get_by_horse_and_service(
        self, *, horse_id: UUID, service_id: UUID
    ) -> HorseServiceRelations | None:
        self.calls.append(("get_by_horse_and_service", (horse_id, service_id)))
        for r in self.relations.values():
            if r.horse_id == horse_id and r.service_id == service_id:
                return r
        return None

    async def get_available_services(
        self, *, horse_id: UUID, equestrian_id: UUID, search: str | None = None
    ) -> list[HorseServiceEntity]:
        self.calls.append(("get_available_services", (horse_id, equestrian_id, search)))
        return self.available_services


class FakeHorseRepository:
    def __init__(self) -> None:
        self.horses: dict[UUID, Horse] = {}
        self.calls: list[tuple[str, Any]] = []

    def add(self, horse: Horse) -> Horse:
        self.horses[horse.id] = horse
        return horse

    async def get_by_id(self, id: UUID, *, equestrian_id: UUID) -> Horse | None:
        self.calls.append(("get_by_id", (id, equestrian_id)))
        h = self.horses.get(id)
        if h is not None and h.equestrian_id == equestrian_id:
            return h
        return None


class FakeHorseServiceRepository:
    def __init__(self) -> None:
        self.services: dict[UUID, HorseServiceEntity] = {}
        self.calls: list[tuple[str, Any]] = []

    def add(self, service: HorseServiceEntity) -> HorseServiceEntity:
        self.services[service.id] = service
        return service

    async def get_by_id(
        self, id: UUID, *, equestrian_id: UUID
    ) -> HorseServiceEntity | None:
        self.calls.append(("get_by_id", (id, equestrian_id)))
        s = self.services.get(id)
        if s is not None and s.equestrian_id == equestrian_id:
            return s
        return None


def make_horse(**overrides: Any) -> Horse:
    data = {
        "name": "Test Horse",
        "sex": "male",
        "equestrian_id": UUID("11111111-1111-4111-8111-111111111111"),
    }
    data.update(overrides)
    return Horse(**data)


def make_service_entity(**overrides: Any) -> HorseServiceEntity:
    data = {
        "name": "Подковка",
        "slug": "podkovka",
        "description": "Базовая услуга",
        "price": 1000,
        "price_formatter": PriceFormatter.equal,
        "equestrian_id": UUID("11111111-1111-4111-8111-111111111111"),
    }
    data.update(overrides)
    return HorseServiceEntity(**data)


def make_service() -> tuple[
    HorseServiceRelationsService,
    FakeRelationsRepository,
    FakeHorseRepository,
    FakeHorseServiceRepository,
]:
    rel_repo = FakeRelationsRepository()
    horse_repo = FakeHorseRepository()
    svc_repo = FakeHorseServiceRepository()
    service = HorseServiceRelationsService(
        relations_repository=cast(Any, rel_repo),
        horse_repository=cast(Any, horse_repo),
        horse_service_repository=cast(Any, svc_repo),
    )
    return service, rel_repo, horse_repo, svc_repo


EQ_ID = UUID("11111111-1111-4111-8111-111111111111")


async def test_create_relation_success() -> None:
    svc, rel_repo, horse_repo, svc_repo = make_service()
    horse = horse_repo.add(make_horse())
    service_entity = svc_repo.add(make_service_entity())

    result = await svc.create(
        horse.id,
        HorseServiceRelationCreateDto(service_id=service_entity.id),
    )

    assert result.service_id == service_entity.id
    assert result.name == "Подковка"
    assert result.price == 1000
    assert len(rel_repo.relations) == 1


async def test_create_relation_with_overrides() -> None:
    svc, rel_repo, horse_repo, svc_repo = make_service()
    horse = horse_repo.add(make_horse())
    service_entity = svc_repo.add(make_service_entity())

    result = await svc.create(
        horse.id,
        HorseServiceRelationCreateDto(
            service_id=service_entity.id,
            description_override="Особое описание",
            price_override=5000,
        ),
    )

    assert result.description == "Особое описание"
    assert result.price == 5000


async def test_create_duplicate_raises_conflict() -> None:
    svc, rel_repo, horse_repo, svc_repo = make_service()
    horse = horse_repo.add(make_horse())
    service_entity = svc_repo.add(make_service_entity())

    await svc.create(
        horse.id,
        HorseServiceRelationCreateDto(service_id=service_entity.id),
    )

    with pytest.raises(ConflictError):
        await svc.create(
            horse.id,
            HorseServiceRelationCreateDto(service_id=service_entity.id),
        )


async def test_create_nonexistent_horse_raises_not_found() -> None:
    svc, _, _, svc_repo = make_service()
    service_entity = svc_repo.add(make_service_entity())

    with pytest.raises(NotFoundError):
        await svc.create(
            uuid4(),
            HorseServiceRelationCreateDto(service_id=service_entity.id),
        )


async def test_create_nonexistent_service_raises_not_found() -> None:
    svc, _, horse_repo, _ = make_service()
    horse = horse_repo.add(make_horse())

    with pytest.raises(NotFoundError):
        await svc.create(
            horse.id,
            HorseServiceRelationCreateDto(service_id=uuid4()),
        )


async def test_update_relation_success() -> None:
    svc, rel_repo, horse_repo, svc_repo = make_service()
    horse = horse_repo.add(make_horse())
    service_entity = svc_repo.add(make_service_entity())

    created = await svc.create(
        horse.id,
        HorseServiceRelationCreateDto(service_id=service_entity.id),
    )

    result = await svc.update(
        horse.id,
        created.id,
        HorseServiceRelationUpdateDto(price_override=9999),
    )

    assert result.price == 9999


async def test_update_nonexistent_relation_raises_not_found() -> None:
    svc, _, horse_repo, _ = make_service()
    horse = horse_repo.add(make_horse())

    with pytest.raises(NotFoundError):
        await svc.update(
            horse.id,
            uuid4(),
            HorseServiceRelationUpdateDto(price_override=100),
        )


async def test_update_empty_data_raises_client_error() -> None:
    svc, rel_repo, horse_repo, svc_repo = make_service()
    horse = horse_repo.add(make_horse())
    service_entity = svc_repo.add(make_service_entity())

    created = await svc.create(
        horse.id,
        HorseServiceRelationCreateDto(service_id=service_entity.id),
    )

    with pytest.raises(ClientError):
        await svc.update(
            horse.id,
            created.id,
            HorseServiceRelationUpdateDto(),
        )


async def test_delete_relation_success() -> None:
    svc, rel_repo, horse_repo, svc_repo = make_service()
    horse = horse_repo.add(make_horse())
    service_entity = svc_repo.add(make_service_entity())

    created = await svc.create(
        horse.id,
        HorseServiceRelationCreateDto(service_id=service_entity.id),
    )

    await svc.delete(horse.id, created.id)
    assert len(rel_repo.relations) == 0


async def test_delete_nonexistent_raises_not_found() -> None:
    svc, _, horse_repo, _ = make_service()
    horse = horse_repo.add(make_horse())

    with pytest.raises(NotFoundError):
        await svc.delete(horse.id, uuid4())


async def test_get_list_by_horse_returns_relations() -> None:
    svc, rel_repo, horse_repo, svc_repo = make_service()
    horse = horse_repo.add(make_horse())
    s1 = svc_repo.add(make_service_entity(name="Услуга 1", slug="usluga-1"))
    s2 = svc_repo.add(make_service_entity(name="Услуга 2", slug="usluga-2", price=2000))

    await svc.create(horse.id, HorseServiceRelationCreateDto(service_id=s1.id))
    await svc.create(
        horse.id,
        HorseServiceRelationCreateDto(service_id=s2.id, price_override=5000),
    )

    result = await svc.get_list_by_horse(horse.id)
    assert result.total == 2
    assert len(result.items) == 2
    prices = {r.price for r in result.items}
    assert 1000 in prices
    assert 5000 in prices


async def test_get_list_by_horse_forwards_pagination_and_total() -> None:
    svc, rel_repo, horse_repo, svc_repo = make_service()
    horse = horse_repo.add(make_horse())
    first = svc_repo.add(make_service_entity(name="Услуга 1", slug="usluga-1"))
    second = svc_repo.add(make_service_entity(name="Услуга 2", slug="usluga-2"))
    await svc.create(horse.id, HorseServiceRelationCreateDto(service_id=first.id))
    await svc.create(horse.id, HorseServiceRelationCreateDto(service_id=second.id))

    result = await svc.get_list_by_horse(horse.id, limit=1, offset=1)

    assert result.total == 2
    assert len(result.items) == 1
    assert rel_repo.calls[-1] == ("get_list_by_horse", (horse.id, 1, 1))


async def test_get_available_services_returns_unlinked() -> None:
    svc, rel_repo, horse_repo, _ = make_service()
    horse = horse_repo.add(make_horse())
    rel_repo.available_services = [
        make_service_entity(
            description="Полное описание",
            price=2500,
            price_formatter=PriceFormatter.gt,
        )
    ]

    result = await svc.get_available_services(horse.id)
    assert len(result) == 1
    assert result[0].description == "Полное описание"
    assert result[0].price == 2500
    assert result[0].price_formatter == PriceFormatter.gt
    assert set(result[0].model_dump()) == {
        "id",
        "name",
        "slug",
        "description",
        "price",
        "price_formatter",
    }


async def test_get_available_services_with_search() -> None:
    svc, _, horse_repo, _ = make_service()
    horse = horse_repo.add(make_horse())

    result = await svc.get_available_services(horse.id, search="раз")
    assert isinstance(result, list)


async def test_architecture_boundary_has_no_fastapi_dependency() -> None:
    import core.services.horse_service_relations as mod

    assert not hasattr(mod, "HTTPException")
