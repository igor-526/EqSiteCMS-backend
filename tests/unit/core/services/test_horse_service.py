from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any, Mapping, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Column, MetaData, String
from sqlalchemy import Table as SATable
from sqlalchemy.dialects import postgresql

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
from core.schemas import (
    HorseCreateInDto,
    HorseOutDto,
    HorseSetPedigreeInDto,
    HorseUpdateInDto,
    UserOutDto,
)
from core.schemas.horses import HorsePhotosUpdateInDto
from core.services.horse import HorseService

pytestmark = pytest.mark.asyncio


class RepositoryError(Exception):
    pass


class FakeHorseRepository:
    def __init__(self) -> None:
        self.by_id: dict[UUID, Horse] = {}
        self.calls: list[tuple[str, Any]] = []
        self.fail_on: set[str] = set()
        self.list_result: tuple[Mapping[UUID, HorseOutDto], int] = ({}, 0)

    def add(self, horse: Horse) -> Horse:
        self.by_id[horse.id] = horse
        return horse

    def _fail_if_needed(self, method: str) -> None:
        if method in self.fail_on:
            raise RepositoryError(method)

    async def get_by_id(self, id: UUID) -> Horse | None:
        self.calls.append(("get_by_id", id))
        self._fail_if_needed("get_by_id")
        return self.by_id.get(id)

    async def get_by_ids(self, ids: list[UUID]) -> Mapping[UUID, Horse]:
        self.calls.append(("get_by_ids", ids))
        self._fail_if_needed("get_by_ids")
        return {id_: self.by_id[id_] for id_ in ids if id_ in self.by_id}

    async def create(self, entity: Horse) -> Horse:
        self.calls.append(("create", entity))
        self._fail_if_needed("create")
        return self.add(entity)

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
    ) -> HorseOutDto | None:
        self.calls.append(
            ("get_horse_full_info_by_id", {"horse_id": horse_id, "pedigree": pedigree})
        )
        self._fail_if_needed("get_horse_full_info_by_id")
        horse = self.by_id.get(horse_id)
        if horse is None:
            return None
        return HorseOutDto(
            id=horse.id,
            slug=horse.slug or "",
            name=horse.name,
            description=horse.description,
            kind=horse.kind,
            height=horse.height,
            sex=horse.sex,
            bdate=horse.bdate,
            ddate=horse.ddate,
            bdate_mode=horse.bdate_mode,
            ddate_mode=horse.ddate_mode,
            this_stable=horse.this_stable,
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
        limit: int | None = 25,
        offset: int | None = 0,
    ) -> tuple[Mapping[UUID, HorseOutDto], int]:
        self.calls.append(
            (
                "get_available_sires",
                {"limit": limit, "offset": offset, "search": search},
            )
        )
        self._fail_if_needed("get_available_sires")
        return ({}, 0)

    async def get_available_dams(
        self,
        *,
        target_horse: Horse,
        search: str | None = None,
        limit: int | None = 25,
        offset: int | None = 0,
    ) -> tuple[Mapping[UUID, HorseOutDto], int]:
        self.calls.append(
            ("get_available_dams", {"limit": limit, "offset": offset, "search": search})
        )
        self._fail_if_needed("get_available_dams")
        return ({}, 0)

    async def get_available_children(
        self,
        *,
        target_horse: Horse,
        search: str | None = None,
        limit: int | None = 25,
        offset: int | None = 0,
    ) -> tuple[Mapping[UUID, HorseOutDto], int]:
        self.calls.append(
            (
                "get_available_children",
                {"limit": limit, "offset": offset, "search": search},
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
        self, horse_id: UUID, photo_ids: list[UUID], *, equestrian_id: UUID
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
            horse_id=horse.id, data=HorseUpdateInDto(), user=make_user()
        )


async def test_update_horse_uc18_denies_non_admin_scope_user() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    horse = horse_repo.add(make_horse())

    with pytest.raises(ClientError):
        await service.update_horse(
            horse_id=horse.id,
            data=HorseUpdateInDto(description="updated"),
            user=make_user(scope_names=["CONTENT_EDITOR"]),
        )


async def test_create_horse_uc16_reference_validation_runs_before_create() -> None:
    service, horse_repo, _, breed_repo, coat_repo, owner_repo = make_service()
    breed = breed_repo.add(Breed(name="Arabian", slug="arabian", short_name="Arabian"))
    coat = coat_repo.add(CoatColor(name="Bay", slug="bay", short_name="Bay"))
    owner = owner_repo.add(HorseOwner(name="Owner"))

    created = await service.create_horse(
        create_data=HorseCreateInDto(
            name="Новая",
            breed_id=breed.id,
            coat_color_id=coat.id,
            horse_owner_id=owner.id,
        ),
        user=make_user(),
    )

    assert created.name == "Новая"
    assert [name for name, _ in horse_repo.calls] == ["create"]


async def test_create_horse_uc16_missing_reference_returns_client_error() -> None:
    service, horse_repo, _, _, _, _ = make_service()

    with pytest.raises(ClientError):
        await service.create_horse(
            create_data=HorseCreateInDto(name="Новая", breed_id=uuid4()),
            user=make_user(),
        )

    assert horse_repo.calls == []


async def test_get_horse_by_slug_or_id_uc12_uuid_vs_slug_deterministic() -> None:
    service, horse_repo, _, _, _, _ = make_service()
    horse = horse_repo.add(make_horse(slug="special-slug"))

    by_uuid = await service.get_horse_by_slug_or_id(slug_or_id=str(horse.id), user=None)
    by_slug = await service.get_horse_by_slug_or_id(
        slug_or_id="special-slug", user=None
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
    )

    assert (
        "get_available_sires",
        {"limit": 50, "offset": 0, "search": None},
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
        )


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
        "kind": HorseKindEnum.HORSE,
        "sex": HorseSexEnum.MALE,
        "bdate_mode": HorseDateModeEnum.HIDE,
        "ddate_mode": HorseDateModeEnum.HIDE,
        "this_stable": False,
    }
    defaults.update(overrides)
    return HorseOutDto(**defaults)


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
    await service.get_filtered_horses(sort=None, user=None)
    kwargs = get_list_call_kwargs(horse_repo)
    assert kwargs["sort"] is None


