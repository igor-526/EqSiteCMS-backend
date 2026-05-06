from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from core.entities.breeds import Breed
from core.exceptions.base import ClientError
from core.schemas.breeds import BreedCreateDto, BreedUpdateDto
from core.services.breeds import BreedService

pytestmark = pytest.mark.asyncio


class RepositoryError(Exception):
    pass


class FakeBreedRepository:
    def __init__(self) -> None:
        self.by_id: dict[UUID, Breed] = {}
        self.by_slug: dict[str, Breed] = {}
        self.by_name: dict[str, Breed] = {}
        self.calls: list[tuple[str, Any]] = []
        self.filtered_result: tuple[list[Breed], int] = ([], 0)
        self.fail_on: set[str] = set()

    def add(self, breed: Breed) -> Breed:
        self.by_id[breed.id] = breed
        self.by_slug[breed.slug or ""] = breed
        self.by_name[breed.name] = breed
        return breed

    def _fail_if_needed(self, method: str) -> None:
        if method in self.fail_on:
            raise RepositoryError(method)

    async def get_by_id(self, id: UUID) -> Breed | None:
        self.calls.append(("get_by_id", id))
        self._fail_if_needed("get_by_id")
        return self.by_id.get(id)

    async def get_all(
        self, *, limit: int | None = None, offset: int | None = None
    ) -> list[Breed]:
        self.calls.append(("get_all", {"limit": limit, "offset": offset}))
        self._fail_if_needed("get_all")
        return list(self.by_id.values())

    async def get_by_ids(self, ids: list[UUID]) -> dict[UUID, Breed]:
        self.calls.append(("get_by_ids", ids))
        self._fail_if_needed("get_by_ids")
        return {id_: self.by_id[id_] for id_ in ids if id_ in self.by_id}

    async def bulk_create(self, entities: list[Breed]) -> list[Breed]:
        self.calls.append(("bulk_create", entities))
        self._fail_if_needed("bulk_create")
        for entity in entities:
            self.add(entity)
        return entities

    async def bulk_delete(self, ids: list[UUID]) -> None:
        self.calls.append(("bulk_delete", ids))
        self._fail_if_needed("bulk_delete")
        for id_ in ids:
            self.by_id.pop(id_, None)

    async def get_by_slug(self, slug: str) -> Breed | None:
        self.calls.append(("get_by_slug", slug))
        self._fail_if_needed("get_by_slug")
        return self.by_slug.get(slug)

    async def get_by_slug_or_id(self, slug_or_id: str | UUID) -> Breed | None:
        self.calls.append(("get_by_slug_or_id", slug_or_id))
        self._fail_if_needed("get_by_slug_or_id")
        if isinstance(slug_or_id, UUID):
            return self.by_id.get(slug_or_id)
        return self.by_slug.get(slug_or_id)

    async def find_by_slug(self, slug: str) -> Breed | None:
        self.calls.append(("find_by_slug", slug))
        self._fail_if_needed("find_by_slug")
        return self.by_slug.get(slug)

    async def find_by_name(self, name: str) -> Breed | None:
        self.calls.append(("find_by_name", name))
        self._fail_if_needed("find_by_name")
        return self.by_name.get(name)

    async def create(self, entity: Breed) -> Breed:
        self.calls.append(("create", entity))
        self._fail_if_needed("create")
        self.add(entity)
        return entity

    async def update(self, entity: Breed) -> Breed:
        self.calls.append(("update", entity))
        self._fail_if_needed("update")
        self.add(entity)
        return entity

    async def delete(self, id: UUID) -> None:
        self.calls.append(("delete", id))
        self._fail_if_needed("delete")
        breed = self.by_id.pop(id, None)
        if breed is not None:
            self.by_slug.pop(breed.slug or "", None)
            self.by_name.pop(breed.name, None)

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
    ) -> tuple[list[Breed], int]:
        filters = {
            "name": name,
            "slug": slug,
            "description": description,
            "page_data": page_data,
            "sort": sort,
            "limit": limit,
            "offset": offset,
        }
        self.calls.append(("get_filtered", filters))
        self._fail_if_needed("get_filtered")
        return self.filtered_result


def make_breed(**overrides: Any) -> Breed:
    data = {
        "name": "Akhal-Teke",
        "slug": "akhal-teke",
        "short_name": "AT",
        "description": "Fast horse",
        "page_data": "<div>Fast horse</div>",
    }
    data.update(overrides)
    return Breed(**data)


def make_service() -> tuple[BreedService, FakeBreedRepository]:
    repo = FakeBreedRepository()
    return BreedService(breed_repository=cast(Any, repo)), repo


def assert_raises_client_error(call: Callable[[], Any]) -> None:
    with pytest.raises(ClientError):
        call()


async def test_parse_slug_or_id_uc01_uuid_and_uc12_malformed_slug_are_deterministic() -> (
    None
):
    service, _ = make_service()
    breed_id = uuid4()

    assert service._parse_slug_or_id(str(breed_id)) == breed_id
    assert service._parse_slug_or_id("not-a-uuid") == "not-a-uuid"
    assert service._parse_slug_or_id(" Жеребец ") == " Жеребец "


