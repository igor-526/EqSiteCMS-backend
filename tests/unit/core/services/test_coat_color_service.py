from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from tenant_context import TEST_EQUESTRIAN_CONTEXT

from core.entities.coat_color import CoatColor
from core.entities.equestrian import EquestrianContext
from core.entities.user import UserScope
from core.exceptions.auth import ForbiddenError
from core.exceptions.base import ClientError
from core.schemas.coat_color import CoatColorCreateDto, CoatColorUpdateDto
from core.schemas.users import UserOutDto
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
        short_name: str | None = None,
        slug: str | None = None,
        description: str | None = None,
        page_data: str | None = None,
        sort: list[str] | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[list[CoatColor], int]:
        filters = {
            "name": name,
            "short_name": short_name,
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


def make_user(*, scope_names: list[str]) -> UserOutDto:
    return UserOutDto(
        equestrian_id=TEST_EQUESTRIAN_CONTEXT.id,
        id=uuid4(),
        username="coat-color-user",
        created_at=datetime.now(tz=timezone.utc),
        scopes=[
            UserScope(scope_name=name, scope_description=f"{name} scope")
            for name in scope_names
        ],
    )


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

    assert (
        await service._ensure_unique_slug(
            "bay", equestrian_context=TEST_EQUESTRIAN_CONTEXT
        )
        == "bay"
    )
    assert repo.calls == [("find_by_slug", "bay")]


async def test_ensure_unique_slug_uc14_suffix_loop_and_uc22_order() -> None:
    service, repo = make_service()
    repo.add(make_coat_color(slug="bay"))
    repo.add(make_coat_color(name="Other", slug="bay-1"))

    assert (
        await service._ensure_unique_slug(
            "bay", equestrian_context=TEST_EQUESTRIAN_CONTEXT
        )
        == "bay-2"
    )
    assert repo.calls == [
        ("find_by_slug", "bay"),
        ("find_by_slug", "bay-1"),
        ("find_by_slug", "bay-2"),
    ]


async def test_ensure_unique_slug_uc15_self_exclusion_returns_existing_slug() -> None:
    service, repo = make_service()
    coat_color = repo.add(make_coat_color(slug="bay"))

    assert (
        await service._ensure_unique_slug(
            "bay", exclude_id=coat_color.id, equestrian_context=TEST_EQUESTRIAN_CONTEXT
        )
        == "bay"
    )


async def test_ensure_unique_slug_uc21_repository_failure_propagates_without_side_effects() -> (
    None
):
    service, repo = make_service()
    repo.fail_on.add("find_by_slug")

    with pytest.raises(RepositoryError):
        await service._ensure_unique_slug(
            "bay", equestrian_context=TEST_EQUESTRIAN_CONTEXT
        )
    assert [name for name, _ in repo.calls] == ["find_by_slug"]


async def test_create_uc01_minimal_input_generates_slug_and_default_page_data() -> None:
    service, repo = make_service()

    coat_color = await service.create(
        CoatColorCreateDto(name="Гнедая"), equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )

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
        ),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
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


async def test_create_uc05_empty_name_is_client_error_and_empty_slug_is_generated() -> (
    None
):
    service, repo = make_service()

    with pytest.raises(ClientError):
        await service.create(
            CoatColorCreateDto(name=" "), equestrian_context=TEST_EQUESTRIAN_CONTEXT
        )
    created = await service.create(
        CoatColorCreateDto(name="Bay", slug=""),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )
    assert created.slug == "bay"


async def test_create_uc10_uc11_length_boundaries_are_enforced() -> None:
    service, _ = make_service()

    accepted = await service.create(
        CoatColorCreateDto(name="a" * 63), equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )
    assert accepted.name == "a" * 63

    with pytest.raises(ClientError):
        await service.create(
            CoatColorCreateDto(name="a" * 64),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )


