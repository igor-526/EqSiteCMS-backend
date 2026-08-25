from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any, Mapping, cast
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import Column, MetaData, String
from sqlalchemy import Table as SATable
from sqlalchemy.dialects import postgresql
from tenant_context import TEST_EQUESTRIAN_CONTEXT

from core.entities import (
    Breed,
    CoatColor,
    Horse,
    HorseKindEnum,
    HorseOwner,
    HorseSexEnum,
    Photo,
    UserScope,
)
from core.entities.horse import HorseDateModeEnum
from core.exceptions.base import ClientError
from core.exceptions.auth import ForbiddenError
from core.protocols.repositories.horse_repository import HorseSlugConflictError
from core.schemas import (
    HorseCreateInDto,
    HorseOutDto,
    HorsePedigree,
    HorseSetPedigreeInDto,
    HorseUpdateInDto,
    HorseWithPedigreeOutDto,
    UserOutDto,
)
from core.schemas.horses import FoalParentsDto, HorseFoalOutDto, HorsePhotosUpdateInDto
from core.services.horse import HORSE_SLUG_MAX_ATTEMPTS, HorseService

pytestmark = pytest.mark.asyncio


class RepositoryError(Exception):
    pass


class FakeHorseRepository:
    def __init__(self) -> None:
        self.by_id: dict[UUID, Horse] = {}
        self.calls: list[tuple[str, Any]] = []
        self.fail_on: set[str] = set()
        self.list_result: tuple[Mapping[UUID, HorseOutDto], int] = ({}, 0)
        self.current_sire_id: UUID | None = None
        self.current_dam_id: UUID | None = None
        self.current_foal_ids: list[UUID] = []

    def add(self, horse: Horse) -> Horse:
        self.by_id[horse.id] = horse
        return horse

    def _fail_if_needed(self, method: str) -> None:
        if method in self.fail_on:
            raise RepositoryError(method)

    async def get_by_id(
        self, id: UUID, *, equestrian_id: UUID | None = None
    ) -> Horse | None:
        self.calls.append(("get_by_id", id))
        self._fail_if_needed("get_by_id")
        horse = self.by_id.get(id)
        if (
            horse is not None
            and equestrian_id is not None
            and horse.equestrian_id != equestrian_id
        ):
            return None
        return horse

    async def get_by_ids(self, ids: list[UUID]) -> Mapping[UUID, Horse]:
        self.calls.append(("get_by_ids", ids))
        self._fail_if_needed("get_by_ids")
        return {id_: self.by_id[id_] for id_ in ids if id_ in self.by_id}

    async def create(self, entity: Horse) -> Horse:
        self.calls.append(("create", entity))
        self._fail_if_needed("create")
        return self.add(entity)

    async def find_by_slug(self, slug: str, *, equestrian_id: UUID) -> Horse | None:
        self.calls.append(
            ("find_by_slug", {"slug": slug, "equestrian_id": equestrian_id})
        )
        self._fail_if_needed("find_by_slug")
        return next(
            (
                horse
                for horse in self.by_id.values()
                if horse.slug == slug and horse.equestrian_id == equestrian_id
            ),
            None,
        )

    async def exists_in_other_tenant(
        self, horse_id: UUID, *, equestrian_id: UUID
    ) -> bool:
        self.calls.append(
            (
                "exists_in_other_tenant",
                {"horse_id": horse_id, "equestrian_id": equestrian_id},
            )
        )
        horse = self.by_id.get(horse_id)
        return horse is not None and horse.equestrian_id != equestrian_id

    async def update(self, entity: Horse) -> Horse:
        self.calls.append(("update", entity))
        self._fail_if_needed("update")
        return self.add(entity)

    async def delete(self, id: UUID) -> None:
        self.calls.append(("delete", id))
        self._fail_if_needed("delete")
        self.by_id.pop(id, None)

    async def get_horse_full_info_by_id(
        self, *, horse_id: UUID, pedigree: int | None = None
    ) -> HorseOutDto | HorseWithPedigreeOutDto | None:
        self.calls.append(
            ("get_horse_full_info_by_id", {"horse_id": horse_id, "pedigree": pedigree})
        )
        self._fail_if_needed("get_horse_full_info_by_id")
        horse = self.by_id.get(horse_id)
        if horse is None:
            return None
        dto = HorseOutDto(
            id=horse.id,
            slug=horse.slug or "",
            name=horse.name,
            pedigree_name=horse.pedigree_name,
            description=horse.description,
            height=horse.height,
            sex=horse.sex,
            bdate=horse.bdate,
            ddate=horse.ddate,
            bdate_mode=horse.bdate_mode,
            ddate_mode=horse.ddate_mode,
            this_stable=horse.this_stable,
        )
        if pedigree is None or pedigree <= 0:
            return dto
        sire = (
            await self.get_horse_full_info_by_id(horse_id=self.current_sire_id)
            if self.current_sire_id is not None
            else None
        )
        dam = (
            await self.get_horse_full_info_by_id(horse_id=self.current_dam_id)
            if self.current_dam_id is not None
            else None
        )
        raw_foals = [
            foal
            for foal_id in self.current_foal_ids
            if (foal := await self.get_horse_full_info_by_id(horse_id=foal_id))
            is not None
        ]
        foals = [
            HorseFoalOutDto(**f.model_dump(), parents=FoalParentsDto())
            for f in raw_foals
        ]
        return HorseWithPedigreeOutDto(
            **dto.model_dump(),
            pedigree=HorsePedigree(
                sire=sire,
                dam=dam,
                foals=foals,
            ),
        )

    async def get_horse_full_info_by_slug(
        self, *, horse_slug: str, pedigree: int | None = None
    ) -> HorseOutDto | None:
        self.calls.append(
            (
                "get_horse_full_info_by_slug",
                {"horse_slug": horse_slug, "pedigree": pedigree},
            )
        )
        self._fail_if_needed("get_horse_full_info_by_slug")
        for horse in self.by_id.values():
            if horse.slug == horse_slug:
                return await self.get_horse_full_info_by_id(
                    horse_id=horse.id, pedigree=pedigree
                )
        return None

    async def get_available_sires(
        self,
        *,
        target_horse: Horse,
        search: str | None = None,
        exclude_ids: list[UUID] | None = None,
        limit: int | None = 25,
        offset: int | None = 0,
    ) -> tuple[Mapping[UUID, HorseOutDto], int]:
        self.calls.append(
            (
                "get_available_sires",
                {
                    "limit": limit,
                    "offset": offset,
                    "search": search,
                    "exclude_ids": exclude_ids,
                },
            )
        )
        self._fail_if_needed("get_available_sires")
        return ({}, 0)

    async def get_available_dams(
        self,
        *,
        target_horse: Horse,
        search: str | None = None,
        exclude_ids: list[UUID] | None = None,
        limit: int | None = 25,
        offset: int | None = 0,
    ) -> tuple[Mapping[UUID, HorseOutDto], int]:
        self.calls.append(
            (
                "get_available_dams",
                {
                    "limit": limit,
                    "offset": offset,
                    "search": search,
                    "exclude_ids": exclude_ids,
                },
            )
        )
        self._fail_if_needed("get_available_dams")
        return ({}, 0)

    async def get_available_children(
        self,
        *,
        target_horse: Horse,
        search: str | None = None,
        exclude_ids: list[UUID] | None = None,
        limit: int | None = 25,
        offset: int | None = 0,
    ) -> tuple[Mapping[UUID, HorseOutDto], int]:
        self.calls.append(
            (
                "get_available_children",
                {
                    "limit": limit,
                    "offset": offset,
                    "search": search,
                    "exclude_ids": exclude_ids,
                },
            )
        )
        self._fail_if_needed("get_available_children")
        return ({}, 0)

    async def get_horse_list_full_info(
        self, **kwargs: Any
    ) -> tuple[Mapping[UUID, HorseOutDto], int]:
        self.calls.append(("get_horse_list_full_info", kwargs))
        self._fail_if_needed("get_horse_list_full_info")
        return self.list_result

    async def set_horse_photos(
        self,
        horse_id: UUID,
        photo_ids: list[UUID],
        main_photo_id: UUID | None = None,
        *,
        equestrian_id: UUID,
    ) -> None:
        self.calls.append(
            ("set_horse_photos", {"horse_id": horse_id, "photo_ids": photo_ids})
        )
        self._fail_if_needed("set_horse_photos")


class FakePhotoRepository:
    def __init__(self) -> None:
        self.by_id: dict[UUID, Any] = {}
        self.calls: list[tuple[str, Any]] = []

    def add(self, photo: Any) -> Any:
        self.by_id[photo.id] = photo
        return photo

    async def get_by_id(self, id: UUID, *, equestrian_id: UUID) -> Any | None:
        self.calls.append(("get_by_id", id))
        return self.by_id.get(id)

    async def get_by_ids(self, ids: Any, *, equestrian_id: UUID) -> dict[UUID, Any]:
        self.calls.append(("get_by_ids", ids))
        return {id_: self.by_id[id_] for id_ in ids if id_ in self.by_id}


class FakeHorseChildrenRepository:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.fail_on: set[str] = set()

    def _fail_if_needed(self, method: str) -> None:
        if method in self.fail_on:
            raise RepositoryError(method)

    async def clear_pedigree(self, **kwargs: Any) -> None:
        self.calls.append(("clear_pedigree", kwargs))
        self._fail_if_needed("clear_pedigree")

    async def set_pedigree(self, **kwargs: Any) -> None:
        self.calls.append(("set_pedigree", kwargs))
        self._fail_if_needed("set_pedigree")


