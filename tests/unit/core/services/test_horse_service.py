from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Mapping, cast
from uuid import UUID, uuid4

import pytest

from core.entities import Breed, CoatColor, Horse, HorseOwner, HorseSexEnum, UserScope
from core.exceptions.base import ClientError
from core.schemas import (
    HorseCreateInDto,
    HorseOutDto,
    HorseSetPedigreeInDto,
    HorseUpdateInDto,
    UserOutDto,
)
from core.services.horse import HorseService

pytestmark = pytest.mark.asyncio


class RepositoryError(Exception):
    pass


class FakeHorseRepository:
    def __init__(self) -> None:
        self.by_id: dict[UUID, Horse] = {}
        self.calls: list[tuple[str, Any]] = []
        self.fail_on: set[str] = set()

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
        return ({}, 0)


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
    breed = breed_repo.add(Breed(name="Arabian", slug="arabian"))
    coat = coat_repo.add(CoatColor(name="Bay", slug="bay"))
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