async def test_create_uc14_duplicate_name_rejects_before_slug_and_create() -> None:
    service, repo = make_service()
    repo.add(make_coat_color(name="Bay"))

    with pytest.raises(ClientError):
        await service.create(
            CoatColorCreateDto(name="Bay"), equestrian_context=TEST_EQUESTRIAN_CONTEXT
        )

    assert [name for name, _ in repo.calls] == ["find_by_name"]


async def test_create_uc14_explicit_slug_collision_is_client_error() -> None:
    service, repo = make_service()
    repo.add(make_coat_color(name="Existing", slug="bay"))

    with pytest.raises(ClientError):
        await service.create(
            CoatColorCreateDto(name="New", slug="bay"),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )

    assert [name for name, _ in repo.calls] == ["find_by_name", "find_by_slug"]


async def test_create_uc21_repository_create_failure_leaves_fake_without_entity() -> (
    None
):
    service, repo = make_service()
    repo.fail_on.add("create")

    with pytest.raises(RepositoryError):
        await service.create(
            CoatColorCreateDto(name="Bay"), equestrian_context=TEST_EQUESTRIAN_CONTEXT
        )

    assert "Bay" not in repo.by_name


async def test_create_uc24_retry_generated_slug_conflict_gets_next_suffix() -> None:
    service, repo = make_service()
    repo.add(make_coat_color(name="Existing", slug="bay"))

    created = await service.create(
        CoatColorCreateDto(name="Bay Copy"), equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )
    duplicate_generated = await service.create(
        CoatColorCreateDto(name="Bay"), equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )

    assert created.slug == "bay-copy"
    assert duplicate_generated.slug == "bay-1"