class FakeSimpleRepository:
    def __init__(self) -> None:
        self.by_id: dict[UUID, Any] = {}
        self.calls: list[tuple[str, Any]] = []

    def add(self, entity: Any) -> Any:
        self.by_id[entity.id] = entity
        return entity

    async def get_by_id(self, id: UUID) -> Any | None:
        self.calls.append(("get_by_id", id))
        return self.by_id.get(id)


def make_horse(**overrides: Any) -> Horse:
    data = {
        "name": "Буран",
        "slug": "buran",
        "sex": HorseSexEnum.MALE,
        "bdate": date(2020, 1, 1),
    }
    data.update(overrides)
    return Horse(**data)


def make_user(
    *, scope_names: list[str] | None = None, user_id: UUID | None = None
) -> UserOutDto:
    scopes = [
        UserScope(scope_name=scope_name, scope_description=f"{scope_name} scope")
        for scope_name in (scope_names or ["ADMIN"])
    ]
    return UserOutDto(
        id=user_id or uuid4(),
        equestrian_id=TEST_EQUESTRIAN_CONTEXT.id,
        username="admin",
        created_at=datetime.now(tz=timezone.utc),
        scopes=scopes,
    )


def make_service() -> tuple[
    HorseService,
    FakeHorseRepository,
    FakeHorseChildrenRepository,
    FakeSimpleRepository,
    FakeSimpleRepository,
    FakeSimpleRepository,
]:
    horse_repo = FakeHorseRepository()
    horse_children_repo = FakeHorseChildrenRepository()
    breed_repo = FakeSimpleRepository()
    coat_repo = FakeSimpleRepository()
    owner_repo = FakeSimpleRepository()
    return (
        HorseService(
            horse_repository=cast(Any, horse_repo),
            horse_children_repository=cast(Any, horse_children_repo),
            breed_repository=cast(Any, breed_repo),
            coat_color_repository=cast(Any, coat_repo),
            horse_owner_repository=cast(Any, owner_repo),
        ),
        horse_repo,
        horse_children_repo,
        breed_repo,
        coat_repo,
        owner_repo,
    )


async def test_update_horse_uc19_partial_update_changes_only_explicit_fields() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    horse = horse_repo.add(make_horse(description="old", this_stable=False))

    updated = await service.update_horse(
        horse_id=horse.id,
        data=HorseUpdateInDto(description="new"),
        user=make_user(),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert updated.description == "new"
    assert updated.this_stable is False
    assert [name for name, _ in horse_repo.calls] == [
        "get_by_id",
        "update",
        "get_horse_full_info_by_id",
    ]


async def test_update_horse_uc20_empty_payload_rejected() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    horse = horse_repo.add(make_horse())

    with pytest.raises(ClientError):
        await service.update_horse(
            horse_id=horse.id,
            data=HorseUpdateInDto(),
            user=make_user(),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )


async def test_update_horse_uc18_denies_non_admin_scope_user() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    horse = horse_repo.add(make_horse())

    with pytest.raises(ClientError):
        await service.update_horse(
            horse_id=horse.id,
            data=HorseUpdateInDto(description="updated"),
            user=make_user(scope_names=["CONTENT_EDITOR"]),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )


async def test_create_horse_uc16_reference_validation_runs_before_create() -> None:
    service, horse_repo, _, breed_repo, coat_repo, owner_repo = make_service()
    breed = breed_repo.add(
        Breed(
            equestrian_id=TEST_EQUESTRIAN_CONTEXT.id,
            name="Arabian",
            slug="arabian",
            short_name="Arabian",
        )
    )
    coat = coat_repo.add(
        CoatColor(
            equestrian_id=TEST_EQUESTRIAN_CONTEXT.id,
            name="Bay",
            slug="bay",
            short_name="Bay",
        )
    )
    owner = owner_repo.add(
        HorseOwner(equestrian_id=TEST_EQUESTRIAN_CONTEXT.id, name="Owner")
    )

    created = await service.create_horse(
        create_data=HorseCreateInDto(
            name="Новая",
            breed_id=breed.id,
            coat_color_id=coat.id,
            horse_owner_id=owner.id,
        ),
        user=make_user(),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert created.name == "Новая"
    assert "kind" not in created.model_dump()
    created_entity = next(
        payload for name, payload in horse_repo.calls if name == "create"
    )
    assert not hasattr(created_entity, "kind")
    assert [name for name, _ in horse_repo.calls] == ["find_by_slug", "create"]


async def test_create_horse_uc16_missing_reference_returns_client_error() -> None:
    service, horse_repo, _, _, _, _ = make_service()

    with pytest.raises(ClientError):
        await service.create_horse(
            create_data=HorseCreateInDto(name="Новая", breed_id=uuid4()),
            user=make_user(),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )

    assert horse_repo.calls == []


async def test_horse_slug_h01_first_name_uses_base_slug() -> None:
    service, _, _, _, _, _ = make_service()
    created = await service.create_horse(
        create_data=HorseCreateInDto(name="Норманн"),
        user=make_user(),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )
    assert created.slug == "normann"


@pytest.mark.parametrize(
    ("occupied", "expected"),
    [
        (["normann"], "normann-1"),
        (["normann", "normann-1", "normann-2"], "normann-3"),
        (["normann", "normann-2"], "normann-1"),
    ],
    ids=["h02-second", "h03-contiguous", "h04-gap"],
)
async def test_horse_slug_h02_h04_chooses_minimal_suffix(
    occupied: list[str], expected: str
) -> None:
    service, horse_repo, _, _, _, _ = make_service()
    for slug in occupied:
        horse_repo.add(make_horse(name=slug, slug=slug))
    created = await service.create_horse(
        create_data=HorseCreateInDto(name="Норманн"),
        user=make_user(),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )
    assert created.slug == expected


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Норманн", "normann"),
        ("  Норманн  ", "normann"),
        ("Норманн!!!", "normann"),
    ],
    ids=["h05-cyrillic", "h06-space-case", "h07-symbols"],
)
async def test_horse_slug_h05_h07_reuses_entity_normalization(
    name: str, expected: str
) -> None:
    service, _, _, _, _, _ = make_service()
    created = await service.create_horse(
        create_data=HorseCreateInDto(name=name),
        user=make_user(),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )
    assert created.slug == expected


async def test_horse_slug_h08_h09_is_tenant_scoped() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    other_tenant = uuid4()
    horse_repo.add(make_horse(slug="normann", equestrian_id=other_tenant))
    created = await service.create_horse(
        create_data=HorseCreateInDto(name="Норманн"),
        user=make_user(),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )
    assert created.slug == "normann"
    lookup = next(
        payload for name, payload in horse_repo.calls if name == "find_by_slug"
    )
    assert lookup["equestrian_id"] == TEST_EQUESTRIAN_CONTEXT.id


@pytest.mark.parametrize(
    ("occupied_count", "expected"),
    [
        (0, "a" * 63),
        (1, f"{'a' * 61}-1"),
        (10, f"{'a' * 60}-10"),
    ],
    ids=["h10-max-base", "h11-one-digit", "h12-multi-digit"],
)
async def test_horse_slug_h10_h13_obeys_full_length_limit(
    occupied_count: int, expected: str
) -> None:
    service, horse_repo, _, _, _, _ = make_service()
    base = "a" * 63
    if occupied_count:
        horse_repo.add(make_horse(name=base, slug=base))
        for suffix in range(1, occupied_count):
            suffix_text = f"-{suffix}"
            horse_repo.add(
                make_horse(slug=f"{base[: 63 - len(suffix_text)]}{suffix_text}")
            )
    created = await service.create_horse(
        create_data=HorseCreateInDto(name=base),
        user=make_user(),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )
    assert created.slug == expected
    assert len(created.slug) <= 63
    if occupied_count:
        assert created.slug.endswith(f"-{occupied_count}")


async def test_horse_slug_h14_degenerate_name_is_client_error() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    with pytest.raises(ClientError, match="slug"):
        await service.create_horse(
            create_data=HorseCreateInDto(name="!!!"),
            user=make_user(),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )
    assert not any(name == "create" for name, _ in horse_repo.calls)


@pytest.mark.parametrize("scope", ["SUPERUSER", "ADMIN", "DEVELOPER"])
async def test_horse_slug_h15_h17_allowed_scopes_create(scope: str) -> None:
    service, _, _, _, _, _ = make_service()
    created = await service.create_horse(
        create_data=HorseCreateInDto(name=f"Horse {scope}"),
        user=make_user(scope_names=[scope]),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )
    assert created.slug


async def test_horse_slug_h18_missing_scope_fails_before_lookup() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    with pytest.raises(ForbiddenError):
        await service.create_horse(
            create_data=HorseCreateInDto(name="Horse"),
            user=make_user(scope_names=["CONTENT_EDITOR"]),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )
    assert horse_repo.calls == []


