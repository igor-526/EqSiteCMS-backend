from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from tenant_context import TEST_EQUESTRIAN_CONTEXT

from core.entities.horse_service import HorseServiceEntity
from core.entities.price import PriceFormatter
from core.exceptions.base import ClientError
from core.schemas.horse_service import HorseServiceCreateDto, HorseServiceUpdateDto
from core.services.horse_service import HorseServiceService

pytestmark = pytest.mark.asyncio


class RepositoryError(Exception):
    pass


class FakeHorseServiceRepository:
    def __init__(self) -> None:
        self.by_id: dict[UUID, HorseServiceEntity] = {}
        self.by_slug: dict[str, HorseServiceEntity] = {}
        self.by_name: dict[str, HorseServiceEntity] = {}
        self.calls: list[tuple[str, Any]] = []
        self.filtered_result: tuple[list[HorseServiceEntity], int] = ([], 0)
        self.fail_on: set[str] = set()

    def add(self, entity: HorseServiceEntity) -> HorseServiceEntity:
        self.by_id[entity.id] = entity
        assert entity.slug is not None
        self.by_slug[entity.slug] = entity
        self.by_name[entity.name] = entity
        return entity

    def _fail_if_needed(self, method: str) -> None:
        if method in self.fail_on:
            raise RepositoryError(method)

    async def get_by_id(self, id: UUID) -> HorseServiceEntity | None:
        self.calls.append(("get_by_id", id))
        self._fail_if_needed("get_by_id")
        return self.by_id.get(id)

    async def get_all(
        self, *, limit: int | None = None, offset: int | None = None
    ) -> list[HorseServiceEntity]:
        self.calls.append(("get_all", {"limit": limit, "offset": offset}))
        self._fail_if_needed("get_all")
        return list(self.by_id.values())

    async def get_by_ids(self, ids: Sequence[UUID]) -> dict[UUID, HorseServiceEntity]:
        self.calls.append(("get_by_ids", ids))
        self._fail_if_needed("get_by_ids")
        return {id_: self.by_id[id_] for id_ in ids if id_ in self.by_id}

    async def bulk_create(
        self, entities: list[HorseServiceEntity]
    ) -> list[HorseServiceEntity]:
        self.calls.append(("bulk_create", entities))
        self._fail_if_needed("bulk_create")
        for entity in entities:
            self.add(entity)
        return entities

    async def bulk_delete(self, ids: Sequence[UUID]) -> None:
        self.calls.append(("bulk_delete", ids))
        self._fail_if_needed("bulk_delete")
        for id_ in ids:
            self.by_id.pop(id_, None)

    async def get_by_slug(self, slug: str) -> HorseServiceEntity | None:
        self.calls.append(("get_by_slug", slug))
        self._fail_if_needed("get_by_slug")
        return self.by_slug.get(slug)

    async def get_by_slug_or_id(
        self, slug_or_id: str | UUID
    ) -> HorseServiceEntity | None:
        self.calls.append(("get_by_slug_or_id", slug_or_id))
        self._fail_if_needed("get_by_slug_or_id")
        if isinstance(slug_or_id, UUID):
            return self.by_id.get(slug_or_id)
        return self.by_slug.get(slug_or_id)

    async def find_by_slug(self, slug: str) -> HorseServiceEntity | None:
        self.calls.append(("find_by_slug", slug))
        self._fail_if_needed("find_by_slug")
        return self.by_slug.get(slug)

    async def find_by_name(self, name: str) -> HorseServiceEntity | None:
        self.calls.append(("find_by_name", name))
        self._fail_if_needed("find_by_name")
        return self.by_name.get(name)

    async def create(self, entity: HorseServiceEntity) -> HorseServiceEntity:
        self.calls.append(("create", entity))
        self._fail_if_needed("create")
        self.add(entity)
        return entity

    async def update(self, entity: HorseServiceEntity) -> HorseServiceEntity:
        self.calls.append(("update", entity))
        self._fail_if_needed("update")
        self.add(entity)
        return entity

    async def delete(self, id: UUID) -> None:
        self.calls.append(("delete", id))
        self._fail_if_needed("delete")
        entity = self.by_id.pop(id, None)
        if entity is not None:
            assert entity.slug is not None
            self.by_slug.pop(entity.slug, None)
            self.by_name.pop(entity.name, None)

    async def get_filtered(
        self,
        *,
        name: str | None = None,
        slug: str | None = None,
        description: str | None = None,
        page_data: str | None = None,
        sort: list[str] | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[list[HorseServiceEntity], int]:
        self.calls.append(
            (
                "get_filtered",
                {
                    "name": name,
                    "slug": slug,
                    "description": description,
                    "page_data": page_data,
                    "sort": sort,
                    "limit": limit,
                    "offset": offset,
                },
            )
        )
        self._fail_if_needed("get_filtered")
        return self.filtered_result


def make_horse_service(**overrides: Any) -> HorseServiceEntity:
    data = {
        "name": "Подковка",
        "slug": "podkovka",
        "description": "Базовая услуга",
        "price": 1000,
        "price_formatter": PriceFormatter.equal,
        "page_data": "<div>Base</div>",
    }
    data.update(overrides)
    return HorseServiceEntity(**data)


def make_service() -> tuple[HorseServiceService, FakeHorseServiceRepository]:
    repo = FakeHorseServiceRepository()
    return HorseServiceService(horse_service_repository=cast(Any, repo)), repo


async def test_parse_slug_or_id_uc01_and_uc12() -> None:
    service, _ = make_service()
    entity_id = uuid4()

    assert service._parse_slug_or_id(str(entity_id)) == entity_id
    assert service._parse_slug_or_id("not-a-uuid") == "not-a-uuid"


async def test_ensure_unique_slug_uc14_suffix_loop_and_uc22_order() -> None:
    service, repo = make_service()
    repo.add(make_horse_service(slug="podkovka"))
    repo.add(make_horse_service(name="Other", slug="podkovka-1"))

    assert (
        await service._ensure_unique_slug(
            "podkovka", equestrian_context=TEST_EQUESTRIAN_CONTEXT
        )
        == "podkovka-2"
    )
    assert repo.calls == [
        ("find_by_slug", "podkovka"),
        ("find_by_slug", "podkovka-1"),
        ("find_by_slug", "podkovka-2"),
    ]


async def test_ensure_unique_slug_uc15_self_exclusion_returns_same_slug() -> None:
    service, repo = make_service()
    entity = repo.add(make_horse_service())

    assert (
        await service._ensure_unique_slug(
            "podkovka", exclude_id=entity.id, equestrian_context=TEST_EQUESTRIAN_CONTEXT
        )
        == "podkovka"
    )


async def test_create_uc01_generates_slug_and_default_page_data() -> None:
    service, repo = make_service()

    entity = await service.create(
        HorseServiceCreateDto(name="Чистка копыт", price=500),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert entity.slug == "chistka-kopyt"
    assert entity.page_data == "<div></div>"
    assert [name for name, _ in repo.calls] == [
        "find_by_name",
        "find_by_slug",
        "create",
    ]


async def test_create_uc03_trims_fields_and_keeps_price_sortable() -> None:
    service, _ = make_service()

    entity = await service.create(
        HorseServiceCreateDto(
            name="  Тренировка  ",
            slug=" train ",
            description=" base ",
            price=1500,
            page_data=" <div>Page</div> ",
        ),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert entity.name == "Тренировка"
    assert entity.slug == "train"
    assert entity.description == "base"
    assert entity.page_data == "<div>Page</div>"
    assert entity.price == 1500


async def test_create_uc14_duplicate_name_rejected_before_create() -> None:
    service, repo = make_service()
    repo.add(make_horse_service(name="Подковка"))

    with pytest.raises(ClientError):
        await service.create(
            HorseServiceCreateDto(name="Подковка", price=1200),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )

    assert [name for name, _ in repo.calls] == ["find_by_name"]


async def test_create_uc21_repository_failure_propagates() -> None:
    service, repo = make_service()
    repo.fail_on.add("create")

    with pytest.raises(RepositoryError):
        await service.create(
            HorseServiceCreateDto(name="Массаж", price=1200),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )


@pytest.mark.parametrize(
    "payload",
    [
        HorseServiceCreateDto(name=" ", price=100),
        HorseServiceCreateDto(name="Good", price=-1),
    ],
)
async def test_create_uc05_uc09_invalid_business_values_raise_client_error(
    payload: HorseServiceCreateDto,
) -> None:
    service, _ = make_service()

    with pytest.raises(ClientError):
        await service.create(payload, equestrian_context=TEST_EQUESTRIAN_CONTEXT)


async def test_create_empty_slug_auto_generates_from_name() -> None:
    service, _ = make_service()

    entity = await service.create(
        HorseServiceCreateDto(name="Good", slug=" ", price=100),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )
    assert entity.slug == "good"


async def test_update_uc01_partial_name_regenerates_slug() -> None:
    service, repo = make_service()
    current = repo.add(make_horse_service(name="Старое", slug="old"))

    updated = await service.update(
        str(current.id),
        HorseServiceUpdateDto(name="Новое"),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert updated.name == "Новое"
    assert updated.slug == "novoe"
    assert [name for name, _ in repo.calls] == [
        "get_by_slug_or_id",
        "find_by_name",
        "find_by_slug",
        "update",
    ]


async def test_update_uc13_not_found_raises_client_error() -> None:
    service, repo = make_service()

    with pytest.raises(ClientError):
        await service.update(
            "missing",
            HorseServiceUpdateDto(name="Новая"),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )
    assert [name for name, _ in repo.calls] == ["get_by_slug_or_id"]


async def test_update_uc14_duplicate_name_rejected_with_self_exclusion() -> None:
    service, repo = make_service()
    current = repo.add(make_horse_service(name="Current", slug="current"))
    repo.add(make_horse_service(name="Taken", slug="taken"))

    with pytest.raises(ClientError):
        await service.update(
            str(current.id),
            HorseServiceUpdateDto(name="Taken"),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )

    assert [name for name, _ in repo.calls] == ["get_by_slug_or_id", "find_by_name"]


async def test_update_uc20_empty_payload_explicitly_rejected() -> None:
    service, repo = make_service()
    current = repo.add(make_horse_service())

    with pytest.raises(ClientError):
        await service.update(
            str(current.id),
            HorseServiceUpdateDto(),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )

    assert [name for name, _ in repo.calls] == ["get_by_slug_or_id"]


async def test_update_uc19_changes_only_explicit_fields() -> None:
    service, repo = make_service()
    repo.add(make_horse_service(description="Old", page_data="<div>Old</div>"))

    updated = await service.update(
        "podkovka",
        HorseServiceUpdateDto(description="New", price=2000),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert updated.description == "New"
    assert updated.price == 2000
    assert updated.page_data == "<div>Old</div>"


async def test_update_uc21_repository_failure_from_update_propagates() -> None:
    service, repo = make_service()
    current = repo.add(make_horse_service(name="Старое", slug="old"))
    repo.fail_on.add("update")

    with pytest.raises(RepositoryError):
        await service.update(
            str(current.id),
            HorseServiceUpdateDto(name="Новое"),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )


async def test_get_by_slug_or_id_uc01_and_uc13() -> None:
    service, repo = make_service()
    entity = repo.add(make_horse_service())

    assert (
        await service.get_by_slug_or_id(
            "podkovka", equestrian_context=TEST_EQUESTRIAN_CONTEXT
        )
        == entity
    )
    assert (
        await service.get_by_slug_or_id(
            str(entity.id), equestrian_context=TEST_EQUESTRIAN_CONTEXT
        )
        == entity
    )

    with pytest.raises(ClientError):
        await service.get_by_slug_or_id(
            "missing", equestrian_context=TEST_EQUESTRIAN_CONTEXT
        )


async def test_get_by_slug_or_id_uc21_repository_failure_propagates() -> None:
    service, repo = make_service()
    repo.fail_on.add("get_by_slug_or_id")

    with pytest.raises(RepositoryError):
        await service.get_by_slug_or_id(
            "podkovka", equestrian_context=TEST_EQUESTRIAN_CONTEXT
        )


async def test_delete_uc01_and_uc13() -> None:
    service, repo = make_service()
    entity = repo.add(make_horse_service())

    await service.delete("podkovka", equestrian_context=TEST_EQUESTRIAN_CONTEXT)
    assert entity.id not in repo.by_id

    with pytest.raises(ClientError):
        await service.delete("missing", equestrian_context=TEST_EQUESTRIAN_CONTEXT)


async def test_delete_uc21_repository_failure_on_delete_propagates() -> None:
    service, repo = make_service()
    repo.add(make_horse_service())
    repo.fail_on.add("delete")

    with pytest.raises(RepositoryError):
        await service.delete("podkovka", equestrian_context=TEST_EQUESTRIAN_CONTEXT)


async def test_get_filtered_uc01_uc25_uc26_uc27_passes_price_sort_and_filters() -> None:
    service, repo = make_service()
    result = [make_horse_service()]
    repo.filtered_result = (result, 10)

    entities, total = await service.get_filtered(
        name="под",
        slug="pod",
        description="баз",
        page_data="div",
        sort=["price", "-name"],
        limit=5,
        offset=10,
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert entities == result
    assert total == 10
    assert repo.calls == [
        (
            "get_filtered",
            {
                "name": "под",
                "slug": "pod",
                "description": "баз",
                "page_data": "div",
                "sort": ["price", "-name"],
                "limit": 5,
                "offset": 10,
            },
        )
    ]


async def test_get_filtered_uc29_invalid_sort_rejected_before_repository_call() -> None:
    service, repo = make_service()

    with pytest.raises(ClientError):
        await service.get_filtered(
            sort=cast(Any, ["invalid"]),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )
    assert repo.calls == []


async def test_get_filtered_uc09_negative_pagination_rejected() -> None:
    service, repo = make_service()

    with pytest.raises(ClientError):
        await service.get_filtered(limit=-1, equestrian_context=TEST_EQUESTRIAN_CONTEXT)
    with pytest.raises(ClientError):
        await service.get_filtered(
            offset=-1, equestrian_context=TEST_EQUESTRIAN_CONTEXT
        )
    assert repo.calls == []


async def test_get_filtered_uc21_repository_failure_propagates() -> None:
    service, repo = make_service()
    repo.fail_on.add("get_filtered")

    with pytest.raises(RepositoryError):
        await service.get_filtered(
            sort=["price"], equestrian_context=TEST_EQUESTRIAN_CONTEXT
        )


async def test_horse_service_uc30_architecture_boundary_has_no_fastapi_dependency() -> (
    None
):
    import core.services.horse_service as horse_service_module

    assert not hasattr(horse_service_module, "HTTPException")


async def test_create_null_slug_auto_generates_from_name() -> None:
    service, _ = make_service()

    entity = await service.create(
        HorseServiceCreateDto(name="Разведение", price=500),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )
    assert entity.slug == "razvedenie"


async def test_create_empty_description_stores_none() -> None:
    service, _ = make_service()

    entity = await service.create(
        HorseServiceCreateDto(name="Тест", price=100, description=""),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )
    assert entity.description is None


async def test_create_null_description_stores_none() -> None:
    service, _ = make_service()

    entity = await service.create(
        HorseServiceCreateDto(name="Тест2", price=100, description=None),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )
    assert entity.description is None


async def test_update_empty_slug_regenerates_from_name() -> None:
    service, repo = make_service()
    current = repo.add(make_horse_service(name="Старое", slug="old"))

    updated = await service.update(
        str(current.id),
        HorseServiceUpdateDto(slug=" "),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )
    assert updated.slug == "staroe"


async def test_update_empty_description_stores_none() -> None:
    service, repo = make_service()
    repo.add(make_horse_service(description="Old description"))

    updated = await service.update(
        "podkovka",
        HorseServiceUpdateDto(description=""),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )
    assert updated.description is None