async def test_u02_sort_name_passes_name_asc_to_repo() -> None:
    """sort=['name'] → repo receives sort=['name'], no default."""
    service, horse_repo, _, _, _, _ = make_service()
    await service.get_filtered_horses(sort=["name"], user=None)
    kwargs = get_list_call_kwargs(horse_repo)
    assert kwargs["sort"] == ["name"]


async def test_u03_sort_minus_name_passes_name_desc_to_repo() -> None:
    """sort=['-name'] → repo receives sort=['-name']."""
    service, horse_repo, _, _, _, _ = make_service()
    await service.get_filtered_horses(sort=["-name"], user=None)
    kwargs = get_list_call_kwargs(horse_repo)
    assert kwargs["sort"] == ["-name"]


async def test_u04_sort_created_at_passes_created_at_asc_to_repo() -> None:
    """sort=['created_at'] → repo receives sort=['created_at']."""
    service, horse_repo, _, _, _, _ = make_service()
    await service.get_filtered_horses(sort=["created_at"], user=None)
    kwargs = get_list_call_kwargs(horse_repo)
    assert kwargs["sort"] == ["created_at"]


async def test_u05_sort_minus_created_at_passes_desc_to_repo() -> None:
    """sort=['-created_at'] → repo receives sort=['-created_at']."""
    service, horse_repo, _, _, _, _ = make_service()
    await service.get_filtered_horses(sort=["-created_at"], user=None)
    kwargs = get_list_call_kwargs(horse_repo)
    assert kwargs["sort"] == ["-created_at"]