async def test_ensure_unique_slug_uc01_returns_free_slug() -> None:
    service, repo = make_service()

    assert await service._ensure_unique_slug("arabian") == "arabian"
    assert repo.calls == [("find_by_slug", "arabian")]


async def test_ensure_unique_slug_uc14_suffix_loop_and_uc22_order() -> None:
    service, repo = make_service()
    repo.add(make_breed(slug="arabian"))
    repo.add(make_breed(name="Other", slug="arabian-1"))

    assert await service._ensure_unique_slug("arabian") == "arabian-2"
    assert repo.calls == [
        ("find_by_slug", "arabian"),
        ("find_by_slug", "arabian-1"),
        ("find_by_slug", "arabian-2"),
    ]


async def test_ensure_unique_slug_uc15_self_exclusion_returns_existing_slug() -> None:
    service, repo = make_service()
    breed = repo.add(make_breed(slug="arabian"))

    assert (
        await service._ensure_unique_slug("arabian", exclude_id=breed.id) == "arabian"
    )


async def test_ensure_unique_slug_uc21_repository_failure_propagates_without_side_effects() -> (
    None
):
    service, repo = make_service()
    repo.fail_on.add("find_by_slug")

    with pytest.raises(RepositoryError):
        await service._ensure_unique_slug("arabian")
    assert [name for name, _ in repo.calls] == ["find_by_slug"]


async def test_create_uc01_minimal_input_generates_slug_and_default_page_data() -> None:
    service, repo = make_service()

    breed = await service.create(BreedCreateDto(name="Арабская"))

    assert breed.name == "Арабская"
    assert breed.slug == "arabskaya"
    assert breed.page_data == "<div></div>"
    assert [name for name, _ in repo.calls] == [
        "find_by_name",
        "find_by_slug",
        "create",
    ]


async def test_create_uc03_full_input_preserves_normalized_fields() -> None:
    service, _ = make_service()

    breed = await service.create(
        BreedCreateDto(
            name="  Arabian  ",
            short_name=" AR ",
            slug=" arabian ",
            description=" fast ",
            page_data=" <div>Page</div> ",
        )
    )

    assert breed.name == "Arabian"
    assert breed.short_name == "AR"
    assert breed.slug == "arabian"
    assert breed.description == "fast"
    assert breed.page_data == "<div>Page</div>"


async def test_create_uc05_uc06_empty_or_whitespace_business_values_are_client_errors() -> (
    None
):
    service, repo = make_service()

    with pytest.raises(ClientError):
        await service.create(BreedCreateDto(name=" "))
    with pytest.raises(ClientError):
        await service.create(BreedCreateDto(name="Arabian", slug=""))
    assert repo.calls == []


async def test_create_uc10_uc11_length_boundaries_are_enforced() -> None:
    service, _ = make_service()

    accepted = await service.create(BreedCreateDto(name="a" * 63))
    assert accepted.name == "a" * 63

    with pytest.raises(ClientError):
        await service.create(BreedCreateDto(name="a" * 64))


async def test_create_uc14_duplicate_name_rejects_before_slug_and_create() -> None:
    service, repo = make_service()
    repo.add(make_breed(name="Arabian"))

    with pytest.raises(ClientError):
        await service.create(BreedCreateDto(name="Arabian"))

    assert [name for name, _ in repo.calls] == ["find_by_name"]


async def test_create_uc21_repository_create_failure_leaves_fake_without_entity() -> (
    None
):
    service, repo = make_service()
    repo.fail_on.add("create")

    with pytest.raises(RepositoryError):
        await service.create(BreedCreateDto(name="Arabian"))

    assert "Arabian" not in repo.by_name


async def test_create_uc24_retry_after_slug_conflict_gets_next_suffix() -> None:
    service, repo = make_service()
    repo.add(make_breed(name="Existing", slug="arabian"))

    first = await service.create(BreedCreateDto(name="Arabian"))
    second = await service.create(BreedCreateDto(name="Arabian Copy", slug="arabian"))

    assert first.slug == "arabian-1"
    assert second.slug == "arabian-2"


async def test_update_uc01_partial_name_regenerates_slug() -> None:
    service, repo = make_service()
    breed = repo.add(make_breed(name="Old", slug="old"))

    updated = await service.update(str(breed.id), BreedUpdateDto(name="Новая"))

    assert updated.name == "Новая"
    assert updated.slug == "novaya"
    assert [name for name, _ in repo.calls] == [
        "get_by_slug_or_id",
        "find_by_name",
        "find_by_slug",
        "update",
    ]


async def test_update_uc13_not_found_is_client_error() -> None:
    service, repo = make_service()

    with pytest.raises(ClientError):
        await service.update("missing", BreedUpdateDto(name="New"))
    assert [name for name, _ in repo.calls] == ["get_by_slug_or_id"]


async def test_update_uc14_duplicate_name_rejects_without_update() -> None:
    service, repo = make_service()
    current = repo.add(make_breed(name="Current", slug="current"))
    repo.add(make_breed(name="Taken", slug="taken"))

    with pytest.raises(ClientError):
        await service.update(str(current.id), BreedUpdateDto(name="Taken"))

    assert [name for name, _ in repo.calls] == ["get_by_slug_or_id", "find_by_name"]