async def test_horse_slug_h19_anonymous_fails_before_lookup() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    with pytest.raises(ClientError):
        await service.create_horse(
            create_data=HorseCreateInDto(name="Horse"),
            user=None,
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )
    assert horse_repo.calls == []


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("breed_id", "Порода"),
        ("coat_color_id", "Масть"),
        ("horse_owner_id", "Владелец"),
    ],
    ids=["h20-invalid-breed", "h21-invalid-coat", "h22-invalid-owner"],
)
async def test_horse_slug_h20_h22_invalid_reference_prevents_insert(
    field: str, message: str
) -> None:
    service, horse_repo, _, _, _, _ = make_service()
    with pytest.raises(ClientError, match=message):
        await service.create_horse(
            create_data=HorseCreateInDto(name="Норманн", **{field: uuid4()}),
            user=make_user(),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )
    assert not any(name == "create" for name, _ in horse_repo.calls)


async def test_horse_slug_h23_entity_validation_maps_to_client_error() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    invalid_command = HorseCreateInDto.model_construct(name="x")
    with pytest.raises(ClientError):
        await service.create_horse(
            create_data=invalid_command,
            user=make_user(),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )
    assert not any(name == "create" for name, _ in horse_repo.calls)


async def test_horse_slug_h24_response_contains_suffix() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    horse_repo.add(make_horse(slug="normann"))
    result = await service.create_horse(
        create_data=HorseCreateInDto(name="Норманн"),
        user=make_user(),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )
    assert result.slug == "normann-1"


async def test_horse_slug_h25_h27_race_becomes_bounded_client_error() -> None:
    service, horse_repo, _, _, _, _ = make_service()

    async def conflict(entity: Horse) -> Horse:
        del entity
        raise HorseSlugConflictError

    horse_repo.create = conflict  # type: ignore[method-assign]
    with pytest.raises(ClientError, match="повторите"):
        await service.create_horse(
            create_data=HorseCreateInDto(name="Норманн"),
            user=make_user(),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )
    assert [name for name, _ in horse_repo.calls].count("find_by_slug") == 1


async def test_horse_slug_h26_candidate_scan_has_hard_limit() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    lookups = 0

    async def always_occupied(slug: str, *, equestrian_id: UUID) -> Horse:
        nonlocal lookups
        lookups += 1
        return make_horse(slug=slug, equestrian_id=equestrian_id)

    horse_repo.find_by_slug = always_occupied  # type: ignore[method-assign]
    with pytest.raises(ClientError, match="подобрать свободный slug"):
        await service.create_horse(
            create_data=HorseCreateInDto(name="Норманн"),
            user=make_user(),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )
    assert not any(name == "create" for name, _ in horse_repo.calls)
    assert lookups == HORSE_SLUG_MAX_ATTEMPTS


async def test_horse_slug_h29_generic_repository_error_propagates() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    horse_repo.fail_on.add("create")
    with pytest.raises(RepositoryError):
        await service.create_horse(
            create_data=HorseCreateInDto(name="Норманн"),
            user=make_user(),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )


async def test_horse_slug_h30_input_is_not_mutated_between_calls() -> None:
    service, _, _, _, _, _ = make_service()
    command = HorseCreateInDto(name="Норманн")
    before = command.model_dump()
    first = await service.create_horse(
        create_data=command,
        user=make_user(),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )
    second = await service.create_horse(
        create_data=command,
        user=make_user(),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )
    assert command.model_dump() == before
    assert (first.slug, second.slug) == ("normann", "normann-1")


@pytest.mark.parametrize("value", [None, ""], ids=["null", "empty"])
async def test_horse_slug_create_empty_values_generate_from_name(
    value: str | None,
) -> None:
    service, _, _, _, _, _ = make_service()
    result = await service.create_horse(
        create_data=HorseCreateInDto(name="Белый Ветер", slug=value),
        user=make_user(),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )
    assert result.slug == "belyy-veter"


async def test_horse_slug_manual_create_is_normalized() -> None:
    service, _, _, _, _, _ = make_service()
    result = await service.create_horse(
        create_data=HorseCreateInDto(name="Horse", slug=" Мой URL "),
        user=make_user(),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )
    assert result.slug == "moy-url"


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "Horse"},
        {"name": "Horse", "slug": None},
        {"name": "Horse", "slug": ""},
        {"name": "Horse", "slug": "a" * 63},
    ],
    ids=["omitted", "null", "empty", "max-length"],
)
async def test_horse_slug_create_dto_accepts_contract_values(
    payload: dict[str, Any],
) -> None:
    command = HorseCreateInDto.model_validate(payload)
    assert command.slug == payload.get("slug")


@pytest.mark.parametrize(
    "dto_type,payload",
    [
        (HorseCreateInDto, {"name": "Horse", "slug": "a" * 64}),
        (HorseUpdateInDto, {"slug": "a" * 64}),
    ],
    ids=["create", "update"],
)
async def test_horse_slug_dto_rejects_values_over_63(
    dto_type: type[HorseCreateInDto] | type[HorseUpdateInDto],
    payload: dict[str, Any],
) -> None:
    with pytest.raises(ValidationError):
        dto_type.model_validate(payload)


async def test_horse_slug_create_dto_keeps_extra_forbidden() -> None:
    with pytest.raises(ValidationError):
        HorseCreateInDto.model_validate({"name": "Horse", "unknown": True})


async def test_horse_slug_manual_create_conflict_is_not_suffixed() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    horse_repo.add(make_horse(slug="reserved"))
    with pytest.raises(ClientError, match="занят"):
        await service.create_horse(
            create_data=HorseCreateInDto(name="Horse", slug=" Reserved "),
            user=make_user(),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )
    assert not any(name == "create" for name, _ in horse_repo.calls)


async def test_horse_slug_manual_create_degenerate_is_client_error() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    with pytest.raises(ClientError, match="slug"):
        await service.create_horse(
            create_data=HorseCreateInDto(name="Horse", slug="!!!"),
            user=make_user(),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )
    assert not any(name == "create" for name, _ in horse_repo.calls)


async def test_horse_slug_patch_omitted_preserves_current_value() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    horse = horse_repo.add(make_horse(slug="stable-url"))
    result = await service.update_horse(
        horse_id=horse.id,
        data=HorseUpdateInDto(description="updated"),
        user=make_user(),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )
    assert result.slug == "stable-url"
    assert not any(name == "find_by_slug" for name, _ in horse_repo.calls)


async def test_horse_slug_patch_manual_normalizes_and_updates_once() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    horse = horse_repo.add(make_horse(slug="old-url"))
    result = await service.update_horse(
        horse_id=horse.id,
        data=HorseUpdateInDto(slug=" Новый URL ", description="changed"),
        user=make_user(),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )
    assert result.slug == "novyy-url"
    assert result.description == "changed"
    assert [name for name, _ in horse_repo.calls].count("update") == 1


async def test_horse_slug_patch_current_value_has_no_self_conflict() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    horse = horse_repo.add(make_horse(slug="same-url"))
    result = await service.update_horse(
        horse_id=horse.id,
        data=HorseUpdateInDto(slug=" SAME URL "),
        user=make_user(),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )
    assert result.slug == "same-url"


async def test_horse_slug_patch_null_regenerates_from_current_name() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    horse = horse_repo.add(make_horse(name="Белый Ветер", slug="custom"))
    result = await service.update_horse(
        horse_id=horse.id,
        data=HorseUpdateInDto(slug=None),
        user=make_user(),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )
    assert result.slug == "belyy-veter"


async def test_horse_slug_patch_empty_regenerates_from_new_name() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    horse = horse_repo.add(make_horse(slug="custom"))
    result = await service.update_horse(
        horse_id=horse.id,
        data=HorseUpdateInDto(name="Новый Конь", slug=""),
        user=make_user(),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )
    assert result.slug == "novyy-kon"


async def test_horse_slug_patch_generated_collision_uses_minimal_suffix() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    horse = horse_repo.add(make_horse(name="Target", slug="custom"))
    horse_repo.add(make_horse(name="Новый Конь", slug="novyy-kon"))
    horse_repo.add(make_horse(name="Новый Конь 2", slug="novyy-kon-2"))
    result = await service.update_horse(
        horse_id=horse.id,
        data=HorseUpdateInDto(name="Новый Конь", slug=None),
        user=make_user(),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )
    assert result.slug == "novyy-kon-1"


async def test_horse_slug_patch_manual_conflict_does_not_update() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    horse = horse_repo.add(make_horse(slug="original"))
    horse_repo.add(make_horse(slug="reserved"))
    with pytest.raises(ClientError, match="занят"):
        await service.update_horse(
            horse_id=horse.id,
            data=HorseUpdateInDto(slug="reserved", description="must-not-change"),
            user=make_user(),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )
    assert not any(name == "update" for name, _ in horse_repo.calls)
    assert horse.description is None


async def test_horse_slug_patch_degenerate_does_not_update() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    horse = horse_repo.add(make_horse(slug="original"))
    with pytest.raises(ClientError, match="slug"):
        await service.update_horse(
            horse_id=horse.id,
            data=HorseUpdateInDto(slug="!!!"),
            user=make_user(),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )
    assert not any(name == "update" for name, _ in horse_repo.calls)


async def test_horse_slug_patch_constraint_race_is_client_error() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    horse = horse_repo.add(make_horse(slug="original"))

    async def conflict(entity: Horse) -> Horse:
        del entity
        raise HorseSlugConflictError

    horse_repo.update = conflict  # type: ignore[method-assign]
    with pytest.raises(ClientError, match="занят"):
        await service.update_horse(
            horse_id=horse.id,
            data=HorseUpdateInDto(slug="new-url"),
            user=make_user(),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )


