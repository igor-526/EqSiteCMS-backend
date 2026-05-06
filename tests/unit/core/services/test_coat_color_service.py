from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from core.entities.coat_color import CoatColor
from core.exceptions.base import ClientError
from core.schemas.coat_color import CoatColorCreateDto, CoatColorUpdateDto
from core.services.coat_color import CoatColorService

pytestmark = pytest.mark.asyncio


class RepositoryError(Exception):
    pass


class FakeCoatColorRepository:
    def __init__(self) -> None:
        self.by_id: dict[UUID, CoatColor] = {}
        self.by_slug: dict[str, CoatColor] = {}
        self.by_name: dict[str, CoatColor] = {}
        self.calls: list[tuple[str, Any]] = []
        self.filtered_result: tuple[list[CoatColor], int] = ([], 0)
        self.fail_on: set[str] = set()

    def add(self, coat_color: CoatColor) -> CoatColor:
        self.by_id[coat_color.id] = coat_color
        self.by_slug[coat_color.slug or ""] = coat_color
        self.by_name[coat_color.name] = coat_color
        return coat_color

    def _fail_if_needed(self, method: str) -> None:
        if method in self.fail_on:
            raise RepositoryError(method)

    async def get_by_id(self, id: UUID) -> CoatColor | None:
        self.calls.append(("get_by_id", id))
        self._fail_if_needed("get_by_id")
        return self.by_id.get(id)

    async def get_all(
        self, *, limit: int | None = None, offset: int | None = None
    ) -> list[CoatColor]:
        self.calls.append(("get_all", {"limit": limit, "offset": offset}))
        self._fail_if_needed("get_all")
        return list(self.by_id.values())

    async def get_by_ids(self, ids: list[UUID]) -> dict[UUID, CoatColor]:
        self.calls.append(("get_by_ids", ids))
        self._fail_if_needed("get_by_ids")
        return {id_: self.by_id[id_] for id_ in ids if id_ in self.by_id}

    async def bulk_create(self, entities: list[CoatColor]) -> list[CoatColor]:
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

    async def get_by_slug(self, slug: str) -> CoatColor | None:
        self.calls.append(("get_by_slug", slug))
        self._fail_if_needed("get_by_slug")
        return self.by_slug.get(slug)

    async def get_by_slug_or_id(self, slug_or_id: str | UUID) -> CoatColor | None:
        self.calls.append(("get_by_slug_or_id", slug_or_id))
        self._fail_if_needed("get_by_slug_or_id")
        if isinstance(slug_or_id, UUID):
            return self.by_id.get(slug_or_id)
        return self.by_slug.get(slug_or_id)

    async def find_by_slug(self, slug: str) -> CoatColor | None:
        self.calls.append(("find_by_slug", slug))
        self._fail_if_needed("find_by_slug")
        return self.by_slug.get(slug)

    async def find_by_name(self, name: str) -> CoatColor | None:
        self.calls.append(("find_by_name", name))
        self._fail_if_needed("find_by_name")
        return self.by_name.get(name)

    async def create(self, entity: CoatColor) -> CoatColor:
        self.calls.append(("create", entity))
        self._fail_if_needed("create")
        self.add(entity)
        return entity

    async def update(self, entity: CoatColor) -> CoatColor:
        self.calls.append(("update", entity))
        self._fail_if_needed("update")
        self.add(entity)
        return entity

    async def delete(self, id: UUID) -> None:
        self.calls.append(("delete", id))
        self._fail_if_needed("delete")
        coat_color = self.by_id.pop(id, None)
        if coat_color is not None:
            self.by_slug.pop(coat_color.slug or "", None)
            self.by_name.pop(coat_color.name, None)

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
    ) -> tuple[list[CoatColor], int]:
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


def make_coat_color(**overrides: Any) -> CoatColor:
    data = {
        "name": "Bay",
        "slug": "bay",
        "short_name": "B",
        "description": "Brown coat with black points",
        "page_data": "<div>Bay coat</div>",
    }
    data.update(overrides)
    return CoatColor(**data)