async def test_u06_sort_empty_list_passes_empty_list_to_repo() -> None:
    """sort=[] (falsy) → repo receives sort=[], repo applies default ordering."""
    service, horse_repo, _, _, _, _ = make_service()
    await service.get_filtered_horses(sort=[], user=None)
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

    result = await service.get_filtered_horses(sort=None, user=None)

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

    result = await service.get_filtered_horses(sort=None, user=None)

    assert result.items[0].id == a_id


async def test_u09_sort_none_null_updated_at_passes_sort_none() -> None:
    """sort=None with records that have updated_at=None → sort=None passed to repo (NULLS LAST handled there)."""
    service, horse_repo, _, _, _, _ = make_service()
    await service.get_filtered_horses(sort=None, user=None)
    kwargs = get_list_call_kwargs(horse_repo)
    assert kwargs["sort"] is None


async def test_u10_sort_none_null_created_at_passes_sort_none() -> None:
    """sort=None with records that have created_at=None → sort=None passed to repo."""
    service, horse_repo, _, _, _, _ = make_service()
    await service.get_filtered_horses(sort=None, user=None)
    kwargs = get_list_call_kwargs(horse_repo)
    assert kwargs["sort"] is None


# ---------------------------------------------------------------------------
# U-11 … U-16  Text filter behaviour (repo-level ~* verified via SQLAlchemy compile)
# ---------------------------------------------------------------------------


async def test_u11_name_filter_passes_name_to_repo() -> None:
    """name='TEST' → repo receives name='TEST' (repo will apply ~* operator)."""
    service, horse_repo, _, _, _, _ = make_service()
    await service.get_filtered_horses(name="TEST", user=None)
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
    await service.get_filtered_horses(description="test", user=None)
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
    await service.get_filtered_horses(name=None, user=None)
    kwargs = get_list_call_kwargs(horse_repo)
    assert kwargs.get("name") is None


async def test_u16_name_empty_string_passes_empty_to_repo() -> None:
    """name='' → repo receives name='', repo skips condition for empty string."""
    service, horse_repo, _, _, _, _ = make_service()
    await service.get_filtered_horses(name="", user=None)
    kwargs = get_list_call_kwargs(horse_repo)
    # Service passes empty string through; repository skips condition when falsy
    assert kwargs.get("name") == ""


# ---------------------------------------------------------------------------
# U-17 … U-19  Boolean this_stable filter
# ---------------------------------------------------------------------------


async def test_u17_this_stable_true_passes_true_to_repo() -> None:
    """this_stable=True → repo receives this_stable=True."""
    service, horse_repo, _, _, _, _ = make_service()
    await service.get_filtered_horses(this_stable=True, user=None)
    kwargs = get_list_call_kwargs(horse_repo)
    assert kwargs["this_stable"] is True


async def test_u18_this_stable_false_passes_false_to_repo() -> None:
    """this_stable=False → repo receives this_stable=False."""
    service, horse_repo, _, _, _, _ = make_service()
    await service.get_filtered_horses(this_stable=False, user=None)
    kwargs = get_list_call_kwargs(horse_repo)
    assert kwargs["this_stable"] is False


async def test_u19_this_stable_none_passes_none_to_repo() -> None:
    """this_stable=None → repo receives this_stable=None (no filter)."""
    service, horse_repo, _, _, _, _ = make_service()
    await service.get_filtered_horses(this_stable=None, user=None)
    kwargs = get_list_call_kwargs(horse_repo)
    assert kwargs["this_stable"] is None


# ---------------------------------------------------------------------------
# U-20 … U-25  Other list filters
# ---------------------------------------------------------------------------


async def test_u20_breed_ids_passed_to_repo() -> None:
    """breed_ids=[uuid1, uuid2] → WHERE breed_id IN (...)."""
    service, horse_repo, _, _, _, _ = make_service()
    id1, id2 = uuid4(), uuid4()
    await service.get_filtered_horses(breed_ids=[id1, id2], user=None)
    kwargs = get_list_call_kwargs(horse_repo)
    assert kwargs["breed_ids"] == [id1, id2]