async def test_update_uc15_self_exclusion_allows_same_name_and_slug() -> None:
    service, repo = make_service()
    current = repo.add(make_breed(name="Current", slug="current"))

    updated = await service.update(
        "current", BreedUpdateDto(name="Current", slug="current")
    )

    assert updated.id == current.id
    assert updated.name == "Current"
    assert updated.slug == "current"


async def test_update_uc19_changes_only_explicit_fields() -> None:
    service, repo = make_service()
    repo.add(make_breed(description="Old", page_data="<div>Old</div>"))

    updated = await service.update("akhal-teke", BreedUpdateDto(description="New"))

    assert updated.description == "New"
    assert updated.page_data == "<div>Old</div>"
    assert updated.name == "Akhal-Teke"


async def test_update_uc20_empty_payload_is_client_error() -> None:
    service, repo = make_service()
    current = repo.add(make_breed())

    with pytest.raises(ClientError):
        await service.update(str(current.id), BreedUpdateDto())

    assert [name for name, _ in repo.calls] == ["get_by_slug_or_id"]


async def test_update_uc21_repository_update_failure_does_not_delete_entity() -> None:
    service, repo = make_service()
    current = repo.add(make_breed())
    repo.fail_on.add("update")

    with pytest.raises(RepositoryError):
        await service.update(str(current.id), BreedUpdateDto(description="New"))

    assert current.id in repo.by_id


async def test_update_uc29_business_validation_uses_client_error() -> None:
    service, repo = make_service()
    repo.add(make_breed())

    with pytest.raises(ClientError):
        await service.update("akhal-teke", BreedUpdateDto(slug=" "))


async def test_get_by_slug_or_id_uc01_returns_breed_by_slug_and_uuid() -> None:
    service, repo = make_service()
    breed = repo.add(make_breed())

    assert await service.get_by_slug_or_id("akhal-teke") == breed
    assert await service.get_by_slug_or_id(str(breed.id)) == breed


async def test_get_by_slug_or_id_uc13_not_found_raises_client_error() -> None:
    service, _ = make_service()

    with pytest.raises(ClientError):
        await service.get_by_slug_or_id("missing")


async def test_get_by_slug_or_id_uc21_repository_failure_propagates() -> None:
    service, repo = make_service()
    repo.fail_on.add("get_by_slug_or_id")

    with pytest.raises(RepositoryError):
        await service.get_by_slug_or_id("akhal-teke")


async def test_delete_uc01_deletes_existing_breed_by_slug() -> None:
    service, repo = make_service()
    breed = repo.add(make_breed())

    await service.delete("akhal-teke")

    assert breed.id not in repo.by_id
    assert [name for name, _ in repo.calls] == ["get_by_slug_or_id", "delete"]


async def test_delete_uc13_not_found_raises_client_error_without_delete() -> None:
    service, repo = make_service()

    with pytest.raises(ClientError):
        await service.delete("missing")

    assert [name for name, _ in repo.calls] == ["get_by_slug_or_id"]


async def test_delete_uc21_repository_delete_failure_propagates() -> None:
    service, repo = make_service()
    repo.add(make_breed())
    repo.fail_on.add("delete")

    with pytest.raises(RepositoryError):
        await service.delete("akhal-teke")


async def test_get_filtered_uc01_uc25_uc26_uc27_passes_contract_through() -> None:
    service, repo = make_service()
    result = [make_breed()]
    repo.filtered_result = (result, 10)

    entities, total = await service.get_filtered(
        name="Arab",
        slug="arab",
        description="fast",
        page_data="page",
        sort=["name", "-slug"],
        limit=5,
        offset=10,
    )

    assert entities == result
    assert total == 10
    assert repo.calls == [
        (
            "get_filtered",
            {
                "name": "Arab",
                "slug": "arab",
                "description": "fast",
                "page_data": "page",
                "sort": ["name", "-slug"],
                "limit": 5,
                "offset": 10,
            },
        )
    ]


async def test_get_filtered_uc02_omitted_optional_defaults_are_passed_as_none() -> None:
    service, repo = make_service()

    assert await service.get_filtered() == ([], 0)
    assert repo.calls == [
        (
            "get_filtered",
            {
                "name": None,
                "slug": None,
                "description": None,
                "page_data": None,
                "sort": None,
                "limit": None,
                "offset": None,
            },
        )
    ]


async def test_get_filtered_uc21_repository_failure_propagates() -> None:
    service, repo = make_service()
    repo.fail_on.add("get_filtered")

    with pytest.raises(RepositoryError):
        await service.get_filtered(limit=1)


async def test_breed_service_uc30_architecture_boundary_has_no_fastapi_dependency() -> (
    None
):
    import core.services.breeds as breeds_module

    assert not hasattr(breeds_module, "HTTPException")
    assert_raises_client_error(
        lambda: BreedService(cast(Any, FakeBreedRepository()))._validate_required_text(
            field="Название породы",
            value=" ",
            max_length=63,
        )
    )
