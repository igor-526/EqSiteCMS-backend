from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

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
from core.schemas.horses import FoalParentsDto, HorseFoalOutDto
from core.services.horse import HorseService


def dependencies() -> tuple[HorseService, AsyncMock]:
    horse_repository = AsyncMock()
    service = HorseService(
        horse_repository=horse_repository,
        horse_children_repository=AsyncMock(),
        breed_repository=AsyncMock(),
        coat_color_repository=AsyncMock(),
        horse_owner_repository=AsyncMock(),
    )
    return service, horse_repository


def context() -> EquestrianContext:
    return EquestrianContext(id=uuid4(), source="authenticated")


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
        "code": "OLD",
    }
    data.update(values)
    return Horse(**data)


@pytest.mark.asyncio
@pytest.mark.parametrize("code", ["EXT-025", None, ""], ids=["value", "null", "empty"])
async def test_service_create_passes_exact_code_to_repository(code: str | None) -> None:
    service, repository = dependencies()
    ctx = context()
    repository.create.side_effect = lambda horse: horse

    result = await service.create_horse(
        create_data=HorseCreateInDto(name="Буран", code=code),
        equestrian_context=ctx,
        user=user(ctx),
    )

    created = repository.create.await_args.args[0]
    assert created.code == code
    assert created.equestrian_id == ctx.id
    assert result.code == code


@pytest.mark.asyncio
async def test_invalid_create_code_never_mutates_repository() -> None:
    _service, repository = dependencies()

    with pytest.raises(ValidationError):
        HorseCreateInDto(name="Буран", code="x" * 32)

    repository.create.assert_not_awaited()
    repository.update.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload, expected_code",
    [({"code": "NEW"}, "NEW"), ({"code": None}, None), ({"description": "new"}, "OLD")],
    ids=["code-only", "explicit-null", "code-omitted"],
)
async def test_service_update_respects_code_fields_set(
    payload: dict[str, object], expected_code: str | None
) -> None:
    service, repository = dependencies()
    ctx = context()
    stored = entity(ctx, description="old")
    repository.get_by_id.return_value = stored

    async def updated_dto(**_: object) -> HorseOutDto:
        return HorseOutDto(
            id=stored.id, slug=stored.slug or "", name=stored.name, code=stored.code
        )

    repository.get_horse_full_info_by_id.side_effect = updated_dto
    result = await service.update_horse(
        horse_id=stored.id,
        data=HorseUpdateInDto.model_validate(payload),
        equestrian_context=ctx,
        user=user(ctx),
    )

    repository.get_by_id.assert_awaited_once_with(stored.id, equestrian_id=ctx.id)
    repository.update.assert_awaited_once_with(stored)
    assert stored.code == expected_code
    assert stored.name == "Буран"
    assert result.code == expected_code


@pytest.mark.asyncio
async def test_anonymous_and_no_scope_create_do_not_touch_repository() -> None:
    service, repository = dependencies()
    ctx = context()
    command = HorseCreateInDto(name="Буран", code="X")

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
async def test_cross_tenant_update_is_not_mutated() -> None:
    service, repository = dependencies()
    ctx = context()
    foreign = entity(context(), code="FOREIGN")
    repository.get_by_id.return_value = None

    with pytest.raises(ClientError, match="Лошадь не найдена"):
        await service.update_horse(
            horse_id=foreign.id,
            data=HorseUpdateInDto(code="ATTACK"),
            equestrian_context=ctx,
            user=user(ctx),
        )

    assert foreign.code == "FOREIGN"
    repository.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_detail_by_uuid_and_slug_return_repository_code() -> None:
    service, repository = dependencies()
    ctx = context()
    dto = HorseOutDto(id=uuid4(), slug="buran", name="Буран", code="DETAIL-025")
    repository.get_horse_full_info_by_id.return_value = dto
    repository.get_horse_full_info_by_slug.return_value = dto

    by_id = await service.get_horse_by_slug_or_id(
        slug_or_id=str(dto.id), equestrian_context=ctx, user=None
    )
    by_slug = await service.get_horse_by_slug_or_id(
        slug_or_id=dto.slug, equestrian_context=ctx, user=None
    )

    assert by_id.code == by_slug.code == "DETAIL-025"
    repository.get_horse_full_info_by_id.assert_awaited_once_with(
        horse_id=dto.id, equestrian_id=ctx.id, pedigree=None
    )
    repository.get_horse_full_info_by_slug.assert_awaited_once_with(
        horse_slug=dto.slug, equestrian_id=ctx.id, pedigree=None
    )


def test_pedigree_foal_candidate_and_photos_dtos_keep_own_codes() -> None:
    sire = HorseOutDto(id=uuid4(), slug="sire", name="Sire", code="SIRE")
    dam = HorseOutDto(id=uuid4(), slug="dam", name="Dam", code=None)
    foal = HorseFoalOutDto(
        id=uuid4(), slug="foal", name="Foal", code="FOAL", parents=FoalParentsDto()
    )
    root = HorseWithPedigreeOutDto(
        id=uuid4(),
        slug="root",
        name="Root",
        code="ROOT",
        pedigree=HorsePedigree(sire=sire, dam=dam, foals=[foal]),
    )
    candidate = HorseOutDto(id=uuid4(), slug="candidate", name="Candidate", code="CAND")
    photos_response = HorseOutDto(
        id=root.id, slug=root.slug, name=root.name, code=root.code, photos=[]
    )

    payload = root.model_dump(mode="json")
    assert payload["code"] == "ROOT"
    assert payload["pedigree"]["sire"]["code"] == "SIRE"
    assert payload["pedigree"]["dam"]["code"] is None
    assert payload["pedigree"]["foals"][0]["code"] == "FOAL"
    assert candidate.model_dump(mode="json")["code"] == "CAND"
    assert photos_response.model_dump(mode="json")["code"] == "ROOT"
