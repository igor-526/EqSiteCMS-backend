"""Unit tests for HorseOwnerService (UC01-UC30)."""

from __future__ import annotations

from typing import Any, Literal, cast
from uuid import UUID, uuid4

import pytest

from core.entities.horse_owner import HorseOwner, HorseOwnerType
from core.exceptions.base import ClientError
from core.schemas.horse_owner import HorseOwnerCreateInDto, HorseOwnerUpdateDto
from core.services.horse_owner import HorseOwnerService

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers / fake repository
# ---------------------------------------------------------------------------


class RepositoryError(Exception):
    """Simulates an infrastructure-level failure."""


class FakeHorseOwnerRepository:
    def __init__(self) -> None:
        self.by_id: dict[UUID, HorseOwner] = {}
        self.calls: list[tuple[str, Any]] = []
        self.filtered_result: tuple[list[HorseOwner], int] = ([], 0)
        self.fail_on: set[str] = set()

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def add(self, owner: HorseOwner) -> HorseOwner:
        self.by_id[owner.id] = owner
        return owner

    def _fail_if_needed(self, method: str) -> None:
        if method in self.fail_on:
            raise RepositoryError(method)

    # ------------------------------------------------------------------
    # protocol methods
    # ------------------------------------------------------------------

    async def get_by_id(self, id: UUID) -> HorseOwner | None:
        self.calls.append(("get_by_id", id))
        self._fail_if_needed("get_by_id")
        return self.by_id.get(id)

    async def get_all(
        self, *, limit: int | None = None, offset: int | None = None
    ) -> list[HorseOwner]:
        self.calls.append(("get_all", {"limit": limit, "offset": offset}))
        self._fail_if_needed("get_all")
        return list(self.by_id.values())

    async def get_by_ids(self, ids: list[UUID]) -> dict[UUID, HorseOwner]:
        self.calls.append(("get_by_ids", ids))
        self._fail_if_needed("get_by_ids")
        return {i: self.by_id[i] for i in ids if i in self.by_id}

    async def bulk_create(self, entities: list[HorseOwner]) -> list[HorseOwner]:
        self.calls.append(("bulk_create", entities))
        self._fail_if_needed("bulk_create")
        for e in entities:
            self.add(e)
        return entities

    async def bulk_delete(self, ids: list[UUID]) -> None:
        self.calls.append(("bulk_delete", ids))
        self._fail_if_needed("bulk_delete")
        for i in ids:
            self.by_id.pop(i, None)

    async def create(self, entity: HorseOwner) -> HorseOwner:
        self.calls.append(("create", entity))
        self._fail_if_needed("create")
        self.add(entity)
        return entity

    async def update(self, entity: HorseOwner) -> HorseOwner:
        self.calls.append(("update", entity))
        self._fail_if_needed("update")
        self.add(entity)
        return entity

    async def delete(self, id: UUID) -> None:
        self.calls.append(("delete", id))
        self._fail_if_needed("delete")
        self.by_id.pop(id, None)

    async def get_filtered(
        self,
        *,
        name: str | None = None,
        description: str | None = None,
        type: list[str] | None = None,
        address: str | None = None,
        phone_numbers: str | None = None,
        sort: (
            list[
                Literal["name", "description", "type", "-name", "-description", "-type"]
            ]
            | None
        ) = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[list[HorseOwner], int]:
        filters = {
            "name": name,
            "description": description,
            "type": type,
            "address": address,
            "phone_numbers": phone_numbers,
            "sort": sort,
            "limit": limit,
            "offset": offset,
        }
        self.calls.append(("get_filtered", filters))
        self._fail_if_needed("get_filtered")
        return self.filtered_result


def make_owner(**overrides: Any) -> HorseOwner:
    data: dict[str, Any] = {
        "name": "Иванов Иван",
        "description": None,
        "type": HorseOwnerType.person,
        "address": None,
        "phone_numbers": [],
    }
    data.update(overrides)
    return HorseOwner(**data)


def make_service() -> tuple[HorseOwnerService, FakeHorseOwnerRepository]:
    repo = FakeHorseOwnerRepository()
    return HorseOwnerService(horse_owner_repository=cast(Any, repo)), repo


# ===========================================================================
# create()
# ===========================================================================


async def test_create_uc01_happy_path() -> None:
    """UC01: create with valid name and phones returns persisted entity."""
    service, repo = make_service()

    owner = await service.create(
        HorseOwnerCreateInDto(name="Иванов", phone_numbers=["+71234567890"])
    )

    assert owner.name == "Иванов"
    assert owner.phone_numbers == ["+71234567890"]
    assert [name for name, _ in repo.calls] == ["create"]


async def test_create_uc02_minimal_input() -> None:
    """UC02: only required field (name) — phones defaults to empty list."""
    service, repo = make_service()

    owner = await service.create(HorseOwnerCreateInDto(name="Петров"))

    assert owner.name == "Петров"
    assert owner.phone_numbers == []
    assert owner.type == HorseOwnerType.person


async def test_create_uc03_full_input() -> None:
    """UC03: all fields provided are preserved on the entity."""
    service, _ = make_service()

    owner = await service.create(
        HorseOwnerCreateInDto(
            name="ООО Ромашка",
            description="Фермерское хозяйство",
            type=HorseOwnerType.company,
            address="г. Москва",
            phone_numbers=["+71234567890", "+71234567891"],
        )
    )

    assert owner.name == "ООО Ромашка"
    assert owner.description == "Фермерское хозяйство"
    assert owner.type == HorseOwnerType.company
    assert owner.address == "г. Москва"
    assert len(owner.phone_numbers) == 2


async def test_create_uc04_omitted_optional_fields() -> None:
    """UC04: optional fields (description, address) default to None."""
    service, _ = make_service()

    owner = await service.create(HorseOwnerCreateInDto(name="Сидоров"))

    assert owner.description is None
    assert owner.address is None


async def test_create_uc05_empty_phone_list_accepted() -> None:
    """UC05: empty phone_numbers list is valid — no validation error."""
    service, _ = make_service()

    owner = await service.create(
        HorseOwnerCreateInDto(name="Алексеев", phone_numbers=[])
    )

    assert owner.phone_numbers == []


async def test_create_uc06_whitespace_name_stored_as_provided() -> None:
    """UC06: service does not strip name — entity stores it as-is (HorseOwner has no whitespace validator)."""
    service, _ = make_service()

    # The service itself does not enforce non-whitespace names;
    # that would be a separate business rule. We just verify it doesn't crash.
    owner = await service.create(HorseOwnerCreateInDto(name="  Пробелы  "))

    assert owner.name == "  Пробелы  "


async def test_create_uc07_unicode_name() -> None:
    """UC07: unicode characters are accepted in name."""
    service, _ = make_service()

    owner = await service.create(HorseOwnerCreateInDto(name="Müller GmbH"))

    assert owner.name == "Müller GmbH"


async def test_create_uc08_phone_boundary_min_7_digits() -> None:
    """UC08: phone with exactly 7 digits after '+' is accepted."""
    service, _ = make_service()

    owner = await service.create(
        HorseOwnerCreateInDto(phone_numbers=["+1234567"], name="X")
    )

    assert "+1234567" in owner.phone_numbers


async def test_create_uc09_phone_below_min_raises_client_error() -> None:
    """UC09: phone with fewer than 7 digits after '+' raises ClientError."""
    service, repo = make_service()

    with pytest.raises(ClientError, match="Неверный формат"):
        await service.create(HorseOwnerCreateInDto(phone_numbers=["+123456"], name="X"))

    assert repo.calls == []  # create never called


async def test_create_uc10_phone_boundary_max_15_digits() -> None:
    """UC10: phone with exactly 15 digits after '+' is accepted."""
    service, _ = make_service()

    owner = await service.create(
        HorseOwnerCreateInDto(phone_numbers=["+123456789012345"], name="X")
    )

    assert "+123456789012345" in owner.phone_numbers


async def test_create_uc11_phone_above_max_raises_client_error() -> None:
    """UC11: phone with more than 15 digits after '+' raises ClientError."""
    service, repo = make_service()

    with pytest.raises(ClientError, match="Неверный формат"):
        await service.create(
            HorseOwnerCreateInDto(phone_numbers=["+1234567890123456"], name="X")
        )

    assert repo.calls == []


async def test_create_uc12_malformed_phone_format_raises_client_error() -> None:
    """UC12: phone without leading '+' raises ClientError."""
    service, repo = make_service()

    with pytest.raises(ClientError):
        await service.create(
            HorseOwnerCreateInDto(phone_numbers=["71234567890"], name="X")
        )

    assert repo.calls == []


async def test_create_uc13_not_found_na_for_create() -> None:
    """UC13: N/A for create — there is no pre-existence check; entity is always created."""
    service, repo = make_service()

    # Create twice — both succeed at the service level (repo handles duplicates)
    first = await service.create(HorseOwnerCreateInDto(name="Дубль"))
    second = await service.create(HorseOwnerCreateInDto(name="Дубль"))

    assert first.name == second.name
    assert [name for name, _ in repo.calls] == ["create", "create"]


async def test_create_uc14_repository_create_failure_propagates() -> None:
    """UC14: repository raises an error → it propagates without being swallowed."""
    service, repo = make_service()
    repo.fail_on.add("create")

    with pytest.raises(RepositoryError):
        await service.create(HorseOwnerCreateInDto(name="Fail"))


async def test_create_uc15_update_not_called_on_create() -> None:
    """UC15: create does not call update (no self-conflict check on create)."""
    service, repo = make_service()

    await service.create(HorseOwnerCreateInDto(name="Иванов"))

    assert "update" not in [name for name, _ in repo.calls]


async def test_create_uc16_no_extra_repo_methods_called() -> None:
    """UC16: create calls only 'create' on the repository — no extra lookups."""
    service, repo = make_service()

    await service.create(HorseOwnerCreateInDto(name="Минимум"))

    assert [name for name, _ in repo.calls] == ["create"]


async def test_create_uc17_valid_call_is_not_blocked() -> None:
    """UC17: service has no auth/permission layer — valid call succeeds."""
    service, _ = make_service()

    owner = await service.create(HorseOwnerCreateInDto(name="Разрешённый"))

    assert owner is not None


@pytest.mark.skip(reason="No auth in HorseOwnerService — permission tests belong to API layer")
async def test_create_uc18_permission_denied_na() -> None:
    """UC18: N/A — no auth in this service layer; skipped by design."""
    ...


async def test_create_uc19_partial_create_uses_defaults() -> None:
    """UC19: N/A for create — all non-provided optional fields use their schema defaults."""
    service, _ = make_service()

    owner = await service.create(HorseOwnerCreateInDto(name="Частичный"))

    assert owner.type == HorseOwnerType.person  # default
    assert owner.phone_numbers == []  # default_factory


async def test_create_uc20_empty_name_rejected_by_pydantic() -> None:
    """UC20: Pydantic raises ValidationError when required 'name' is missing."""
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        HorseOwnerCreateInDto()  # type: ignore[call-arg]


async def test_create_uc21_repository_failure_no_side_effects() -> None:
    """UC21: when create fails, entity is not stored in fake repo."""
    service, repo = make_service()
    repo.fail_on.add("create")

    with pytest.raises(RepositoryError):
        await service.create(HorseOwnerCreateInDto(name="Сбой"))

    assert len(repo.by_id) == 0


async def test_create_uc22_create_called_after_validation() -> None:
    """UC22: phone validation runs before repository.create is called."""
    service, repo = make_service()

    with pytest.raises(ClientError):
        await service.create(HorseOwnerCreateInDto(name="X", phone_numbers=["bad"]))

    assert "create" not in [name for name, _ in repo.calls]


async def test_create_uc23_rollback_intent_no_repo_call_on_validation_error() -> None:
    """UC23: on validation error, repository.create is never called."""
    service, repo = make_service()

    with pytest.raises(ClientError):
        await service.create(HorseOwnerCreateInDto(name="X", phone_numbers=["+12345"]))

    assert repo.calls == []


async def test_create_uc24_idempotency_same_data_stored_twice() -> None:
    """UC24: calling create with same data twice stores two entities (no dedup at service level)."""
    service, repo = make_service()

    dto = HorseOwnerCreateInDto(name="Повтор")
    first = await service.create(dto)
    second = await service.create(dto)

    assert first.id != second.id  # each HorseOwner gets a new UUID by default
    assert len(repo.by_id) == 2


async def test_create_uc25_sorting_na_does_not_apply_to_create() -> None:
    """UC25: N/A for create — sort parameter is irrelevant; create returns entity directly."""
    service, _ = make_service()

    owner = await service.create(HorseOwnerCreateInDto(name="Сортировка"))

    assert owner.name == "Сортировка"


async def test_create_uc26_filtering_na_does_not_apply_to_create() -> None:
    """UC26: N/A for create — filter parameters are irrelevant."""
    service, _ = make_service()

    owner = await service.create(HorseOwnerCreateInDto(name="Фильтр"))

    assert owner is not None


async def test_create_uc27_pagination_na_does_not_apply_to_create() -> None:
    """UC27: N/A for create — pagination is irrelevant."""
    service, _ = make_service()

    owner = await service.create(HorseOwnerCreateInDto(name="Страница"))

    assert owner is not None


async def test_create_uc28_serialization_all_fields_returned() -> None:
    """UC28: all provided fields are present on the returned entity."""
    service, _ = make_service()

    owner = await service.create(
        HorseOwnerCreateInDto(
            name="Полный",
            description="Описание",
            type=HorseOwnerType.company,
            address="Адрес",
            phone_numbers=["+71234567890"],
        )
    )

    assert owner.name == "Полный"
    assert owner.description == "Описание"
    assert owner.type == HorseOwnerType.company
    assert owner.address == "Адрес"
    assert owner.phone_numbers == ["+71234567890"]


async def test_create_uc29_invalid_phone_raises_client_error_not_422() -> None:
    """UC29: invalid phone raises ClientError (maps to HTTP 400), not Pydantic 422."""
    service, _ = make_service()

    with pytest.raises(ClientError):
        await service.create(
            HorseOwnerCreateInDto(name="X", phone_numbers=["bad_phone"])
        )


async def test_create_uc30_architecture_boundary_no_fastapi_or_sqlalchemy() -> None:
    """UC30: horse_owner service module does not import FastAPI or SQLAlchemy."""
    import core.services.horse_owner as svc_module

    assert "fastapi" not in dir(svc_module)
    assert "sqlalchemy" not in dir(svc_module)
    # Verify ClientError is used (not HTTPException)
    assert hasattr(svc_module, "ClientError")


# ===========================================================================
# update()
# ===========================================================================


async def test_update_uc01_happy_path() -> None:
    """UC01: update existing owner — changes only provided fields."""
    service, repo = make_service()
    owner = repo.add(make_owner(name="Старый", description="Старое"))

    updated = await service.update(owner.id, HorseOwnerUpdateDto(name="Новый"))

    assert updated.name == "Новый"
    assert updated.description == "Старое"  # unchanged


async def test_update_uc02_minimal_input_one_field() -> None:
    """UC02: update with a single field changes only that field."""
    service, repo = make_service()
    owner = repo.add(make_owner(address=None))

    updated = await service.update(owner.id, HorseOwnerUpdateDto(address="Москва"))

    assert updated.address == "Москва"


async def test_update_uc03_full_input_all_fields() -> None:
    """UC03: update all mutable fields at once."""
    service, repo = make_service()
    owner = repo.add(make_owner())

    updated = await service.update(
        owner.id,
        HorseOwnerUpdateDto(
            name="Новый",
            description="Новое описание",
            type=HorseOwnerType.company,
            address="Санкт-Петербург",
            phone_numbers=["+79991234567"],
        ),
    )

    assert updated.name == "Новый"
    assert updated.description == "Новое описание"
    assert updated.type == HorseOwnerType.company
    assert updated.address == "Санкт-Петербург"
    assert updated.phone_numbers == ["+79991234567"]


async def test_update_uc04_omitted_optional_fields_not_changed() -> None:
    """UC04: fields not in payload remain unchanged."""
    service, repo = make_service()
    owner = repo.add(make_owner(description="Исходное"))

    updated = await service.update(owner.id, HorseOwnerUpdateDto(name="Новый"))

    assert updated.description == "Исходное"


async def test_update_uc05_empty_phone_list_accepted() -> None:
    """UC05: setting phone_numbers to empty list is valid."""
    service, repo = make_service()
    owner = repo.add(make_owner(phone_numbers=["+71234567890"]))

    updated = await service.update(owner.id, HorseOwnerUpdateDto(phone_numbers=[]))

    assert updated.phone_numbers == []


async def test_update_uc06_whitespace_name_stored_as_provided() -> None:
    """UC06: service does not strip whitespace from name on update."""
    service, repo = make_service()
    owner = repo.add(make_owner())

    updated = await service.update(owner.id, HorseOwnerUpdateDto(name="  Пробел  "))

    assert updated.name == "  Пробел  "


async def test_update_uc07_unicode_name() -> None:
    """UC07: unicode characters accepted in updated name."""
    service, repo = make_service()
    owner = repo.add(make_owner())

    updated = await service.update(owner.id, HorseOwnerUpdateDto(name="José García"))

    assert updated.name == "José García"


async def test_update_uc08_phone_boundary_min_7_digits() -> None:
    """UC08: phone with exactly 7 digits after '+' accepted on update."""
    service, repo = make_service()
    owner = repo.add(make_owner())

    updated = await service.update(
        owner.id, HorseOwnerUpdateDto(phone_numbers=["+1234567"])
    )

    assert "+1234567" in updated.phone_numbers


async def test_update_uc09_phone_below_min_raises_client_error() -> None:
    """UC09: phone with fewer than 7 digits after '+' raises ClientError on update."""
    service, repo = make_service()
    owner = repo.add(make_owner())

    with pytest.raises(ClientError, match="Неверный формат"):
        await service.update(owner.id, HorseOwnerUpdateDto(phone_numbers=["+12345"]))

    # update() in repo must NOT have been called
    assert "update" not in [name for name, _ in repo.calls]


async def test_update_uc10_phone_boundary_max_15_digits() -> None:
    """UC10: phone with exactly 15 digits after '+' accepted on update."""
    service, repo = make_service()
    owner = repo.add(make_owner())

    updated = await service.update(
        owner.id, HorseOwnerUpdateDto(phone_numbers=["+123456789012345"])
    )

    assert "+123456789012345" in updated.phone_numbers


async def test_update_uc11_phone_above_max_raises_client_error() -> None:
    """UC11: phone with more than 15 digits after '+' raises ClientError on update."""
    service, repo = make_service()
    owner = repo.add(make_owner())

    with pytest.raises(ClientError):
        await service.update(
            owner.id, HorseOwnerUpdateDto(phone_numbers=["+1234567890123456"])
        )


async def test_update_uc12_nonexistent_id_raises_client_error() -> None:
    """UC12: using a random UUID that doesn't exist raises ClientError."""
    service, _ = make_service()

    with pytest.raises(ClientError, match="Владелец не найден"):
        await service.update(uuid4(), HorseOwnerUpdateDto(name="X"))


async def test_update_uc13_not_found_raises_client_error() -> None:
    """UC13: repository returns None → service raises ClientError."""
    service, _ = make_service()

    with pytest.raises(ClientError):
        await service.update(uuid4(), HorseOwnerUpdateDto(name="Новый"))


async def test_update_uc14_repository_update_failure_propagates() -> None:
    """UC14: repository.update raises → exception propagates unchanged."""
    service, repo = make_service()
    owner = repo.add(make_owner())
    repo.fail_on.add("update")

    with pytest.raises(RepositoryError):
        await service.update(owner.id, HorseOwnerUpdateDto(name="Сбой"))


async def test_update_uc15_update_existing_owner_no_conflict() -> None:
    """UC15: updating an owner with its own data (no unique-field conflict) succeeds."""
    service, repo = make_service()
    owner = repo.add(make_owner(name="Тот же"))

    updated = await service.update(owner.id, HorseOwnerUpdateDto(name="Тот же"))

    assert updated.name == "Тот же"


async def test_update_uc16_no_extra_repo_lookups() -> None:
    """UC16: update calls get_by_id then update — no additional repository methods."""
    service, repo = make_service()
    owner = repo.add(make_owner())

    await service.update(owner.id, HorseOwnerUpdateDto(name="Проверка"))

    method_names = [name for name, _ in repo.calls]
    assert method_names == ["get_by_id", "update"]


async def test_update_uc17_valid_call_not_blocked() -> None:
    """UC17: no auth layer — any valid call succeeds."""
    service, repo = make_service()
    owner = repo.add(make_owner())

    result = await service.update(owner.id, HorseOwnerUpdateDto(name="Разрешено"))

    assert result is not None


@pytest.mark.skip(reason="No auth in HorseOwnerService — permission tests belong to API layer")
async def test_update_uc18_permission_denied_na() -> None:
    """UC18: N/A — no auth in service layer."""
    ...


async def test_update_uc19_partial_update_only_specified_fields() -> None:
    """UC19: only explicitly provided fields are updated."""
    service, repo = make_service()
    owner = repo.add(
        make_owner(
            name="Старый",
            description="Описание",
            type=HorseOwnerType.person,
            address="Адрес",
            phone_numbers=["+71234567890"],
        )
    )

    updated = await service.update(owner.id, HorseOwnerUpdateDto(name="Новый"))

    assert updated.name == "Новый"
    assert updated.description == "Описание"
    assert updated.address == "Адрес"
    assert updated.phone_numbers == ["+71234567890"]


async def test_update_uc20_empty_payload_raises_client_error() -> None:
    """UC20: DTO with all-None fields raises ClientError('Нет данных для обновления')."""
    service, repo = make_service()
    owner = repo.add(make_owner())

    with pytest.raises(ClientError, match="Нет данных"):
        await service.update(owner.id, HorseOwnerUpdateDto())

    # repository.update must NOT have been called
    assert "update" not in [name for name, _ in repo.calls]


async def test_update_uc21_repository_failure_entity_not_deleted() -> None:
    """UC21: when repository.update fails, the entity remains in the repo."""
    service, repo = make_service()
    owner = repo.add(make_owner())
    repo.fail_on.add("update")

    with pytest.raises(RepositoryError):
        await service.update(owner.id, HorseOwnerUpdateDto(name="Сбой"))

    assert owner.id in repo.by_id


async def test_update_uc22_get_by_id_called_before_update() -> None:
    """UC22: get_by_id is called before update — dependency order preserved."""
    service, repo = make_service()
    owner = repo.add(make_owner())

    await service.update(owner.id, HorseOwnerUpdateDto(name="Порядок"))

    method_names = [name for name, _ in repo.calls]
    assert method_names.index("get_by_id") < method_names.index("update")


async def test_update_uc23_rollback_intent_update_not_called_on_not_found() -> None:
    """UC23: when get_by_id returns None, repository.update is never called."""
    service, repo = make_service()

    with pytest.raises(ClientError):
        await service.update(uuid4(), HorseOwnerUpdateDto(name="X"))

    assert "update" not in [name for name, _ in repo.calls]


async def test_update_uc24_idempotency_multiple_updates() -> None:
    """UC24: calling update twice with same data is safe."""
    service, repo = make_service()
    owner = repo.add(make_owner())

    first = await service.update(owner.id, HorseOwnerUpdateDto(name="Одинаково"))
    second = await service.update(owner.id, HorseOwnerUpdateDto(name="Одинаково"))

    assert first.name == second.name


@pytest.mark.skip(reason="sort parameter does not apply to update()")
async def test_update_uc25_sorting_na() -> None:
    """UC25: N/A for update — sort is not applicable."""
    ...


@pytest.mark.skip(reason="filter parameters do not apply to update()")
async def test_update_uc26_filtering_na() -> None:
    """UC26: N/A for update — filter parameters not applicable."""
    ...


@pytest.mark.skip(reason="pagination does not apply to update()")
async def test_update_uc27_pagination_na() -> None:
    """UC27: N/A for update — pagination not applicable."""
    ...


async def test_update_uc28_serialization_updated_fields_returned() -> None:
    """UC28: returned entity reflects all updated fields correctly."""
    service, repo = make_service()
    owner = repo.add(make_owner())

    updated = await service.update(
        owner.id,
        HorseOwnerUpdateDto(
            name="Обновлённый",
            description="Новое",
            phone_numbers=["+79991234567"],
        ),
    )

    assert updated.name == "Обновлённый"
    assert updated.description == "Новое"
    assert updated.phone_numbers == ["+79991234567"]
    assert updated.id == owner.id


async def test_update_uc29_invalid_phone_raises_client_error() -> None:
    """UC29: invalid phone in update raises ClientError (→ HTTP 400), not 422."""
    service, repo = make_service()
    owner = repo.add(make_owner())

    with pytest.raises(ClientError):
        await service.update(
            owner.id, HorseOwnerUpdateDto(phone_numbers=["not-a-phone"])
        )


async def test_update_uc30_architecture_boundary() -> None:
    """UC30: service module does not import FastAPI or SQLAlchemy."""
    import core.services.horse_owner as svc_module

    assert "fastapi" not in dir(svc_module)
    assert "sqlalchemy" not in dir(svc_module)


# ===========================================================================
# get_by_id() and get_by_id_or_raise()
# ===========================================================================


async def test_get_by_id_uc01_returns_existing_owner() -> None:
    """UC01: get_by_id returns the entity when it exists."""
    service, repo = make_service()
    owner = repo.add(make_owner())

    result = await service.get_by_id(owner.id)

    assert result == owner


async def test_get_by_id_uc02_returns_none_for_missing() -> None:
    """UC02: get_by_id returns None when owner does not exist."""
    service, _ = make_service()

    result = await service.get_by_id(uuid4())

    assert result is None


async def test_get_by_id_uc12_random_uuid_returns_none() -> None:
    """UC12: a random UUID yields None (not found)."""
    service, _ = make_service()

    assert await service.get_by_id(uuid4()) is None


async def test_get_by_id_uc21_repository_failure_propagates() -> None:
    """UC21: repository raises → exception propagates."""
    service, repo = make_service()
    repo.fail_on.add("get_by_id")

    with pytest.raises(RepositoryError):
        await service.get_by_id(uuid4())


async def test_get_by_id_or_raise_uc01_returns_existing_owner() -> None:
    """UC01: get_by_id_or_raise returns entity when found."""
    service, repo = make_service()
    owner = repo.add(make_owner())

    result = await service.get_by_id_or_raise(owner.id)

    assert result == owner


async def test_get_by_id_or_raise_uc13_not_found_raises_client_error() -> None:
    """UC13: get_by_id_or_raise raises ClientError when entity is missing."""
    service, _ = make_service()

    with pytest.raises(ClientError, match="Владелец не найден"):
        await service.get_by_id_or_raise(uuid4())


async def test_get_by_id_or_raise_uc30_no_http_exception() -> None:
    """UC30: get_by_id_or_raise raises ClientError, never HTTPException."""
    service, _ = make_service()

    exc = None
    try:
        await service.get_by_id_or_raise(uuid4())
    except ClientError as e:
        exc = e

    assert exc is not None
    assert type(exc).__name__ == "ClientError"


# ===========================================================================
# delete()
# ===========================================================================


async def test_delete_uc01_happy_path() -> None:
    """UC01: delete existing owner — entity removed from repo."""
    service, repo = make_service()
    owner = repo.add(make_owner())

    await service.delete(owner.id)

    assert owner.id not in repo.by_id
    assert [name for name, _ in repo.calls] == ["get_by_id", "delete"]


async def test_delete_uc02_only_required_id() -> None:
    """UC02: delete requires only an id — no other parameters needed."""
    service, repo = make_service()
    owner = repo.add(make_owner())

    await service.delete(owner.id)

    assert owner.id not in repo.by_id


async def test_delete_uc12_random_uuid_raises_client_error() -> None:
    """UC12: random UUID raises ClientError without calling delete."""
    service, repo = make_service()

    with pytest.raises(ClientError, match="Владелец не найден"):
        await service.delete(uuid4())

    assert "delete" not in [name for name, _ in repo.calls]


async def test_delete_uc13_not_found_raises_client_error() -> None:
    """UC13: when get_by_id returns None, ClientError is raised."""
    service, _ = make_service()

    with pytest.raises(ClientError):
        await service.delete(uuid4())


async def test_delete_uc14_repository_delete_failure_propagates() -> None:
    """UC14: repository.delete raises → exception propagates."""
    service, repo = make_service()
    owner = repo.add(make_owner())
    repo.fail_on.add("delete")

    with pytest.raises(RepositoryError):
        await service.delete(owner.id)


async def test_delete_uc21_repository_failure_entity_still_in_repo() -> None:
    """UC21: when repository.delete fails, entity remains in fake repo."""
    service, repo = make_service()
    owner = repo.add(make_owner())
    repo.fail_on.add("delete")

    with pytest.raises(RepositoryError):
        await service.delete(owner.id)

    assert owner.id in repo.by_id


async def test_delete_uc22_get_by_id_called_before_delete() -> None:
    """UC22: get_by_id is invoked before delete."""
    service, repo = make_service()
    owner = repo.add(make_owner())

    await service.delete(owner.id)

    method_names = [name for name, _ in repo.calls]
    assert method_names.index("get_by_id") < method_names.index("delete")


async def test_delete_uc23_rollback_intent_delete_not_called_on_not_found() -> None:
    """UC23: if not found, delete is never called on the repository."""
    service, repo = make_service()

    with pytest.raises(ClientError):
        await service.delete(uuid4())

    assert "delete" not in [name for name, _ in repo.calls]


# ===========================================================================
# get_filtered()
# ===========================================================================


async def test_get_filtered_uc01_happy_path() -> None:
    """UC01: get_filtered with all params returns what the repository returns."""
    service, repo = make_service()
    owner = make_owner()
    repo.filtered_result = ([owner], 1)

    entities, total = await service.get_filtered(name="Иванов")

    assert entities == [owner]
    assert total == 1


async def test_get_filtered_uc02_minimal_no_params() -> None:
    """UC02: get_filtered with no params passes all-None to repository."""
    service, repo = make_service()

    entities, total = await service.get_filtered()

    assert entities == []
    assert total == 0
    _, filters = repo.calls[0]
    assert all(v is None for v in filters.values())


async def test_get_filtered_uc03_full_input_all_params_passed_through() -> None:
    """UC03: all filter params are forwarded to the repository."""
    service, repo = make_service()

    await service.get_filtered(
        name="Иванов",
        description="Коневод",
        type=["person"],
        address="Москва",
        phone_numbers="+7",
        sort=["name"],
        limit=10,
        offset=5,
    )

    _, filters = repo.calls[0]
    assert filters["name"] == "Иванов"
    assert filters["description"] == "Коневод"
    assert filters["type"] == ["person"]
    assert filters["address"] == "Москва"
    assert filters["phone_numbers"] == "+7"
    assert filters["sort"] == ["name"]
    assert filters["limit"] == 10
    assert filters["offset"] == 5


async def test_get_filtered_uc04_omitted_optional_defaults_to_none() -> None:
    """UC04: omitted optional params are passed as None."""
    service, repo = make_service()

    await service.get_filtered(name="Иванов")

    _, filters = repo.calls[0]
    assert filters["description"] is None
    assert filters["type"] is None


async def test_get_filtered_uc25_sort_parameter_passed_through() -> None:
    """UC25: sort parameter is passed directly to the repository without transformation."""
    service, repo = make_service()

    await service.get_filtered(sort=["-name", "type"])

    _, filters = repo.calls[0]
    assert filters["sort"] == ["-name", "type"]


async def test_get_filtered_uc26_multiple_filters_all_passed() -> None:
    """UC26: multiple filter params are all forwarded correctly."""
    service, repo = make_service()

    await service.get_filtered(name="X", type=["company"], address="СПб")

    _, filters = repo.calls[0]
    assert filters["name"] == "X"
    assert filters["type"] == ["company"]
    assert filters["address"] == "СПб"


async def test_get_filtered_uc27_pagination_limit_offset_passed_through() -> None:
    """UC27: limit and offset are forwarded without modification."""
    service, repo = make_service()

    await service.get_filtered(limit=20, offset=40)

    _, filters = repo.calls[0]
    assert filters["limit"] == 20
    assert filters["offset"] == 40


async def test_get_filtered_uc21_repository_failure_propagates() -> None:
    """UC21: repository raises → exception propagates from get_filtered."""
    service, repo = make_service()
    repo.fail_on.add("get_filtered")

    with pytest.raises(RepositoryError):
        await service.get_filtered(limit=1)


async def test_get_filtered_uc28_result_entities_returned_unchanged() -> None:
    """UC28: entities returned from the repo are returned unchanged by the service."""
    service, repo = make_service()
    owner = make_owner(name="Фильтрованный")
    repo.filtered_result = ([owner], 5)

    entities, total = await service.get_filtered()

    assert entities[0] is owner
    assert total == 5


async def test_get_filtered_uc30_architecture_boundary() -> None:
    """UC30: get_filtered does not import FastAPI or SQLAlchemy."""
    import core.services.horse_owner as svc_module

    assert "fastapi" not in dir(svc_module)
    assert "sqlalchemy" not in dir(svc_module)
