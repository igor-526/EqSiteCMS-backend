from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from core.entities import Horse, UserScope
from core.entities.equestrian import EquestrianContext
from core.exceptions.auth import ForbiddenError
from core.exceptions.base import ClientError
from core.schemas import (
    HorseCreateInDto,
    HorseOutDto,
    HorsePedigree,
    HorseUpdateInDto,
    HorseWithPedigreeOutDto,
    UserOutDto,
)
from core.schemas.horses import (
    FoalParentRefDto,
    FoalParentsDto,
    HorseFoalOutDto,
)
from core.services.horse import HorseService


def dependencies() -> tuple[HorseService, AsyncMock]:
    repository = AsyncMock()
    return (
        HorseService(
            horse_repository=repository,
            horse_children_repository=AsyncMock(),
            breed_repository=AsyncMock(),
            coat_color_repository=AsyncMock(),
            horse_owner_repository=AsyncMock(),
        ),
        repository,
    )


def context(source: str = "authenticated") -> EquestrianContext:
    return EquestrianContext(id=uuid4(), source=source)  # type: ignore[arg-type]


def user(ctx: EquestrianContext, scope: str = "ADMIN") -> UserOutDto:
    scopes = [UserScope(scope_name=scope, scope_description=scope)] if scope else []
    return UserOutDto(
        id=uuid4(),
        equestrian_id=ctx.id,
        username="tester",
        created_at=datetime.now(timezone.utc),
        scopes=scopes,
    )


def entity(ctx: EquestrianContext, **values: object) -> Horse:
    data: dict[str, object] = {
        "equestrian_id": ctx.id,
        "name": "Буран",
        "slug": "buran",
        "pedigree_name": "Родословный Буран",
    }
    data.update(values)
    return Horse(**data)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "pedigree_name", ["Родословный Буран", None, ""], ids=["value", "null", "empty"]
)
async def test_create_preserves_raw_pedigree_name(
    pedigree_name: str | None,
) -> None:
    service, repository = dependencies()
    ctx = context()
    repository.create.side_effect = lambda horse: horse

    result = await service.create_horse(
        create_data=HorseCreateInDto(name="Буран", pedigree_name=pedigree_name),
        equestrian_context=ctx,
        user=user(ctx),
    )

    created = repository.create.await_args.args[0]
    assert created.pedigree_name == pedigree_name
    assert result.name == "Буран"
    assert result.pedigree_name == pedigree_name


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload, expected",
    [
        ({"pedigree_name": "Новая"}, "Новая"),
        ({"pedigree_name": None}, None),
        ({"description": "new"}, "Родословный Буран"),
    ],
    ids=["replace", "clear", "omit"],
)
async def test_update_respects_omitted_and_null(
    payload: dict[str, object], expected: str | None
) -> None:
    service, repository = dependencies()
    ctx = context()
    stored = entity(ctx)
    repository.get_by_id.return_value = stored
    repository.get_horse_full_info_by_id.side_effect = lambda **_: HorseOutDto(
        id=stored.id,
        slug=stored.slug or "",
        name=stored.name,
        pedigree_name=stored.pedigree_name,
    )

    result = await service.update_horse(
        horse_id=stored.id,
        data=HorseUpdateInDto.model_validate(payload),
        equestrian_context=ctx,
        user=user(ctx),
    )

    assert stored.pedigree_name == expected
    assert result.pedigree_name == expected


@pytest.mark.asyncio
async def test_denied_writes_do_not_mutate_repository() -> None:
    service, repository = dependencies()
    ctx = context()
    command = HorseCreateInDto(name="Буран", pedigree_name="X")

    with pytest.raises(ClientError, match="не авторизован"):
        await service.create_horse(
            create_data=command, equestrian_context=ctx, user=None
        )
    with pytest.raises(ForbiddenError):
        await service.create_horse(
            create_data=command, equestrian_context=ctx, user=user(ctx, scope="")
        )
    repository.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_foreign_tenant_update_does_not_mutate() -> None:
    service, repository = dependencies()
    ctx = context()
    repository.get_by_id.return_value = None

    with pytest.raises(ClientError, match="Лошадь не найдена"):
        await service.update_horse(
            horse_id=uuid4(),
            data=HorseUpdateInDto(pedigree_name="ATTACK"),
            equestrian_context=ctx,
            user=user(ctx),
        )
    repository.update.assert_not_awaited()


def nested_dto() -> HorseWithPedigreeOutDto:
    sire = HorseOutDto(
        id=uuid4(), slug="sire", name="Sire", pedigree_name="Pedigree Sire"
    )
    dam = HorseOutDto(id=uuid4(), slug="dam", name="Dam", pedigree_name=None)
    foal = HorseFoalOutDto(
        id=uuid4(),
        slug="foal",
        name="Foal",
        pedigree_name="Pedigree Foal",
        parents=FoalParentsDto(
            sire=FoalParentRefDto(id=sire.id, name="Sire", pedigree_name="Parent Sire"),
            dam=FoalParentRefDto(id=dam.id, name="Dam", pedigree_name=None),
        ),
    )
    return HorseWithPedigreeOutDto(
        id=uuid4(),
        slug="root",
        name="Root",
        pedigree_name="Pedigree Root",
        pedigree=HorsePedigree(sire=sire, dam=dam, foals=[foal]),
    )


def test_public_projection_is_recursive_independent_and_detached() -> None:
    original = nested_dto()
    result = HorseService._project_public_horse_names(
        original, equestrian_context=context("public")
    )
    assert isinstance(result, HorseWithPedigreeOutDto)
    assert result.name == "Pedigree Root"
    assert result.pedigree_name == "Pedigree Root"
    assert result.pedigree.sire is not None
    assert result.pedigree.sire.name == "Pedigree Sire"
    assert result.pedigree.dam is not None
    assert result.pedigree.dam.name == "Dam"
    assert result.pedigree.foals[0].name == "Pedigree Foal"
    assert result.pedigree.foals[0].parents.sire is not None
    assert result.pedigree.foals[0].parents.sire.name == "Parent Sire"
    assert result.pedigree.foals[0].parents.dam is not None
    assert result.pedigree.foals[0].parents.dam.name == "Dam"
    assert original.name == "Root"
    assert original.pedigree.sire is not None
    assert original.pedigree.sire.name == "Sire"


@pytest.mark.parametrize("pedigree_name", [None, ""])
def test_public_fallback_only_for_null_not_empty(pedigree_name: str | None) -> None:
    dto = HorseOutDto(id=uuid4(), slug="root", name="Root", pedigree_name=pedigree_name)
    result = HorseService._project_public_horse_names(
        dto, equestrian_context=context("public")
    )
    assert result.name == ("Root" if pedigree_name is None else "")
    assert result.pedigree_name == pedigree_name


def test_authenticated_projection_keeps_raw_name_and_explicit_null() -> None:
    dto = HorseOutDto(id=uuid4(), slug="root", name="Root", pedigree_name=None)
    result = HorseService._project_public_horse_names(
        dto, equestrian_context=context("authenticated")
    )
    assert result.name == "Root"
    assert result.model_dump(mode="json")["pedigree_name"] is None
