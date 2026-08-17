from datetime import datetime, timezone
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from core.entities.breed_groups import BreedGroup
from core.entities.equestrian import EquestrianContext
from core.entities.user import UserScope
from core.exceptions.auth import ForbiddenError
from core.exceptions.base import ClientError
from core.schemas.breed_groups import BreedGroupCreateDto, BreedGroupUpdateDto
from core.schemas.users import UserOutDto
from core.services.breed_groups import BreedGroupService

pytestmark = pytest.mark.asyncio
TENANT = UUID("11111111-1111-4111-8111-111111111111")
CONTEXT = EquestrianContext(id=TENANT, source="test")


def entity(**values: Any) -> BreedGroup:
    data = {"equestrian_id": TENANT, "name": "Warmbloods", "slug": "warmbloods"}
    data.update(values)
    return BreedGroup(**data)


def user(scope: str) -> UserOutDto:
    return UserOutDto(
        id=uuid4(),
        equestrian_id=TENANT,
        username="u",
        created_at=datetime.now(timezone.utc),
        scopes=[UserScope(scope_name=scope, scope_description="x")],
    )


def setup() -> tuple[BreedGroupService, AsyncMock]:
    repo = AsyncMock()
    repo.find_by_name.return_value = None
    repo.find_by_slug.return_value = None
    repo.create.side_effect = lambda item: item
    repo.update.side_effect = lambda item: item
    return BreedGroupService(cast(Any, repo)), repo


async def test_entity_has_tenant_timestamps_and_defaults() -> None:
    item = entity()
    assert item.equestrian_id == TENANT and item.created_at and item.updated_at
    assert item.page_data == "<div></div>"


async def test_create_normalizes_name_generates_slug_and_default_html() -> None:
    service, repo = setup()
    result = await service.create(
        BreedGroupCreateDto(name="  Тяжеловозы  "), equestrian_context=CONTEXT
    )
    assert (result.name, result.slug, result.page_data) == (
        "Тяжеловозы",
        "tyazhelovozy",
        "<div></div>",
    )
    repo.create.assert_awaited_once()


@pytest.mark.parametrize("name", ["", "   ", "x" * 64])
async def test_invalid_name_rejected_before_create(name: str) -> None:
    service, repo = setup()
    with pytest.raises(ClientError):
        await service.create(BreedGroupCreateDto(name=name), equestrian_context=CONTEXT)
    repo.create.assert_not_awaited()


async def test_unsafe_html_rejected() -> None:
    service, repo = setup()
    with pytest.raises(ClientError):
        await service.create(
            BreedGroupCreateDto(name="A", page_data="<script>alert(1)</script>"),
            equestrian_context=CONTEXT,
        )
    repo.create.assert_not_awaited()


async def test_duplicate_name_rejected() -> None:
    service, repo = setup()
    repo.find_by_name.return_value = entity()
    with pytest.raises(ClientError):
        await service.create(
            BreedGroupCreateDto(name="Warmbloods"), equestrian_context=CONTEXT
        )


async def test_duplicate_slug_gets_deterministic_suffix() -> None:
    service, repo = setup()
    repo.find_by_slug.side_effect = [entity(), entity(slug="warmbloods-1"), None]
    result = await service.create(
        BreedGroupCreateDto(name="Other", slug="warmbloods"), equestrian_context=CONTEXT
    )
    assert result.slug == "warmbloods-2"


async def test_user_without_scope_is_forbidden() -> None:
    service, repo = setup()
    with pytest.raises(ForbiddenError):
        await service.create(
            BreedGroupCreateDto(name="A"),
            equestrian_context=CONTEXT,
            user=user("VIEWER"),
        )
    repo.create.assert_not_awaited()


@pytest.mark.parametrize("scope", ["ADMIN", "DEVELOPER", "SUPERUSER"])
async def test_allowed_scopes_create(scope: str) -> None:
    service, repo = setup()
    await service.create(
        BreedGroupCreateDto(name="A"), equestrian_context=CONTEXT, user=user(scope)
    )
    repo.create.assert_awaited_once()


@pytest.mark.parametrize("lookup", ["warmbloods", str(uuid4())])
async def test_detail_uses_tenant_lookup(lookup: str) -> None:
    service, repo = setup()
    repo.get_by_slug_or_id.return_value = entity()
    await service.get(lookup, equestrian_context=CONTEXT)
    assert repo.get_by_slug_or_id.await_args.kwargs["equestrian_id"] == TENANT


async def test_missing_detail_has_no_disclosure() -> None:
    service, repo = setup()
    repo.get_by_slug_or_id.return_value = None
    with pytest.raises(ClientError, match="не найдена"):
        await service.get(str(uuid4()), equestrian_context=CONTEXT)


async def test_list_forwards_filters_sort_and_paging() -> None:
    service, repo = setup()
    repo.get_filtered.return_value = ([entity()], 7)
    result = await service.list(
        equestrian_context=CONTEXT,
        name="war",
        slug="w",
        page_data="div",
        sort=["-name"],
        limit=5,
        offset=10,
    )
    assert result[1] == 7
    assert repo.get_filtered.await_args.kwargs == {
        "equestrian_id": TENANT,
        "name": "war",
        "slug": "w",
        "page_data": "div",
        "sort": ["-name"],
        "limit": 5,
        "offset": 10,
    }


async def test_empty_patch_rejected_without_update() -> None:
    service, repo = setup()
    repo.get_by_slug_or_id.return_value = entity()
    with pytest.raises(ClientError):
        await service.update(
            "warmbloods", BreedGroupUpdateDto(), equestrian_context=CONTEXT
        )
    repo.update.assert_not_awaited()


async def test_partial_update_preserves_absent_fields() -> None:
    service, repo = setup()
    original = entity(page_data="<div>old</div>")
    repo.get_by_slug_or_id.return_value = original
    result = await service.update(
        "warmbloods", BreedGroupUpdateDto(slug="new"), equestrian_context=CONTEXT
    )
    assert result.name == "Warmbloods" and result.page_data == "<div>old</div>"


async def test_rename_recomputes_slug() -> None:
    service, repo = setup()
    repo.get_by_slug_or_id.return_value = entity()
    result = await service.update(
        "warmbloods",
        BreedGroupUpdateDto(name="Draft Horses"),
        equestrian_context=CONTEXT,
    )
    assert result.slug == "draft-horses"


async def test_update_revalidates_html() -> None:
    service, repo = setup()
    repo.get_by_slug_or_id.return_value = entity()
    with pytest.raises(ClientError):
        await service.update(
            "warmbloods",
            BreedGroupUpdateDto(page_data="javascript:alert(1)"),
            equestrian_context=CONTEXT,
        )
    repo.update.assert_not_awaited()


async def test_delete_is_tenant_scoped() -> None:
    service, repo = setup()
    item = entity()
    repo.get_by_slug_or_id.return_value = item
    await service.delete("warmbloods", equestrian_context=CONTEXT)
    repo.delete.assert_awaited_once_with(item.id, equestrian_id=TENANT)


async def test_repository_failure_does_not_report_success() -> None:
    service, repo = setup()
    repo.create.side_effect = RuntimeError("constraint")
    with pytest.raises(RuntimeError, match="constraint"):
        await service.create(
            BreedGroupCreateDto(name="Atomic"), equestrian_context=CONTEXT
        )
    assert repo.update.await_count == 0 and repo.delete.await_count == 0