def make_service() -> tuple[CoatColorService, FakeCoatColorRepository]:
    repo = FakeCoatColorRepository()
    return CoatColorService(coat_color_repository=cast(Any, repo)), repo


def assert_raises_client_error(call: Callable[[], Any]) -> None:
    with pytest.raises(ClientError):
        call()


async def test_parse_slug_or_id_uc01_uuid_and_uc12_malformed_slug_are_deterministic() -> (
    None
):
    service, _ = make_service()
    coat_color_id = uuid4()

    assert service._parse_slug_or_id(str(coat_color_id)) == coat_color_id
    assert service._parse_slug_or_id("not-a-uuid") == "not-a-uuid"
    assert service._parse_slug_or_id(" Гнедая ") == " Гнедая "


async def test_ensure_unique_slug_uc01_returns_free_slug() -> None:
    service, repo = make_service()

    assert await service._ensure_unique_slug("bay") == "bay"
    assert repo.calls == [("find_by_slug", "bay")]


async def test_ensure_unique_slug_uc14_suffix_loop_and_uc22_order() -> None:
    service, repo = make_service()
    repo.add(make_coat_color(slug="bay"))
    repo.add(make_coat_color(name="Other", slug="bay-1"))

    assert await service._ensure_unique_slug("bay") == "bay-2"
    assert repo.calls == [
        ("find_by_slug", "bay"),
        ("find_by_slug", "bay-1"),
        ("find_by_slug", "bay-2"),
    ]


async def test_ensure_unique_slug_uc15_self_exclusion_returns_existing_slug() -> None:
    service, repo = make_service()
    coat_color = repo.add(make_coat_color(slug="bay"))

    assert await service._ensure_unique_slug("bay", exclude_id=coat_color.id) == "bay"


async def test_ensure_unique_slug_uc21_repository_failure_propagates_without_side_effects() -> (
    None
):
    service, repo = make_service()
    repo.fail_on.add("find_by_slug")

    with pytest.raises(RepositoryError):
        await service._ensure_unique_slug("bay")
    assert [name for name, _ in repo.calls] == ["find_by_slug"]


async def test_create_uc01_minimal_input_generates_slug_and_default_page_data() -> None:
    service, repo = make_service()

    coat_color = await service.create(CoatColorCreateDto(name="Гнедая"))

    assert coat_color.name == "Гнедая"
    assert coat_color.slug == "gnedaya"
    assert coat_color.page_data == "<div></div>"
    assert [name for name, _ in repo.calls] == [
        "find_by_name",
        "find_by_slug",
        "create",
    ]


async def test_create_uc03_full_input_preserves_normalized_fields() -> None:
    service, repo = make_service()

    coat_color = await service.create(
        CoatColorCreateDto(
            name="  Bay  ",
            short_name=" B ",
            slug=" bay ",
            description=" common ",
            page_data=" <div>Page</div> ",
        )
    )

    assert coat_color.name == "Bay"
    assert coat_color.short_name == "B"
    assert coat_color.slug == "bay"
    assert coat_color.description == "common"
    assert coat_color.page_data == "<div>Page</div>"
    assert [name for name, _ in repo.calls] == [
        "find_by_name",
        "find_by_slug",
        "create",
    ]


async def test_create_uc05_uc06_empty_or_whitespace_business_values_are_client_errors() -> (
    None
):
    service, repo = make_service()

    with pytest.raises(ClientError):
        await service.create(CoatColorCreateDto(name=" "))
    with pytest.raises(ClientError):
        await service.create(CoatColorCreateDto(name="Bay", slug=""))
    assert repo.calls == []


async def test_create_uc10_uc11_length_boundaries_are_enforced() -> None:
    service, _ = make_service()

    accepted = await service.create(CoatColorCreateDto(name="a" * 63))
    assert accepted.name == "a" * 63

    with pytest.raises(ClientError):
        await service.create(CoatColorCreateDto(name="a" * 64))


