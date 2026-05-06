from __future__ import annotations

from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from core.entities.prices import PriceGroup
from core.exceptions.base import ClientError
from core.schemas.prices import PriceGroupCreateDto, PriceGroupUpdateDto
from core.services.prices import PriceGroupService

pytestmark = pytest.mark.asyncio


class RepositoryError(Exception):
    pass


class FakePriceGroupRepository:
    def __init__(self) -> None:
        self.by_id: dict[UUID, PriceGroup] = {}
        self.by_name: dict[str, PriceGroup] = {}
        self.calls: list[tuple[str, Any]] = []
        self.filtered_result: tuple[list[PriceGroup], int] = ([], 0)
        self.fail_on: set[str] = set()

    def add(self, group: PriceGroup) -> PriceGroup:
        self.by_id[group.id] = group
        self.by_name[group.name] = group
        return group

    def _fail_if_needed(self, method: str) -> None:
        if method in self.fail_on:
            raise RepositoryError(method)

    async def find_by_name(self, name: str) -> PriceGroup | None:
        self.calls.append(("find_by_name", name))
        self._fail_if_needed("find_by_name")
        return self.by_name.get(name)

    async def get_by_id(self, id: UUID) -> PriceGroup | None:
        self.calls.append(("get_by_id", id))
        self._fail_if_needed("get_by_id")
        return self.by_id.get(id)

    async def get_by_ids(self, ids: list[UUID]) -> dict[UUID, PriceGroup]:
        self.calls.append(("get_by_ids", ids))
        self._fail_if_needed("get_by_ids")
        return {id_: self.by_id[id_] for id_ in ids if id_ in self.by_id}

    async def create(self, entity: PriceGroup) -> PriceGroup:
        self.calls.append(("create", entity))
        self._fail_if_needed("create")
        return self.add(entity)

    async def update(self, entity: PriceGroup) -> PriceGroup:
        self.calls.append(("update", entity))
        self._fail_if_needed("update")
        old = self.by_id.get(entity.id)
        if old is not None:
            self.by_name.pop(old.name, None)
        return self.add(entity)

    async def delete(self, id: UUID) -> None:
        self.calls.append(("delete", id))
        self._fail_if_needed("delete")
        group = self.by_id.pop(id, None)
        if group is not None:
            self.by_name.pop(group.name, None)

    async def get_filtered(
        self,
        *,
        name: str | None = None,
        description: str | None = None,
        sort: list[str] | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[list[PriceGroup], int]:
        self.calls.append(
            (
                "get_filtered",
                {
                    "name": name,
                    "description": description,
                    "sort": sort,
                    "limit": limit,
                    "offset": offset,
                },
            )
        )
        self._fail_if_needed("get_filtered")
        return self.filtered_result


def make_group(**overrides: Any) -> PriceGroup:
    data = {"name": "Group", "description": "Desc"}
    data.update(overrides)
    return PriceGroup(**data)


def make_service() -> tuple[PriceGroupService, FakePriceGroupRepository]:
    repo = FakePriceGroupRepository()
    return PriceGroupService(price_group_repository=cast(Any, repo)), repo


async def test_ensure_unique_name_uc01_uc15_allows_missing_and_self() -> None:
    service, repo = make_service()
    group = repo.add(make_group(name="Existing"))

    assert await service._ensure_unique_name("New") == "New"
    assert (
        await service._ensure_unique_name("Existing", exclude_id=group.id) == "Existing"
    )


async def test_ensure_unique_name_uc14_rejects_duplicate() -> None:
    service, repo = make_service()
    repo.add(make_group(name="Existing"))

    with pytest.raises(ClientError):
        await service._ensure_unique_name("Existing")


async def test_create_uc01_uc02_uc07_trims_and_creates_group() -> None:
    service, repo = make_service()

    created = await service.create(
        PriceGroupCreateDto(name="  Конюшня  ", description="  Акции  ")
    )

    assert created.name == "Конюшня"
    assert created.description == "Акции"
    assert [name for name, _ in repo.calls] == ["find_by_name", "create"]


async def test_create_uc05_uc06_rejects_empty_name_before_repository_write() -> None:
    service, repo = make_service()

    with pytest.raises(ClientError):
        await service.create(PriceGroupCreateDto(name="   "))

    assert repo.calls == []


async def test_create_uc10_uc11_rejects_too_long_name() -> None:
    service, repo = make_service()

    with pytest.raises(ClientError):
        await service.create(PriceGroupCreateDto(name="x" * 64))

    assert repo.calls == []


async def test_create_uc14_duplicate_name_is_client_error() -> None:
    service, repo = make_service()
    repo.add(make_group(name="Existing"))

    with pytest.raises(ClientError):
        await service.create(PriceGroupCreateDto(name="Existing"))

    assert [name for name, _ in repo.calls] == ["find_by_name"]


async def test_update_uc01_uc19_updates_only_provided_fields() -> None:
    service, repo = make_service()
    group = repo.add(make_group(name="Old", description="Old desc"))

    updated = await service.update(
        group.id, PriceGroupUpdateDto(description=" New desc ")
    )

    assert updated.name == "Old"
    assert updated.description == "New desc"


async def test_update_uc13_not_found_is_client_error() -> None:
    service, _ = make_service()

    with pytest.raises(ClientError):
        await service.update(uuid4(), PriceGroupUpdateDto(name="New"))


async def test_update_uc20_empty_update_is_client_error_without_write() -> None:
    service, repo = make_service()
    group = repo.add(make_group())

    with pytest.raises(ClientError):
        await service.update(group.id, PriceGroupUpdateDto())

    assert [name for name, _ in repo.calls] == ["get_by_id"]


async def test_update_uc14_uc15_rejects_other_duplicate_allows_self() -> None:
    service, repo = make_service()
    current = repo.add(make_group(name="Current"))
    repo.add(make_group(name="Other"))

    updated = await service.update(current.id, PriceGroupUpdateDto(name="Current"))
    assert updated.name == "Current"

    with pytest.raises(ClientError):
        await service.update(current.id, PriceGroupUpdateDto(name="Other"))


async def test_get_by_id_uc13_service_level_not_found_contract() -> None:
    service, _ = make_service()

    with pytest.raises(ClientError):
        await service.get_by_id(uuid4())


async def test_delete_uc01_uc13_deletes_existing_and_rejects_missing() -> None:
    service, repo = make_service()
    group = repo.add(make_group())

    await service.delete(group.id)
    assert group.id not in repo.by_id

    with pytest.raises(ClientError):
        await service.delete(group.id)


async def test_get_filtered_uc26_uc27_passes_filtering_and_pagination() -> None:
    service, repo = make_service()
    groups = [make_group(name="A"), make_group(name="B")]
    repo.filtered_result = (groups, 2)

    entities, total = await service.get_filtered(
        name="A",
        description="desc",
        sort=["name", "-name"],
        limit=10,
        offset=20,
    )

    assert entities == groups
    assert total == 2
    assert repo.calls[-1][0] == "get_filtered"


async def test_price_group_service_uc21_bubbles_repository_failure() -> None:
    service, repo = make_service()
    repo.fail_on.add("find_by_name")

    with pytest.raises(RepositoryError):
        await service.create(PriceGroupCreateDto(name="New"))


async def test_price_group_service_uc30_has_no_fastapi_or_settings_dependency() -> None:
    import inspect

    import core.services.prices as prices_module

    module_source = inspect.getsource(prices_module)
    assert "fastapi" not in module_source
    assert "from settings import settings" not in module_source