async def test_update_uc01_partial_name_regenerates_slug() -> None:
    service, repo = make_service()
    coat_color = repo.add(make_coat_color(name="Old", slug="old"))

    updated = await service.update(
        str(coat_color.id),
        CoatColorUpdateDto(name="Рыжая"),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

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
        await service.update(
            "missing",
            CoatColorUpdateDto(name="New"),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )
    assert [name for name, _ in repo.calls] == ["get_by_slug_or_id"]


async def test_update_uc14_duplicate_name_rejects_without_update() -> None:
    service, repo = make_service()
    current = repo.add(make_coat_color(name="Current", slug="current"))
    repo.add(make_coat_color(name="Taken", slug="taken"))

    with pytest.raises(ClientError):
        await service.update(
            str(current.id),
            CoatColorUpdateDto(name="Taken"),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )

    assert [name for name, _ in repo.calls] == ["get_by_slug_or_id", "find_by_name"]


async def test_update_uc14_explicit_slug_collision_rejects_without_update() -> None:
    service, repo = make_service()
    current = repo.add(make_coat_color(name="Current", slug="current"))
    repo.add(make_coat_color(name="Taken", slug="taken"))

    with pytest.raises(ClientError):
        await service.update(
            str(current.id),
            CoatColorUpdateDto(slug="taken"),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )

    assert [name for name, _ in repo.calls] == ["get_by_slug_or_id", "find_by_slug"]


async def test_update_uc15_self_exclusion_allows_same_name_and_slug() -> None:
    service, repo = make_service()
    current = repo.add(make_coat_color(name="Current", slug="current"))

    updated = await service.update(
        "current",
        CoatColorUpdateDto(name="Current", slug="current"),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert updated.id == current.id
    assert updated.name == "Current"
    assert updated.slug == "current"


async def test_update_uc19_changes_only_explicit_fields() -> None:
    service, repo = make_service()
    repo.add(make_coat_color(description="Old", page_data="<div>Old</div>"))

    updated = await service.update(
        "bay",
        CoatColorUpdateDto(description="New"),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert updated.description == "New"
    assert updated.page_data == "<div>Old</div>"
    assert updated.name == "Bay"


async def test_update_uc20_empty_payload_is_client_error() -> None:
    service, repo = make_service()
    current = repo.add(make_coat_color())

    with pytest.raises(ClientError):
        await service.update(
            str(current.id),
            CoatColorUpdateDto(),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )

    assert [name for name, _ in repo.calls] == ["get_by_slug_or_id"]


async def test_update_uc21_repository_update_failure_does_not_delete_entity() -> None:
    service, repo = make_service()
    current = repo.add(make_coat_color())
    repo.fail_on.add("update")

    with pytest.raises(RepositoryError):
        await service.update(
            str(current.id),
            CoatColorUpdateDto(description="New"),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )

    assert current.id in repo.by_id


async def test_update_uc29_empty_slug_preserves_current_slug() -> None:
    service, repo = make_service()
    repo.add(make_coat_color())

    updated = await service.update(
        "bay", CoatColorUpdateDto(slug=" "), equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )
    assert updated.slug == "bay"


async def test_validation_026_create_slug_null_generates_slug() -> None:
    service, _ = make_service()
    assert (
        await service.create(
            CoatColorCreateDto(name="Bay", slug=None),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )
    ).slug == "bay"


async def test_validation_026_create_whitespace_slug_generates_slug() -> None:
    service, _ = make_service()
    assert (
        await service.create(
            CoatColorCreateDto(name="Bay", slug="  \t"),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )
    ).slug == "bay"


async def test_validation_026_generated_slug_collision_gets_suffix() -> None:
    service, repo = make_service()
    repo.add(make_coat_color(name="Existing", slug="gnedaya"))
    assert (
        await service.create(
            CoatColorCreateDto(name="Гнедая", slug=""),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )
    ).slug == "gnedaya-1"


async def test_validation_026_missing_description_is_none() -> None:
    service, _ = make_service()
    assert (
        await service.create(
            CoatColorCreateDto(name="Bay"), equestrian_context=TEST_EQUESTRIAN_CONTEXT
        )
    ).description is None


async def test_validation_026_null_description_is_none() -> None:
    service, _ = make_service()
    assert (
        await service.create(
            CoatColorCreateDto(name="Bay", description=None),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )
    ).description is None


async def test_validation_026_empty_description_is_none() -> None:
    service, _ = make_service()
    assert (
        await service.create(
            CoatColorCreateDto(name="Bay", description=""),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )
    ).description is None


async def test_validation_026_whitespace_description_is_none() -> None:
    service, _ = make_service()
    assert (
        await service.create(
            CoatColorCreateDto(name="Bay", description=" \t"),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )
    ).description is None


async def test_validation_026_description_511_is_accepted() -> None:
    service, _ = make_service()
    assert (
        len(
            (
                await service.create(
                    CoatColorCreateDto(name="Bay", description="d" * 511),
                    equestrian_context=TEST_EQUESTRIAN_CONTEXT,
                )
            ).description
            or ""
        )
        == 511
    )


async def test_validation_026_description_512_is_rejected_without_write() -> None:
    service, repo = make_service()
    with pytest.raises(ClientError):
        await service.create(
            CoatColorCreateDto(name="Bay", description="d" * 512),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )
    assert not any(name == "create" for name, _ in repo.calls)


async def test_validation_026_rename_with_empty_slug_generates_unique_slug() -> None:
    service, repo = make_service()
    current = repo.add(make_coat_color(name="Old", slug="old"))
    repo.add(make_coat_color(name="Taken", slug="ryzhaya"))
    updated = await service.update(
        str(current.id),
        CoatColorUpdateDto(name="Рыжая", slug=""),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )
    assert updated.slug == "ryzhaya-1"


async def test_validation_026_update_empty_description_sets_none() -> None:
    service, repo = make_service()
    current = repo.add(make_coat_color())
    updated = await service.update(
        str(current.id),
        CoatColorUpdateDto(description=" "),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )
    assert updated.description is None


async def test_validation_026_foreign_tenant_cannot_update_record() -> None:
    class TenantAwareRepository(FakeCoatColorRepository):
        async def get_by_slug_or_id(
            self, slug_or_id: str | UUID, *, equestrian_id: UUID | None = None
        ) -> CoatColor | None:
            coat_color = await super().get_by_slug_or_id(slug_or_id)
            if coat_color is None or coat_color.equestrian_id != equestrian_id:
                return None
            return coat_color

    repo = TenantAwareRepository()
    foreign_id = uuid4()
    repo.add(make_coat_color(equestrian_id=foreign_id))
    service = CoatColorService(coat_color_repository=cast(Any, repo))

    with pytest.raises(ClientError, match="не найдена"):
        await service.update(
            "bay",
            CoatColorUpdateDto(description="denied"),
            equestrian_context=EquestrianContext(id=uuid4(), source="authenticated"),
        )
    assert repo.by_slug["bay"].description == "Brown coat with black points"


async def test_validation_026_create_denies_authenticated_user_without_admin_scope() -> (
    None
):
    service, repo = make_service()
    with pytest.raises(ForbiddenError):
        await service.create(
            CoatColorCreateDto(name="Denied"),
            user=make_user(scope_names=["CONTENT_EDITOR"]),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )
    assert repo.calls == []


async def test_validation_026_update_denies_authenticated_user_without_admin_scope() -> (
    None
):
    service, repo = make_service()
    current = repo.add(make_coat_color())
    with pytest.raises(ForbiddenError):
        await service.update(
            "bay",
            CoatColorUpdateDto(description="Denied"),
            user=make_user(scope_names=[]),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )
    assert current.description == "Brown coat with black points"
    assert repo.calls == []


async def test_validation_026_delete_denies_authenticated_user_without_admin_scope() -> (
    None
):
    service, repo = make_service()
    current = repo.add(make_coat_color())
    with pytest.raises(ForbiddenError):
        await service.delete(
            "bay",
            user=make_user(scope_names=["CONTENT_EDITOR"]),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )
    assert current.id in repo.by_id
    assert repo.calls == []


async def test_get_by_slug_or_id_uc01_returns_coat_color_by_slug_and_uuid() -> None:
    service, repo = make_service()
    coat_color = repo.add(make_coat_color())

    assert (
        await service.get_by_slug_or_id(
            "bay", equestrian_context=TEST_EQUESTRIAN_CONTEXT
        )
        == coat_color
    )
    assert (
        await service.get_by_slug_or_id(
            str(coat_color.id), equestrian_context=TEST_EQUESTRIAN_CONTEXT
        )
        == coat_color
    )


async def test_get_by_slug_or_id_uc13_not_found_raises_client_error() -> None:
    service, _ = make_service()

    with pytest.raises(ClientError):
        await service.get_by_slug_or_id(
            "missing", equestrian_context=TEST_EQUESTRIAN_CONTEXT
        )


async def test_get_by_slug_or_id_uc21_repository_failure_propagates() -> None:
    service, repo = make_service()
    repo.fail_on.add("get_by_slug_or_id")

    with pytest.raises(RepositoryError):
        await service.get_by_slug_or_id(
            "bay", equestrian_context=TEST_EQUESTRIAN_CONTEXT
        )


async def test_delete_uc01_deletes_existing_coat_color_by_slug() -> None:
    service, repo = make_service()
    coat_color = repo.add(make_coat_color())

    await service.delete("bay", equestrian_context=TEST_EQUESTRIAN_CONTEXT)

    assert coat_color.id not in repo.by_id
    assert [name for name, _ in repo.calls] == ["get_by_slug_or_id", "delete"]


async def test_delete_uc13_not_found_raises_client_error_without_delete() -> None:
    service, repo = make_service()

    with pytest.raises(ClientError):
        await service.delete("missing", equestrian_context=TEST_EQUESTRIAN_CONTEXT)

    assert [name for name, _ in repo.calls] == ["get_by_slug_or_id"]


async def test_delete_uc21_repository_delete_failure_propagates() -> None:
    service, repo = make_service()
    repo.add(make_coat_color())
    repo.fail_on.add("delete")

    with pytest.raises(RepositoryError):
        await service.delete("bay", equestrian_context=TEST_EQUESTRIAN_CONTEXT)


async def test_get_filtered_uc01_uc25_uc26_uc27_passes_contract_through() -> None:
    service, repo = make_service()
    result = [make_coat_color()]
    repo.filtered_result = (result, 10)

    entities, total = await service.get_filtered(
        name="Bay",
        short_name="B",
        slug="bay",
        description="brown",
        page_data="page",
        sort=["name", "-slug"],
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
                "name": "Bay",
                "short_name": "B",
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

    assert await service.get_filtered(equestrian_context=TEST_EQUESTRIAN_CONTEXT) == (
        [],
        0,
    )
    assert repo.calls == [
        (
            "get_filtered",
            {
                "name": None,
                "short_name": None,
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

    assert await service.get_filtered(
        limit=0, offset=0, equestrian_context=TEST_EQUESTRIAN_CONTEXT
    ) == ([], 0)
    assert repo.calls == [
        (
            "get_filtered",
            {
                "name": None,
                "short_name": None,
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
        await service.get_filtered(limit=1, equestrian_context=TEST_EQUESTRIAN_CONTEXT)


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


# --- short_name auto-generation tests ---


async def test_create_short_name_none_generates_from_name() -> None:
    """Если short_name не передан (None) — автоматически берётся из name."""
    service, _ = make_service()

    coat_color = await service.create(
        CoatColorCreateDto(name="Гнедая", short_name=None),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert coat_color.short_name == "Гнедая"


async def test_create_short_name_empty_string_generates_from_name() -> None:
    """Если short_name передан как пустая строка — автоматически берётся из name."""
    service, _ = make_service()

    coat_color = await service.create(
        CoatColorCreateDto(name="Гнедая", short_name=""),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert coat_color.short_name == "Гнедая"


async def test_create_short_name_explicit_value_is_preserved() -> None:
    """Если short_name передан явно — используется как есть."""
    service, _ = make_service()

    coat_color = await service.create(
        CoatColorCreateDto(name="Гнедая", short_name="ГН"),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert coat_color.short_name == "ГН"


async def test_create_short_name_long_name_truncated_to_max_len() -> None:
    """Если name длиннее MAX_LEN и short_name не передан — обрезается до MAX_LEN."""
    service, _ = make_service()
    long_name = "А" * 63  # exactly at boundary
    coat_color = await service.create(
        CoatColorCreateDto(name=long_name, short_name=None),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert coat_color.short_name == long_name[:63]
    assert len(coat_color.short_name) == 63


async def test_create_short_name_whitespace_only_generates_from_name() -> None:
    """Если short_name — только пробелы — автоматически берётся из name."""
    service, _ = make_service()

    coat_color = await service.create(
        CoatColorCreateDto(name="Серая", short_name="   "),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert coat_color.short_name == "Серая"


async def test_update_short_name_empty_string_generates_from_current_name() -> None:
    """При обновлении short_name='' — автоматически берётся из существующего name."""
    service, repo = make_service()
    repo.add(make_coat_color(name="Bay", slug="bay", short_name="B"))

    updated = await service.update(
        "bay",
        CoatColorUpdateDto(short_name=""),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert updated.short_name == "Bay"


async def test_update_short_name_empty_with_new_name_uses_new_name() -> None:
    """При обновлении name + short_name='' — short_name берётся из нового name."""
    service, repo = make_service()
    repo.add(make_coat_color(name="Old", slug="old", short_name="O"))

    updated = await service.update(
        "old",
        CoatColorUpdateDto(name="Рыжая", short_name=""),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert updated.short_name == "Рыжая"


async def test_update_short_name_explicit_value_is_preserved() -> None:
    """При обновлении short_name с явным значением — значение сохраняется."""
    service, repo = make_service()
    repo.add(make_coat_color(name="Bay", slug="bay", short_name="B"))

    updated = await service.update(
        "bay",
        CoatColorUpdateDto(short_name="ГН"),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert updated.short_name == "ГН"