async def test_create_uc14_duplicate_name_rejects_before_slug_and_create() -> None:
    service, repo = make_service()
    repo.add(make_coat_color(name="Bay"))

    with pytest.raises(ClientError):
        await service.create(CoatColorCreateDto(name="Bay"))

    assert [name for name, _ in repo.calls] == ["find_by_name"]


async def test_create_uc14_explicit_slug_collision_is_client_error() -> None:
    service, repo = make_service()
    repo.add(make_coat_color(name="Existing", slug="bay"))

    with pytest.raises(ClientError):
        await service.create(CoatColorCreateDto(name="New", slug="bay"))

    assert [name for name, _ in repo.calls] == ["find_by_name", "find_by_slug"]


async def test_create_uc21_repository_create_failure_leaves_fake_without_entity() -> (
    None
):
    service, repo = make_service()
    repo.fail_on.add("create")

    with pytest.raises(RepositoryError):
        await service.create(CoatColorCreateDto(name="Bay"))

    assert "Bay" not in repo.by_name


async def test_create_uc24_retry_generated_slug_conflict_gets_next_suffix() -> None:
    service, repo = make_service()
    repo.add(make_coat_color(name="Existing", slug="bay"))

    created = await service.create(CoatColorCreateDto(name="Bay Copy"))
    duplicate_generated = await service.create(CoatColorCreateDto(name="Bay"))

    assert created.slug == "bay-copy"
    assert duplicate_generated.slug == "bay-1"


async def test_update_uc01_partial_name_regenerates_slug() -> None:
    service, repo = make_service()
    coat_color = repo.add(make_coat_color(name="Old", slug="old"))

    updated = await service.update(str(coat_color.id), CoatColorUpdateDto(name="Рыжая"))

    assert updated.name == "Рыжая"
    assert updated.slug == "ryzhaya"
    assert [name for name, _ in repo.calls] == [
        "get_by_slug_or_id",
        "find_by_name",
        "find_by_slug",
        "update",
    ]


async def test_update_uc13_not_found_is_client_error() -> None:
    service, repo = make_service()

    with pytest.raises(ClientError):
        await service.update("missing", CoatColorUpdateDto(name="New"))
    assert [name for name, _ in repo.calls] == ["get_by_slug_or_id"]


async def test_update_uc14_duplicate_name_rejects_without_update() -> None:
    service, repo = make_service()
    current = repo.add(make_coat_color(name="Current", slug="current"))
    repo.add(make_coat_color(name="Taken", slug="taken"))

    with pytest.raises(ClientError):
        await service.update(str(current.id), CoatColorUpdateDto(name="Taken"))

    assert [name for name, _ in repo.calls] == ["get_by_slug_or_id", "find_by_name"]


async def test_update_uc14_explicit_slug_collision_rejects_without_update() -> None:
    service, repo = make_service()
    current = repo.add(make_coat_color(name="Current", slug="current"))
    repo.add(make_coat_color(name="Taken", slug="taken"))

    with pytest.raises(ClientError):
        await service.update(str(current.id), CoatColorUpdateDto(slug="taken"))

    assert [name for name, _ in repo.calls] == ["get_by_slug_or_id", "find_by_slug"]


async def test_update_uc15_self_exclusion_allows_same_name_and_slug() -> None:
    service, repo = make_service()
    current = repo.add(make_coat_color(name="Current", slug="current"))

    updated = await service.update(
        "current", CoatColorUpdateDto(name="Current", slug="current")
    )

    assert updated.id == current.id
    assert updated.name == "Current"
    assert updated.slug == "current"


async def test_update_uc19_changes_only_explicit_fields() -> None:
    service, repo = make_service()
    repo.add(make_coat_color(description="Old", page_data="<div>Old</div>"))

    updated = await service.update("bay", CoatColorUpdateDto(description="New"))

    assert updated.description == "New"
    assert updated.page_data == "<div>Old</div>"
    assert updated.name == "Bay"


async def test_update_uc20_empty_payload_is_client_error() -> None:
    service, repo = make_service()
    current = repo.add(make_coat_color())

    with pytest.raises(ClientError):
        await service.update(str(current.id), CoatColorUpdateDto())

    assert [name for name, _ in repo.calls] == ["get_by_slug_or_id"]


