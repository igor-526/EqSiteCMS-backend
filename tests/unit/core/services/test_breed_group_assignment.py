from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from core.entities.breed_groups import BreedGroup
from core.entities.breeds import Breed
from core.entities.equestrian import EquestrianContext
from core.exceptions.base import ClientError
from core.schemas.breeds import BreedCreateDto, BreedOutDto, BreedUpdateDto
from core.services.breeds import BreedService

pytestmark = pytest.mark.asyncio
TENANT = UUID("11111111-1111-4111-8111-111111111111")
CONTEXT = EquestrianContext(id=TENANT, source="test")


def setup() -> tuple[BreedService, AsyncMock, AsyncMock, BreedGroup]:
    breeds = AsyncMock()
    groups = AsyncMock()
    group = BreedGroup(equestrian_id=TENANT, name="Warmbloods", slug="warmbloods")
    groups.get_by_id.return_value = group
    breeds.find_by_name.return_value = None
    breeds.find_by_slug.return_value = None
    breeds.create.side_effect = lambda item: item
    breeds.update.side_effect = lambda item: item
    return BreedService(cast(Any, breeds), cast(Any, groups)), breeds, groups, group


async def test_create_assigns_valid_tenant_group_and_nested_dto() -> None:
    service, breeds, groups, group = setup()
    result = await service.create(
        BreedCreateDto(name="Arabian", breed_group_id=group.id),
        equestrian_context=CONTEXT,
    )
    assert result.breed_group_id == group.id
    dto_group = BreedOutDto.model_validate(result).group
    assert dto_group is not None
    assert dto_group.model_dump() == {
        "id": group.id,
        "name": "Warmbloods",
        "slug": "warmbloods",
    }
    groups.get_by_id.assert_awaited_once_with(group.id, equestrian_id=TENANT)
    breeds.create.assert_awaited_once()


async def test_create_rejects_unknown_group_before_breed_create() -> None:
    service, breeds, groups, _ = setup()
    groups.get_by_id.return_value = None
    with pytest.raises(ClientError):
        await service.create(
            BreedCreateDto(name="Arabian", breed_group_id=uuid4()),
            equestrian_context=CONTEXT,
        )
    breeds.create.assert_not_awaited()


async def test_update_assigns_valid_group() -> None:
    service, breeds, _, group = setup()
    breed = Breed(
        equestrian_id=TENANT, name="Arabian", short_name="Arabian", slug="arabian"
    )
    breeds.get_by_slug_or_id.return_value = breed
    result = await service.update(
        "arabian", BreedUpdateDto(breed_group_id=group.id), equestrian_context=CONTEXT
    )
    assert result.group and result.group.id == group.id


async def test_update_explicit_null_clears_group() -> None:
    service, breeds, groups, group = setup()
    breed = Breed(
        equestrian_id=TENANT,
        name="Arabian",
        short_name="Arabian",
        slug="arabian",
        breed_group_id=group.id,
    )
    breeds.get_by_slug_or_id.return_value = breed
    result = await service.update(
        "arabian", BreedUpdateDto(breed_group_id=None), equestrian_context=CONTEXT
    )
    assert result.breed_group_id is None and result.group is None
    groups.get_by_id.assert_not_awaited()


async def test_update_without_group_field_preserves_identity() -> None:
    service, breeds, groups, group = setup()
    breed = Breed(
        equestrian_id=TENANT,
        name="Arabian",
        short_name="Arabian",
        slug="arabian",
        breed_group_id=group.id,
        group={"id": group.id, "name": group.name, "slug": group.slug},
    )
    breeds.get_by_slug_or_id.return_value = breed
    result = await service.update(
        "arabian", BreedUpdateDto(description="new"), equestrian_context=CONTEXT
    )
    assert (
        result.breed_group_id == group.id
        and result.group
        and result.group.id == group.id
    )
    groups.get_by_id.assert_not_awaited()


async def test_nested_group_can_be_null() -> None:
    breed = Breed(
        equestrian_id=TENANT, name="Arabian", short_name="Arabian", slug="arabian"
    )
    assert BreedOutDto.model_validate(breed).group is None