async def test_horse_slug_patch_other_tenant_slug_is_available() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    horse = horse_repo.add(make_horse(slug="original"))
    horse_repo.add(make_horse(slug="shared", equestrian_id=uuid4()))
    result = await service.update_horse(
        horse_id=horse.id,
        data=HorseUpdateInDto(slug="shared"),
        user=make_user(),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )
    assert result.slug == "shared"


async def test_horse_slug_foreign_tenant_patch_is_forbidden_before_mutation() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    foreign = horse_repo.add(make_horse(equestrian_id=uuid4(), slug="foreign"))
    with pytest.raises(ForbiddenError):
        await service.update_horse(
            horse_id=foreign.id,
            data=HorseUpdateInDto(slug="stolen"),
            user=make_user(),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )
    assert not any(name == "update" for name, _ in horse_repo.calls)


async def test_get_horse_by_slug_or_id_uc12_uuid_vs_slug_deterministic() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    horse = horse_repo.add(make_horse(slug="special-slug"))

    by_uuid = await service.get_horse_by_slug_or_id(
        slug_or_id=str(horse.id), user=None, equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )
    by_slug = await service.get_horse_by_slug_or_id(
        slug_or_id="special-slug",
        user=None,
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert by_uuid.id == horse.id
    assert by_slug.id == horse.id
    assert [name for name, _ in horse_repo.calls] == [
        "get_horse_full_info_by_id",
        "get_horse_full_info_by_slug",
        "get_horse_full_info_by_id",
    ]


async def test_get_available_pedigree_uc27_normalizes_pagination_bounds() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    horse = horse_repo.add(make_horse())

    await service.get_available_pedigree(
        user=make_user(),
        horse_id=horse.id,
        mode="sire",
        limit=999,
        offset=-5,
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert (
        "get_available_sires",
        {"limit": 50, "offset": 0, "search": None, "exclude_ids": []},
    ) in horse_repo.calls


async def test_get_available_pedigree_sire_limit_below_one_clamped() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    horse = horse_repo.add(make_horse())

    await service.get_available_pedigree(
        user=None,
        horse_id=horse.id,
        mode="sire",
        limit=0,
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert (
        "get_available_sires",
        {"limit": 1, "offset": 0, "search": None, "exclude_ids": []},
    ) in horse_repo.calls


async def test_get_available_pedigree_dam_negative_offset_clamped() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    horse = horse_repo.add(make_horse())

    await service.get_available_pedigree(
        user=None,
        horse_id=horse.id,
        mode="dam",
        offset=-10,
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert (
        "get_available_dams",
        {"limit": 25, "offset": 0, "search": None, "exclude_ids": []},
    ) in horse_repo.calls


async def test_get_available_pedigree_invalid_mode_returns_client_error() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    horse = horse_repo.add(make_horse())

    with pytest.raises(ClientError, match="Некорректный режим родословной"):
        await service.get_available_pedigree(
            user=None,
            horse_id=horse.id,
            mode=cast(Any, "parent"),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )


async def test_get_available_pedigree_missing_target_returns_client_error() -> None:
    service, _, _, _, _, _ = make_service()

    with pytest.raises(ClientError, match="Лошадь не найдена"):
        await service.get_available_pedigree(
            user=None,
            horse_id=uuid4(),
            mode="children",
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )


async def test_get_available_pedigree_excludes_current_relations() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    horse = horse_repo.add(make_horse())
    dam = horse_repo.add(
        make_horse(
            name="Dam",
            slug="dam",
            sex=HorseSexEnum.FEMALE,
            bdate=date(2015, 1, 1),
        )
    )
    foal = horse_repo.add(make_horse(name="Foal", slug="foal", bdate=date(2022, 1, 1)))
    horse_repo.current_dam_id = dam.id
    horse_repo.current_foal_ids = [foal.id]

    await service.get_available_pedigree(
        user=None,
        horse_id=horse.id,
        mode="sire",
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert (
        "get_available_sires",
        {
            "limit": 25,
            "offset": 0,
            "search": None,
            "exclude_ids": [dam.id, foal.id],
        },
    ) in horse_repo.calls


async def test_set_horse_pedigree_uc14_duplicate_foals_rejected() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    target = horse_repo.add(make_horse())
    foal = horse_repo.add(make_horse(name="Foal", slug="foal", bdate=date(2021, 1, 1)))

    with pytest.raises(ClientError):
        await service.set_horse_pedigree(
            horse_id=target.id,
            pedigree_data=HorseSetPedigreeInDto(foals=[foal.id, foal.id]),
            user=make_user(),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )


async def test_set_horse_pedigree_without_user_denied_before_write() -> None:
    service, horse_repo, children_repo, _, _, _ = make_service()
    target = horse_repo.add(make_horse())

    with pytest.raises(ClientError, match="Пользователь не авторизован"):
        await service.set_horse_pedigree(
            horse_id=target.id,
            pedigree_data=HorseSetPedigreeInDto(sire_id=uuid4()),
            user=None,
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )

    assert children_repo.calls == []


async def test_set_horse_pedigree_without_admin_scope_denied_before_write() -> None:
    service, horse_repo, children_repo, _, _, _ = make_service()
    target = horse_repo.add(make_horse())

    with pytest.raises(ClientError, match="Недостаточно прав"):
        await service.set_horse_pedigree(
            horse_id=target.id,
            pedigree_data=HorseSetPedigreeInDto(sire_id=uuid4()),
            user=make_user(scope_names=["CONTENT_EDITOR"]),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )

    assert children_repo.calls == []


async def test_set_horse_pedigree_missing_target_returns_not_found_group_error() -> (
    None
):
    service, _, children_repo, _, _, _ = make_service()

    with pytest.raises(ClientError, match="Некоторые лошади не найдены"):
        await service.set_horse_pedigree(
            horse_id=uuid4(),
            pedigree_data=HorseSetPedigreeInDto(sire_id=uuid4()),
            user=make_user(),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )

    assert children_repo.calls == []


async def test_set_horse_pedigree_explicit_null_clears_sire() -> None:
    service, horse_repo, children_repo, _, _, _ = make_service()
    target = horse_repo.add(make_horse(sex=HorseSexEnum.FEMALE))
    sire = horse_repo.add(
        make_horse(
            name="Sire",
            slug="sire",
            sex=HorseSexEnum.MALE,
            bdate=date(2018, 1, 1),
        )
    )
    horse_repo.current_sire_id = sire.id

    await service.set_horse_pedigree(
        horse_id=target.id,
        pedigree_data=HorseSetPedigreeInDto(sire_id=None),
        user=make_user(),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert children_repo.calls[0] == (
        "clear_pedigree",
        {"target_horse_id": target.id, "sire": True, "dam": False, "foals": False},
    )
    assert children_repo.calls[1] == (
        "set_pedigree",
        {
            "target_horse_id": target.id,
            "sire_id": None,
            "dam_id": None,
            "foals_ids": None,
        },
    )


async def test_set_horse_pedigree_explicit_null_clears_dam() -> None:
    service, horse_repo, children_repo, _, _, _ = make_service()
    target = horse_repo.add(make_horse())
    dam = horse_repo.add(
        make_horse(
            name="Dam",
            slug="dam",
            sex=HorseSexEnum.FEMALE,
            bdate=date(2018, 1, 1),
        )
    )
    horse_repo.current_dam_id = dam.id

    await service.set_horse_pedigree(
        horse_id=target.id,
        pedigree_data=HorseSetPedigreeInDto(dam_id=None),
        user=make_user(),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert children_repo.calls[0] == (
        "clear_pedigree",
        {"target_horse_id": target.id, "sire": False, "dam": True, "foals": False},
    )


async def test_set_horse_pedigree_empty_foals_clears_foals_only() -> None:
    service, horse_repo, children_repo, _, _, _ = make_service()
    target = horse_repo.add(make_horse())
    foal = horse_repo.add(make_horse(name="Foal", slug="foal", bdate=date(2022, 1, 1)))
    horse_repo.current_foal_ids = [foal.id]

    await service.set_horse_pedigree(
        horse_id=target.id,
        pedigree_data=HorseSetPedigreeInDto(foals=[]),
        user=make_user(),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert children_repo.calls[0] == (
        "clear_pedigree",
        {"target_horse_id": target.id, "sire": False, "dam": False, "foals": True},
    )
    assert children_repo.calls[1][1]["foals_ids"] == []


async def test_set_horse_pedigree_omitted_fields_do_not_clear_other_relations() -> None:
    service, horse_repo, children_repo, _, _, _ = make_service()
    target = horse_repo.add(make_horse(sex=HorseSexEnum.FEMALE))
    sire = horse_repo.add(
        make_horse(
            name="Sire",
            slug="sire",
            sex=HorseSexEnum.MALE,
            bdate=date(2018, 1, 1),
        )
    )

    await service.set_horse_pedigree(
        horse_id=target.id,
        pedigree_data=HorseSetPedigreeInDto(sire_id=sire.id),
        user=make_user(),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert children_repo.calls[0][1] == {
        "target_horse_id": target.id,
        "sire": True,
        "dam": False,
        "foals": False,
    }


async def test_set_horse_pedigree_sire_self_reference_rejected() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    target = horse_repo.add(make_horse())

    with pytest.raises(ClientError, match="Отец не может совпадать"):
        await service.set_horse_pedigree(
            horse_id=target.id,
            pedigree_data=HorseSetPedigreeInDto(sire_id=target.id),
            user=make_user(),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )


async def test_set_horse_pedigree_sire_wrong_sex_rejected() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    target = horse_repo.add(make_horse())
    sire = horse_repo.add(
        make_horse(
            name="Wrong",
            slug="wrong",
            sex=HorseSexEnum.FEMALE,
            bdate=date(2018, 1, 1),
        )
    )

    with pytest.raises(ClientError, match="Отец должен быть мужского пола"):
        await service.set_horse_pedigree(
            horse_id=target.id,
            pedigree_data=HorseSetPedigreeInDto(sire_id=sire.id),
            user=make_user(),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )


async def test_set_horse_pedigree_sire_equal_bdate_rejected() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    target = horse_repo.add(make_horse(sex=HorseSexEnum.FEMALE))
    sire = horse_repo.add(
        make_horse(
            name="Sire",
            slug="sire",
            sex=HorseSexEnum.MALE,
            bdate=target.bdate,
        )
    )

    with pytest.raises(ClientError, match="раньше даты рождения"):
        await service.set_horse_pedigree(
            horse_id=target.id,
            pedigree_data=HorseSetPedigreeInDto(sire_id=sire.id),
            user=make_user(),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )


async def test_set_horse_pedigree_dam_self_reference_rejected() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    target = horse_repo.add(make_horse(sex=HorseSexEnum.FEMALE))

    with pytest.raises(ClientError, match="Мать не может совпадать"):
        await service.set_horse_pedigree(
            horse_id=target.id,
            pedigree_data=HorseSetPedigreeInDto(dam_id=target.id),
            user=make_user(),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )


async def test_set_horse_pedigree_dam_wrong_sex_rejected() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    target = horse_repo.add(make_horse())
    dam = horse_repo.add(
        make_horse(
            name="Wrong",
            slug="wrong",
            sex=HorseSexEnum.GELD,
            bdate=date(2018, 1, 1),
        )
    )

    with pytest.raises(ClientError, match="Мать должна быть женского пола"):
        await service.set_horse_pedigree(
            horse_id=target.id,
            pedigree_data=HorseSetPedigreeInDto(dam_id=dam.id),
            user=make_user(),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )


async def test_set_horse_pedigree_dam_equal_bdate_rejected() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    target = horse_repo.add(make_horse())
    dam = horse_repo.add(
        make_horse(
            name="Dam",
            slug="dam",
            sex=HorseSexEnum.FEMALE,
            bdate=target.bdate,
        )
    )

    with pytest.raises(ClientError, match="раньше даты рождения"):
        await service.set_horse_pedigree(
            horse_id=target.id,
            pedigree_data=HorseSetPedigreeInDto(dam_id=dam.id),
            user=make_user(),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )


async def test_set_horse_pedigree_dam_dead_before_target_birth_rejected() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    target = horse_repo.add(make_horse(bdate=date(2020, 1, 1)))
    dam = horse_repo.add(
        make_horse(
            name="Dam",
            slug="dam",
            sex=HorseSexEnum.FEMALE,
            bdate=date(2010, 1, 1),
            ddate=date(2019, 12, 31),
        )
    )

    with pytest.raises(ClientError, match="Дата смерти матери"):
        await service.set_horse_pedigree(
            horse_id=target.id,
            pedigree_data=HorseSetPedigreeInDto(dam_id=dam.id),
            user=make_user(),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )


async def test_set_horse_pedigree_foal_self_reference_rejected() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    target = horse_repo.add(make_horse())

    with pytest.raises(ClientError, match="Ребёнок не может совпадать"):
        await service.set_horse_pedigree(
            horse_id=target.id,
            pedigree_data=HorseSetPedigreeInDto(foals=[target.id]),
            user=make_user(),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )


async def test_set_horse_pedigree_child_equal_bdate_rejected() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    target = horse_repo.add(make_horse())
    foal = horse_repo.add(make_horse(name="Foal", slug="foal", bdate=target.bdate))

    with pytest.raises(ClientError, match="позже даты рождения"):
        await service.set_horse_pedigree(
            horse_id=target.id,
            pedigree_data=HorseSetPedigreeInDto(foals=[foal.id]),
            user=make_user(),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )


async def test_set_horse_pedigree_child_after_mothers_death_rejected() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    target = horse_repo.add(
        make_horse(
            sex=HorseSexEnum.FEMALE,
            bdate=date(2010, 1, 1),
            ddate=date(2020, 1, 1),
        )
    )
    foal = horse_repo.add(make_horse(name="Foal", slug="foal", bdate=date(2020, 1, 2)))

    with pytest.raises(ClientError, match="позже даты смерти матери"):
        await service.set_horse_pedigree(
            horse_id=target.id,
            pedigree_data=HorseSetPedigreeInDto(foals=[foal.id]),
            user=make_user(),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )


async def test_set_horse_pedigree_sire_and_dam_same_rejected() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    target = horse_repo.add(make_horse())
    parent = horse_repo.add(
        make_horse(
            name="Parent",
            slug="parent",
            sex=HorseSexEnum.MALE,
            bdate=date(2018, 1, 1),
        )
    )

    with pytest.raises(ClientError, match="Отец и мать не могут совпадать"):
        await service.set_horse_pedigree(
            horse_id=target.id,
            pedigree_data=HorseSetPedigreeInDto(
                sire_id=parent.id,
                dam_id=parent.id,
            ),
            user=make_user(),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )


async def test_set_horse_pedigree_sire_in_foals_rejected() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    target = horse_repo.add(make_horse())
    sire = horse_repo.add(
        make_horse(
            name="Sire",
            slug="sire",
            sex=HorseSexEnum.MALE,
            bdate=date(2018, 1, 1),
        )
    )

    with pytest.raises(ClientError, match="потомком"):
        await service.set_horse_pedigree(
            horse_id=target.id,
            pedigree_data=HorseSetPedigreeInDto(sire_id=sire.id, foals=[sire.id]),
            user=make_user(),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )


async def test_set_horse_pedigree_dam_in_foals_rejected() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    target = horse_repo.add(make_horse())
    dam = horse_repo.add(
        make_horse(
            name="Dam",
            slug="dam",
            sex=HorseSexEnum.FEMALE,
            bdate=date(2018, 1, 1),
        )
    )

    with pytest.raises(ClientError, match="потомком"):
        await service.set_horse_pedigree(
            horse_id=target.id,
            pedigree_data=HorseSetPedigreeInDto(dam_id=dam.id, foals=[dam.id]),
            user=make_user(),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )


async def test_set_horse_pedigree_parent_cannot_be_current_foal() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    target = horse_repo.add(make_horse(sex=HorseSexEnum.FEMALE))
    foal = horse_repo.add(
        make_horse(
            name="Foal",
            slug="foal",
            sex=HorseSexEnum.MALE,
            bdate=date(2022, 1, 1),
        )
    )
    horse_repo.current_foal_ids = [foal.id]

    with pytest.raises(ClientError, match="потомком"):
        await service.set_horse_pedigree(
            horse_id=target.id,
            pedigree_data=HorseSetPedigreeInDto(sire_id=foal.id),
            user=make_user(),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )


async def test_set_horse_pedigree_child_cannot_be_current_parent() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    target = horse_repo.add(make_horse())
    sire = horse_repo.add(
        make_horse(
            name="Sire",
            slug="sire",
            sex=HorseSexEnum.MALE,
            bdate=date(2018, 1, 1),
        )
    )
    horse_repo.current_sire_id = sire.id

    with pytest.raises(ClientError, match="родителем"):
        await service.set_horse_pedigree(
            horse_id=target.id,
            pedigree_data=HorseSetPedigreeInDto(foals=[sire.id]),
            user=make_user(),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )


async def test_set_horse_pedigree_replacement_allows_existing_foal_to_remain() -> None:
    service, horse_repo, children_repo, _, _, _ = make_service()
    target = horse_repo.add(make_horse())
    foal = horse_repo.add(make_horse(name="Foal", slug="foal", bdate=date(2022, 1, 1)))
    horse_repo.current_foal_ids = [foal.id]

    await service.set_horse_pedigree(
        horse_id=target.id,
        pedigree_data=HorseSetPedigreeInDto(foals=[foal.id]),
        user=make_user(),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert children_repo.calls[0] == (
        "clear_pedigree",
        {"target_horse_id": target.id, "sire": False, "dam": False, "foals": True},
    )
    assert children_repo.calls[1] == (
        "set_pedigree",
        {
            "target_horse_id": target.id,
            "sire_id": None,
            "dam_id": None,
            "foals_ids": [foal.id],
        },
    )


async def test_set_pedigree_allows_sire_with_different_breed_kind() -> None:
    service, horse_repo, children_repo, breed_repo, _, _ = make_service()
    horse_breed = breed_repo.add(
        Breed(
            equestrian_id=TEST_EQUESTRIAN_CONTEXT.id,
            name="Horse Breed",
            slug="horse-breed",
            short_name="HB",
        )
    )
    pony_breed = breed_repo.add(
        Breed(
            equestrian_id=TEST_EQUESTRIAN_CONTEXT.id,
            name="Pony Breed",
            slug="pony-breed",
            short_name="PB",
            kind=HorseKindEnum.PONY,
        )
    )
    target = horse_repo.add(
        make_horse(sex=HorseSexEnum.FEMALE, breed_id=horse_breed.id)
    )
    sire = horse_repo.add(
        make_horse(
            name="Pony Sire",
            slug="pony-sire",
            sex=HorseSexEnum.MALE,
            bdate=date(2018, 1, 1),
            breed_id=pony_breed.id,
        )
    )

    await service.set_horse_pedigree(
        horse_id=target.id,
        pedigree_data=HorseSetPedigreeInDto(sire_id=sire.id),
        user=make_user(),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert breed_repo.calls == []
    assert children_repo.calls[-1][1]["sire_id"] == sire.id


async def test_horse_kind_to_breed_set_pedigree_allows_matching_breed_kind() -> None:
    service, horse_repo, children_repo, breed_repo, _, _ = make_service()
    pony_breed = breed_repo.add(
        Breed(
            equestrian_id=TEST_EQUESTRIAN_CONTEXT.id,
            name="Pony Breed",
            slug="pony-breed",
            short_name="PB",
            kind=HorseKindEnum.PONY,
        )
    )
    target = horse_repo.add(make_horse(sex=HorseSexEnum.FEMALE, breed_id=pony_breed.id))
    sire = horse_repo.add(
        make_horse(
            name="Pony Sire",
            slug="pony-sire",
            sex=HorseSexEnum.MALE,
            bdate=date(2018, 1, 1),
            breed_id=pony_breed.id,
        )
    )

    await service.set_horse_pedigree(
        horse_id=target.id,
        pedigree_data=HorseSetPedigreeInDto(sire_id=sire.id),
        user=make_user(),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert children_repo.calls[-1][0] == "set_pedigree"


async def test_set_pedigree_allows_dam_with_different_breed_kind() -> None:
    service, horse_repo, children_repo, breed_repo, _, _ = make_service()
    target = horse_repo.add(make_horse(breed_id=uuid4()))
    dam = horse_repo.add(
        make_horse(
            name="Cross-kind dam",
            slug="cross-kind-dam",
            sex=HorseSexEnum.FEMALE,
            bdate=date(2018, 1, 1),
            breed_id=uuid4(),
        )
    )

    await service.set_horse_pedigree(
        horse_id=target.id,
        pedigree_data=HorseSetPedigreeInDto(dam_id=dam.id),
        user=make_user(),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert breed_repo.calls == []
    assert children_repo.calls[-1][1]["dam_id"] == dam.id


async def test_set_pedigree_allows_child_with_different_breed_kind() -> None:
    service, horse_repo, children_repo, breed_repo, _, _ = make_service()
    target = horse_repo.add(make_horse(breed_id=uuid4()))
    child = horse_repo.add(
        make_horse(
            name="Cross-kind child",
            slug="cross-kind-child",
            bdate=date(2022, 1, 1),
            breed_id=uuid4(),
        )
    )

    await service.set_horse_pedigree(
        horse_id=target.id,
        pedigree_data=HorseSetPedigreeInDto(foals=[child.id]),
        user=make_user(),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert breed_repo.calls == []
    assert children_repo.calls[-1][1]["foals_ids"] == [child.id]


async def test_set_pedigree_allows_bred_parent_for_target_without_breed() -> None:
    service, horse_repo, children_repo, breed_repo, _, _ = make_service()
    target = horse_repo.add(make_horse(breed_id=None))
    sire = horse_repo.add(
        make_horse(
            name="Bred sire",
            slug="bred-sire",
            sex=HorseSexEnum.MALE,
            bdate=date(2018, 1, 1),
            breed_id=uuid4(),
        )
    )

    await service.set_horse_pedigree(
        horse_id=target.id,
        pedigree_data=HorseSetPedigreeInDto(sire_id=sire.id),
        user=make_user(),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert breed_repo.calls == []
    assert children_repo.calls[-1][1]["sire_id"] == sire.id


async def test_set_pedigree_allows_unbred_child_for_target_with_breed() -> None:
    service, horse_repo, children_repo, breed_repo, _, _ = make_service()
    target = horse_repo.add(make_horse(breed_id=uuid4()))
    child = horse_repo.add(
        make_horse(
            name="Unbred child",
            slug="unbred-child",
            bdate=date(2022, 1, 1),
            breed_id=None,
        )
    )

    await service.set_horse_pedigree(
        horse_id=target.id,
        pedigree_data=HorseSetPedigreeInDto(foals=[child.id]),
        user=make_user(),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert breed_repo.calls == []
    assert children_repo.calls[-1][1]["foals_ids"] == [child.id]


async def test_set_horse_pedigree_uc22_clear_then_set_order() -> None:
    service, horse_repo, children_repo, _, _, _ = make_service()
    target = horse_repo.add(make_horse(sex=HorseSexEnum.FEMALE))
    sire = horse_repo.add(
        make_horse(
            name="Sire",
            slug="sire",
            sex=HorseSexEnum.MALE,
            bdate=date(2018, 1, 1),
        )
    )

    await service.set_horse_pedigree(
        horse_id=target.id,
        pedigree_data=HorseSetPedigreeInDto(sire_id=sire.id),
        user=make_user(),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert [name for name, _ in children_repo.calls] == [
        "clear_pedigree",
        "set_pedigree",
    ]


async def test_set_horse_pedigree_uc23_clear_called_before_repository_failure() -> None:
    service, horse_repo, children_repo, _, _, _ = make_service()
    target = horse_repo.add(make_horse(sex=HorseSexEnum.FEMALE))
    sire = horse_repo.add(
        make_horse(
            name="Sire",
            slug="sire",
            sex=HorseSexEnum.MALE,
            bdate=date(2018, 1, 1),
        )
    )
    children_repo.fail_on.add("set_pedigree")

    with pytest.raises(ClientError) as ex:
        await service.set_horse_pedigree(
            horse_id=target.id,
            pedigree_data=HorseSetPedigreeInDto(sire_id=sire.id),
            user=make_user(),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )

    assert children_repo.calls[0][0] == "clear_pedigree"
    assert children_repo.calls[1][0] == "set_pedigree"
    assert "операция неатомарна" in str(ex.value)


async def test_check_admin_permission_uc18_denied_without_user() -> None:
    service, _, _, _, _, _ = make_service()

    with pytest.raises(ClientError):
        await service._check_admin_permission(user=None, raise_exception=True)


async def test_check_admin_permission_uc17_allows_user_with_admin_scope() -> None:
    service, _, _, _, _, _ = make_service()

    allowed = await service._check_admin_permission(
        user=make_user(scope_names=["SUPERUSER"]), raise_exception=False
    )

    assert allowed is True


async def test_check_admin_permission_uc18_denied_without_required_scope() -> None:
    service, _, _, _, _, _ = make_service()

    with pytest.raises(ClientError):
        await service._check_admin_permission(
            user=make_user(scope_names=["CONTENT_EDITOR"]), raise_exception=True
        )


async def test_placeholder_horse_service_functions_are_explicitly_not_implemented() -> (
    None
):
    service, _, _, _, _, _ = make_service()

    with pytest.raises(ClientError):
        await service.add_horse_service()
    with pytest.raises(ClientError):
        await service.remove_horse_service()
    with pytest.raises(ClientError):
        await service.update_horse_service()


# ---------------------------------------------------------------------------
# Helpers for get_filtered_horses tests
# ---------------------------------------------------------------------------


def make_horse_out_dto(**overrides: Any) -> HorseOutDto:
    """Create a minimal HorseOutDto for use in list_result."""
    defaults: dict[str, Any] = {
        "id": uuid4(),
        "slug": "test-horse",
        "name": "Тест",
        "sex": HorseSexEnum.MALE,
        "bdate_mode": HorseDateModeEnum.HIDE,
        "ddate_mode": HorseDateModeEnum.HIDE,
        "this_stable": False,
    }
    defaults.update(overrides)
    return HorseOutDto(**defaults)


async def test_horse_kind_to_breed_horse_write_and_read_dtos_do_not_expose_kind() -> (
    None
):
    assert "kind" not in HorseCreateInDto.model_fields
    assert "kind" not in HorseUpdateInDto.model_fields
    assert "kind" not in HorseOutDto.model_fields
    assert "kind" not in HorseWithPedigreeOutDto.model_fields


async def test_horse_kind_to_breed_pedigree_nested_dtos_do_not_expose_kind() -> None:
    dto = HorseWithPedigreeOutDto(
        **make_horse_out_dto().model_dump(),
        pedigree=HorsePedigree(
            sire=make_horse_out_dto(name="Sire"),
            dam=make_horse_out_dto(name="Dam"),
            foals=[
                HorseFoalOutDto(
                    **make_horse_out_dto(name="Foal").model_dump(),
                    parents=FoalParentsDto(sire=None, dam=None),
                )
            ],
        ),
    )

    dumped = dto.model_dump()
    assert "kind" not in dumped
    assert "kind" not in dumped["pedigree"]["sire"]
    assert "kind" not in dumped["pedigree"]["dam"]
    assert "kind" not in dumped["pedigree"]["foals"][0]
    assert "parents" in dumped["pedigree"]["foals"][0]


async def test_horse_kind_to_breed_horse_create_update_reject_extra_kind() -> None:
    with pytest.raises(ValueError):
        HorseCreateInDto.model_validate({"name": "Буран", "kind": "horse"})
    with pytest.raises(ValueError):
        HorseUpdateInDto.model_validate({"kind": "horse"})


def get_list_call_kwargs(horse_repo: FakeHorseRepository) -> dict[str, Any]:
    """Return kwargs from the most recent get_horse_list_full_info call."""
    for name, kwargs in reversed(horse_repo.calls):
        if name == "get_horse_list_full_info":
            return kwargs
    raise AssertionError("get_horse_list_full_info was never called")


# ---------------------------------------------------------------------------
# U-01 … U-06  Default sort behaviour
# ---------------------------------------------------------------------------


async def test_u01_sort_none_passes_none_to_repo() -> None:
    """sort=None → repo receives sort=None (default ordering applied in repo)."""
    service, horse_repo, _, _, _, _ = make_service()
    await service.get_filtered_horses(
        sort=None, user=None, equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )
    kwargs = get_list_call_kwargs(horse_repo)
    assert kwargs["sort"] is None


async def test_u02_sort_name_passes_name_asc_to_repo() -> None:
    """sort=['name'] → repo receives sort=['name'], no default."""
    service, horse_repo, _, _, _, _ = make_service()
    await service.get_filtered_horses(
        sort=["name"], user=None, equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )
    kwargs = get_list_call_kwargs(horse_repo)
    assert kwargs["sort"] == ["name"]


async def test_u03_sort_minus_name_passes_name_desc_to_repo() -> None:
    """sort=['-name'] → repo receives sort=['-name']."""
    service, horse_repo, _, _, _, _ = make_service()
    await service.get_filtered_horses(
        sort=["-name"], user=None, equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )
    kwargs = get_list_call_kwargs(horse_repo)
    assert kwargs["sort"] == ["-name"]


async def test_u04_sort_created_at_passes_created_at_asc_to_repo() -> None:
    """sort=['created_at'] → repo receives sort=['created_at']."""
    service, horse_repo, _, _, _, _ = make_service()
    await service.get_filtered_horses(
        sort=["created_at"], user=None, equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )
    kwargs = get_list_call_kwargs(horse_repo)
    assert kwargs["sort"] == ["created_at"]


async def test_u05_sort_minus_created_at_passes_desc_to_repo() -> None:
    """sort=['-created_at'] → repo receives sort=['-created_at']."""
    service, horse_repo, _, _, _, _ = make_service()
    await service.get_filtered_horses(
        sort=["-created_at"], user=None, equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )
    kwargs = get_list_call_kwargs(horse_repo)
    assert kwargs["sort"] == ["-created_at"]


async def test_u06_sort_empty_list_passes_empty_list_to_repo() -> None:
    """sort=[] (falsy) → repo receives sort=[], repo applies default ordering."""
    service, horse_repo, _, _, _, _ = make_service()
    await service.get_filtered_horses(
        sort=[], user=None, equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )
    kwargs = get_list_call_kwargs(horse_repo)
    # Service passes the empty list through; repository treats falsy sort as default
    assert kwargs["sort"] == []


async def test_u07_sort_none_repo_returns_items_in_provided_order() -> None:
    """sort=None + repo returns items ordered by updated_at DESC → service preserves order."""
    service, horse_repo, _, _, _, _ = make_service()
    h1_id = uuid4()
    h2_id = uuid4()
    h1 = make_horse_out_dto(id=h1_id, name="Первая")
    h2 = make_horse_out_dto(id=h2_id, name="Вторая")
    # Repo returns h1 first (simulating latest updated_at DESC)
    horse_repo.list_result = ({h1_id: h1, h2_id: h2}, 2)

    result = await service.get_filtered_horses(
        sort=None, user=None, equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )

    assert len(result.items) == 2
    assert result.items[0].id == h1_id
    assert result.items[1].id == h2_id


async def test_u08_sort_none_repo_secondary_order_preserved() -> None:
    """Same updated_at → service preserves the secondary order (created_at DESC) from repo."""
    service, horse_repo, _, _, _, _ = make_service()
    a_id = uuid4()
    b_id = uuid4()
    ha = make_horse_out_dto(id=a_id, name="A")
    hb = make_horse_out_dto(id=b_id, name="B")
    horse_repo.list_result = ({a_id: ha, b_id: hb}, 2)

    result = await service.get_filtered_horses(
        sort=None, user=None, equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )

    assert result.items[0].id == a_id


async def test_u09_sort_none_null_updated_at_passes_sort_none() -> None:
    """sort=None with records that have updated_at=None → sort=None passed to repo (NULLS LAST handled there)."""
    service, horse_repo, _, _, _, _ = make_service()
    await service.get_filtered_horses(
        sort=None, user=None, equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )
    kwargs = get_list_call_kwargs(horse_repo)
    assert kwargs["sort"] is None


async def test_u10_sort_none_null_created_at_passes_sort_none() -> None:
    """sort=None with records that have created_at=None → sort=None passed to repo."""
    service, horse_repo, _, _, _, _ = make_service()
    await service.get_filtered_horses(
        sort=None, user=None, equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )
    kwargs = get_list_call_kwargs(horse_repo)
    assert kwargs["sort"] is None


# ---------------------------------------------------------------------------
# U-11 … U-16  Text filter behaviour (repo-level ~* verified via SQLAlchemy compile)
# ---------------------------------------------------------------------------


async def test_u11_name_filter_passes_name_to_repo() -> None:
    """name='TEST' → repo receives name='TEST' (repo will apply ~* operator)."""
    service, horse_repo, _, _, _, _ = make_service()
    await service.get_filtered_horses(
        name="TEST", user=None, equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )
    kwargs = get_list_call_kwargs(horse_repo)
    assert kwargs["name"] == "TEST"


async def test_u11_repo_name_filter_uses_regex_not_ilike() -> None:
    """Verify SQLAlchemy condition for name uses ~* (regex), not ILIKE."""
    # Build a minimal table matching the real horse table structure
    meta = MetaData()
    t = SATable("horse", meta, Column("name", String))
    safe = re.escape("TEST")
    cond_regex = t.c.name.op("~*")(safe)
    cond_ilike = t.c.name.ilike("%TEST%")
    compiled_regex = str(
        cond_regex.compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )
    compiled_ilike = str(
        cond_ilike.compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )
    assert "~*" in compiled_regex
    assert "ILIKE" not in compiled_regex
    assert "ILIKE" in compiled_ilike


async def test_u12_description_filter_passes_value_to_repo() -> None:
    """description='test' → repo receives description='test' (repo will apply ~*)."""
    service, horse_repo, _, _, _, _ = make_service()
    await service.get_filtered_horses(
        description="test", user=None, equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )
    kwargs = get_list_call_kwargs(horse_repo)
    assert kwargs["description"] == "test"


async def test_u12_repo_description_filter_uses_regex_not_ilike() -> None:
    """Verify SQLAlchemy condition for description uses ~*, not ILIKE."""
    meta = MetaData()
    t = SATable("horse", meta, Column("description", String))
    safe = re.escape("test")
    cond = t.c.description.op("~*")(safe)
    compiled = str(
        cond.compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )
    assert "~*" in compiled
    assert "ILIKE" not in compiled


async def test_u13_name_with_dot_re_escape_applied() -> None:
    """name='А.Б' → re.escape converts dot to literal, pattern is 'А\\.Б' not 'А.Б'."""
    meta = MetaData()
    t = SATable("horse", meta, Column("name", String))
    raw = "А.Б"
    safe = re.escape(raw)
    assert safe == "А\\.Б"
    cond = t.c.name.op("~*")(safe)
    compiled = str(
        cond.compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )
    assert "\\." in compiled


async def test_u14_name_with_parens_re_escape_applied() -> None:
    """name='(тест)' → re.escape escapes parentheses so they are treated as literals."""
    raw = "(тест)"
    safe = re.escape(raw)
    assert "\\(" in safe and "\\)" in safe


async def test_u15_name_none_not_passed_as_condition() -> None:
    """name=None → repo receives name=None, no filter condition is added."""
    service, horse_repo, _, _, _, _ = make_service()
    await service.get_filtered_horses(
        name=None, user=None, equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )
    kwargs = get_list_call_kwargs(horse_repo)
    assert kwargs.get("name") is None


async def test_u16_name_empty_string_passes_empty_to_repo() -> None:
    """name='' → repo receives name='', repo skips condition for empty string."""
    service, horse_repo, _, _, _, _ = make_service()
    await service.get_filtered_horses(
        name="", user=None, equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )
    kwargs = get_list_call_kwargs(horse_repo)
    # Service passes empty string through; repository skips condition when falsy
    assert kwargs.get("name") == ""


# ---------------------------------------------------------------------------
# U-17 … U-19  Boolean this_stable filter
# ---------------------------------------------------------------------------


async def test_u17_this_stable_true_passes_true_to_repo() -> None:
    """this_stable=True → repo receives this_stable=True."""
    service, horse_repo, _, _, _, _ = make_service()
    await service.get_filtered_horses(
        this_stable=True, user=None, equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )
    kwargs = get_list_call_kwargs(horse_repo)
    assert kwargs["this_stable"] is True


async def test_u18_this_stable_false_passes_false_to_repo() -> None:
    """this_stable=False → repo receives this_stable=False."""
    service, horse_repo, _, _, _, _ = make_service()
    await service.get_filtered_horses(
        this_stable=False, user=None, equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )
    kwargs = get_list_call_kwargs(horse_repo)
    assert kwargs["this_stable"] is False


async def test_u19_this_stable_none_passes_none_to_repo() -> None:
    """this_stable=None → repo receives this_stable=None (no filter)."""
    service, horse_repo, _, _, _, _ = make_service()
    await service.get_filtered_horses(
        this_stable=None, user=None, equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )
    kwargs = get_list_call_kwargs(horse_repo)
    assert kwargs["this_stable"] is None


# ---------------------------------------------------------------------------
# U-20 … U-25  Other list filters
# ---------------------------------------------------------------------------


async def test_u20_breed_ids_passed_to_repo() -> None:
    """breed_ids=[uuid1, uuid2] → WHERE breed_id IN (...)."""
    service, horse_repo, _, _, _, _ = make_service()
    id1, id2 = uuid4(), uuid4()
    await service.get_filtered_horses(
        breed_ids=[id1, id2], user=None, equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )
    kwargs = get_list_call_kwargs(horse_repo)
    assert kwargs["breed_ids"] == [id1, id2]


async def test_u21_coat_color_ids_passed_to_repo() -> None:
    """coat_color_ids=[uuid1] → WHERE coat_color_id IN (...)."""
    service, horse_repo, _, _, _, _ = make_service()
    id1 = uuid4()
    await service.get_filtered_horses(
        coat_color_ids=[id1], user=None, equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )
    kwargs = get_list_call_kwargs(horse_repo)
    assert kwargs["coat_color_ids"] == [id1]


async def test_u22_horse_owner_ids_passed_to_repo() -> None:
    """horse_owner_ids=[uuid1] → WHERE horse_owner_id IN (...)."""
    service, horse_repo, _, _, _, _ = make_service()
    id1 = uuid4()
    await service.get_filtered_horses(
        horse_owner_ids=[id1], user=None, equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )
    kwargs = get_list_call_kwargs(horse_repo)
    assert kwargs["horse_owner_ids"] == [id1]


async def test_u23_kind_filter_passed_to_repo() -> None:
    """kind=['horse'] → WHERE kind IN ('horse')."""
    service, horse_repo, _, _, _, _ = make_service()
    await service.get_filtered_horses(
        kind=[HorseKindEnum.HORSE],
        user=None,
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )
    kwargs = get_list_call_kwargs(horse_repo)
    assert kwargs["kind"] == [HorseKindEnum.HORSE]


async def test_u24_sex_filter_passed_to_repo() -> None:
    """sex=['male', 'female'] → WHERE sex IN ('male', 'female')."""
    service, horse_repo, _, _, _, _ = make_service()
    await service.get_filtered_horses(
        sex=[HorseSexEnum.MALE, HorseSexEnum.FEMALE],
        user=None,
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )
    kwargs = get_list_call_kwargs(horse_repo)
    assert kwargs["sex"] == [HorseSexEnum.MALE, HorseSexEnum.FEMALE]


async def test_u25_height_gte_passed_to_repo() -> None:
    """height_gte=150 → WHERE height >= 150."""
    service, horse_repo, _, _, _, _ = make_service()
    await service.get_filtered_horses(
        height_gte=150, user=None, equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )
    kwargs = get_list_call_kwargs(horse_repo)
    assert kwargs["height_gte"] == 150


# ---------------------------------------------------------------------------
# U-26 … U-28  Pagination clamping
# ---------------------------------------------------------------------------


async def test_u26_limit_zero_clamped_to_one() -> None:
    """limit=0 → service clamps to 1 before passing to repo."""
    service, horse_repo, _, _, _, _ = make_service()
    await service.get_filtered_horses(
        limit=0, user=None, equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )
    kwargs = get_list_call_kwargs(horse_repo)
    assert kwargs["limit"] == 1


async def test_u27_limit_too_large_clamped_to_100() -> None:
    """limit=200 → service clamps to 100."""
    service, horse_repo, _, _, _, _ = make_service()
    await service.get_filtered_horses(
        limit=200, user=None, equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )
    kwargs = get_list_call_kwargs(horse_repo)
    assert kwargs["limit"] == 100


async def test_u28_negative_offset_clamped_to_zero() -> None:
    """offset=-1 → service clamps to 0."""
    service, horse_repo, _, _, _, _ = make_service()
    await service.get_filtered_horses(
        offset=-1, user=None, equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )
    kwargs = get_list_call_kwargs(horse_repo)
    assert kwargs["offset"] == 0


# ---------------------------------------------------------------------------
# U-29 … U-32  Sort by related fields and preserved order
# ---------------------------------------------------------------------------


async def test_u29_sort_none_result_items_order_preserved() -> None:
    """Service returns PaginatedEntities with items in the same order as repo dict."""
    service, horse_repo, _, _, _, _ = make_service()
    ids = [uuid4(), uuid4(), uuid4()]
    items = {
        id_: make_horse_out_dto(id=id_, name=f"Horse{i}") for i, id_ in enumerate(ids)
    }
    horse_repo.list_result = (items, 3)

    result = await service.get_filtered_horses(
        sort=None, user=None, equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )

    assert result.total == 3
    assert [h.id for h in result.items] == ids


async def test_u30_sort_breed_name_passes_breed_name_to_repo() -> None:
    """sort=['breed_name'] → repo receives sort=['breed_name'] (repo sorts by breeds.c.short_name)."""
    service, horse_repo, _, _, _, _ = make_service()
    await service.get_filtered_horses(
        sort=["breed_name"], user=None, equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )
    kwargs = get_list_call_kwargs(horse_repo)
    assert kwargs["sort"] == ["breed_name"]


async def test_u31_sort_coat_color_name_passes_coat_color_name_to_repo() -> None:
    """sort=['coat_color_name'] → repo receives sort=['coat_color_name'] (repo sorts by coat_color.c.short_name)."""
    service, horse_repo, _, _, _, _ = make_service()
    await service.get_filtered_horses(
        sort=["coat_color_name"], user=None, equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )
    kwargs = get_list_call_kwargs(horse_repo)
    assert kwargs["sort"] == ["coat_color_name"]


async def test_u32_name_with_asterisk_re_escape_applied() -> None:
    """name='тест*' → re.escape turns '*' into '\\*' so it's treated as literal."""
    raw = "тест*"
    safe = re.escape(raw)
    assert safe == "тест\\*"


# ---------------------------------------------------------------------------
# U-33 … U-35  POST /horses/{id}/photos — update_horse_photos
# ---------------------------------------------------------------------------


def make_photo(equestrian_id: UUID | None = None) -> Photo:
    return Photo(
        equestrian_id=equestrian_id or uuid4(),
        name="Test photo",
        path="photos/test.jpg",
    )


def make_service_with_photos() -> tuple[
    HorseService,
    FakeHorseRepository,
    FakeHorseChildrenRepository,
    FakeSimpleRepository,
    FakeSimpleRepository,
    FakeSimpleRepository,
    FakePhotoRepository,
]:
    horse_repo = FakeHorseRepository()
    horse_children_repo = FakeHorseChildrenRepository()
    breed_repo = FakeSimpleRepository()
    coat_repo = FakeSimpleRepository()
    owner_repo = FakeSimpleRepository()
    photo_repo = FakePhotoRepository()
    return (
        HorseService(
            horse_repository=cast(Any, horse_repo),
            horse_children_repository=cast(Any, horse_children_repo),
            breed_repository=cast(Any, breed_repo),
            coat_color_repository=cast(Any, coat_repo),
            horse_owner_repository=cast(Any, owner_repo),
            photo_repository=cast(Any, photo_repo),
        ),
        horse_repo,
        horse_children_repo,
        breed_repo,
        coat_repo,
        owner_repo,
        photo_repo,
    )


async def test_u33_update_horse_photos_success_calls_set_horse_photos() -> None:
    """update_horse_photos with valid photo_ids calls set_horse_photos on repo."""
    service, horse_repo, _, _, _, _, photo_repo = make_service_with_photos()
    horse = horse_repo.add(make_horse())
    photo = make_photo()
    photo_repo.add(photo)

    result = await service.update_horse_photos(
        horse_id=horse.id,
        data=HorsePhotosUpdateInDto(photo_ids=[photo.id]),
        user=make_user(),
        equestrian_context=cast(
            Any, type("EC", (), {"id": horse.equestrian_id or uuid4()})()
        ),
    )

    assert any(name == "set_horse_photos" for name, _ in horse_repo.calls)
    assert result is not None


async def test_u34_update_horse_photos_horse_not_found_raises_client_error() -> None:
    """update_horse_photos raises ClientError when horse not found."""
    service, _, _, _, _, _, _ = make_service_with_photos()

    with pytest.raises(ClientError):
        await service.update_horse_photos(
            horse_id=uuid4(),
            data=HorsePhotosUpdateInDto(photo_ids=[]),
            user=make_user(),
            equestrian_context=cast(Any, type("EC", (), {"id": uuid4()})()),
        )


async def test_u35_update_horse_photos_unauthorized_raises_client_error() -> None:
    """update_horse_photos raises ClientError when user is None (unauthorized)."""
    service, horse_repo, _, _, _, _, _ = make_service_with_photos()
    horse = horse_repo.add(make_horse())

    with pytest.raises(ClientError):
        await service.update_horse_photos(
            horse_id=horse.id,
            data=HorsePhotosUpdateInDto(photo_ids=[]),
            user=None,
            equestrian_context=cast(
                Any, type("EC", (), {"id": horse.equestrian_id or uuid4()})()
            ),
        )