async def test_update_uc21_repository_update_failure_does_not_delete_entity() -> None:
    service, repo = make_service()
    current = repo.add(make_coat_color())
    repo.fail_on.add("update")

    with pytest.raises(RepositoryError):
        await service.update(str(current.id), CoatColorUpdateDto(description="New"))

    assert current.id in repo.by_id


async def test_update_uc29_business_validation_uses_client_error() -> None:
    service, repo = make_service()
    repo.add(make_coat_color())

    with pytest.raises(ClientError):
        await service.update("bay", CoatColorUpdateDto(slug=" "))


async def test_get_by_slug_or_id_uc01_returns_coat_color_by_slug_and_uuid() -> None:
    service, repo = make_service()
    coat_color = repo.add(make_coat_color())

    assert await service.get_by_slug_or_id("bay") == coat_color
    assert await service.get_by_slug_or_id(str(coat_color.id)) == coat_color


async def test_get_by_slug_or_id_uc13_not_found_raises_client_error() -> None:
    service, _ = make_service()

    with pytest.raises(ClientError):
        await service.get_by_slug_or_id("missing")


async def test_get_by_slug_or_id_uc21_repository_failure_propagates() -> None:
    service, repo = make_service()
    repo.fail_on.add("get_by_slug_or_id")

    with pytest.raises(RepositoryError):
        await service.get_by_slug_or_id("bay")


async def test_delete_uc01_deletes_existing_coat_color_by_slug() -> None:
    service, repo = make_service()
    coat_color = repo.add(make_coat_color())

    await service.delete("bay")

    assert coat_color.id not in repo.by_id
    assert [name for name, _ in repo.calls] == ["get_by_slug_or_id", "delete"]


async def test_delete_uc13_not_found_raises_client_error_without_delete() -> None:
    service, repo = make_service()

    with pytest.raises(ClientError):
        await service.delete("missing")

    assert [name for name, _ in repo.calls] == ["get_by_slug_or_id"]


async def test_delete_uc21_repository_delete_failure_propagates() -> None:
    service, repo = make_service()
    repo.add(make_coat_color())
    repo.fail_on.add("delete")

    with pytest.raises(RepositoryError):
        await service.delete("bay")


async def test_get_filtered_uc01_uc25_uc26_uc27_passes_contract_through() -> None:
    service, repo = make_service()
    result = [make_coat_color()]
    repo.filtered_result = (result, 10)

    entities, total = await service.get_filtered(
        name="Bay",
        slug="bay",
        description="brown",
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
                "name": "Bay",
                "slug": "bay",
                "description": "brown",
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


async def test_get_filtered_uc08_boundary_zero_limit_and_offset_are_passed() -> None:
    service, repo = make_service()

    assert await service.get_filtered(limit=0, offset=0) == ([], 0)
    assert repo.calls == [
        (
            "get_filtered",
            {
                "name": None,
                "slug": None,
                "description": None,
                "page_data": None,
                "sort": None,
                "limit": 0,
                "offset": 0,
            },
        )
    ]


async def test_get_filtered_uc09_negative_limit_or_offset_is_client_error() -> None:
    service, repo = make_service()

    with pytest.raises(ClientError):
        await service.get_filtered(limit=-1)
    with pytest.raises(ClientError):
        await service.get_filtered(offset=-1)
    assert repo.calls == []


async def test_get_filtered_uc21_repository_failure_propagates() -> None:
    service, repo = make_service()
    repo.fail_on.add("get_filtered")

    with pytest.raises(RepositoryError):
        await service.get_filtered(limit=1)


async def test_coat_color_service_uc30_architecture_boundary_has_no_fastapi_dependency() -> (
    None
):
    import core.services.coat_color as coat_color_module

    assert not hasattr(coat_color_module, "HTTPException")
    assert_raises_client_error(
        lambda: CoatColorService(
            cast(Any, FakeCoatColorRepository())
        )._validate_required_text(
            field="Название масти",
            value=" ",
            max_length=63,
        )
    )