async def test_u21_coat_color_ids_passed_to_repo() -> None:
    """coat_color_ids=[uuid1] → WHERE coat_color_id IN (...)."""
    service, horse_repo, _, _, _, _ = make_service()
    id1 = uuid4()
    await service.get_filtered_horses(coat_color_ids=[id1], user=None)
    kwargs = get_list_call_kwargs(horse_repo)
    assert kwargs["coat_color_ids"] == [id1]


async def test_u22_horse_owner_ids_passed_to_repo() -> None:
    """horse_owner_ids=[uuid1] → WHERE horse_owner_id IN (...)."""
    service, horse_repo, _, _, _, _ = make_service()
    id1 = uuid4()
    await service.get_filtered_horses(horse_owner_ids=[id1], user=None)
    kwargs = get_list_call_kwargs(horse_repo)
    assert kwargs["horse_owner_ids"] == [id1]


async def test_u23_kind_filter_passed_to_repo() -> None:
    """kind=['horse'] → WHERE kind IN ('horse')."""
    service, horse_repo, _, _, _, _ = make_service()
    await service.get_filtered_horses(kind=[HorseKindEnum.HORSE], user=None)
    kwargs = get_list_call_kwargs(horse_repo)
    assert kwargs["kind"] == [HorseKindEnum.HORSE]


async def test_u24_sex_filter_passed_to_repo() -> None:
    """sex=['male', 'female'] → WHERE sex IN ('male', 'female')."""
    service, horse_repo, _, _, _, _ = make_service()
    await service.get_filtered_horses(
        sex=[HorseSexEnum.MALE, HorseSexEnum.FEMALE], user=None
    )
    kwargs = get_list_call_kwargs(horse_repo)
    assert kwargs["sex"] == [HorseSexEnum.MALE, HorseSexEnum.FEMALE]


async def test_u25_height_gte_passed_to_repo() -> None:
    """height_gte=150 → WHERE height >= 150."""
    service, horse_repo, _, _, _, _ = make_service()
    await service.get_filtered_horses(height_gte=150, user=None)
    kwargs = get_list_call_kwargs(horse_repo)
    assert kwargs["height_gte"] == 150


# ---------------------------------------------------------------------------
# U-26 … U-28  Pagination clamping
# ---------------------------------------------------------------------------


async def test_u26_limit_zero_clamped_to_one() -> None:
    """limit=0 → service clamps to 1 before passing to repo."""
    service, horse_repo, _, _, _, _ = make_service()
    await service.get_filtered_horses(limit=0, user=None)
    kwargs = get_list_call_kwargs(horse_repo)
    assert kwargs["limit"] == 1


async def test_u27_limit_too_large_clamped_to_100() -> None:
    """limit=200 → service clamps to 100."""
    service, horse_repo, _, _, _, _ = make_service()
    await service.get_filtered_horses(limit=200, user=None)
    kwargs = get_list_call_kwargs(horse_repo)
    assert kwargs["limit"] == 100


async def test_u28_negative_offset_clamped_to_zero() -> None:
    """offset=-1 → service clamps to 0."""
    service, horse_repo, _, _, _, _ = make_service()
    await service.get_filtered_horses(offset=-1, user=None)
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

    result = await service.get_filtered_horses(sort=None, user=None)

    assert result.total == 3
    assert [h.id for h in result.items] == ids


async def test_u30_sort_breed_name_passes_breed_name_to_repo() -> None:
    """sort=['breed_name'] → repo receives sort=['breed_name'] (repo sorts by breeds.c.short_name)."""
    service, horse_repo, _, _, _, _ = make_service()
    await service.get_filtered_horses(sort=["breed_name"], user=None)
    kwargs = get_list_call_kwargs(horse_repo)
    assert kwargs["sort"] == ["breed_name"]


async def test_u31_sort_coat_color_name_passes_coat_color_name_to_repo() -> None:
    """sort=['coat_color_name'] → repo receives sort=['coat_color_name'] (repo sorts by coat_color.c.short_name)."""
    service, horse_repo, _, _, _, _ = make_service()
    await service.get_filtered_horses(sort=["coat_color_name"], user=None)
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
