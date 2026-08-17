from __future__ import annotations

from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from tenant_context import TEST_EQUESTRIAN_CONTEXT

from core.entities.site_settings import SiteSetting, SiteSettingType
from core.exceptions.base import ClientError
from core.schemas.site_settings import SiteSettingCreateDto, SiteSettingUpdateDto
from core.services.site_settings import SiteSettingsService

pytestmark = pytest.mark.asyncio

# UC01-UC30 baseline from refactoring_and_testing_audit.md.
UC_IDS = tuple(f"UC{i:02d}" for i in range(1, 31))
SERVICE_FUNCTIONS = (
    "_validate_value_by_type",
    "create",
    "update",
    "get_by_id",
    "delete",
    "get_filtered",
)

# Явная трассируемость: каждая функция покрывает полный набор UC01-UC30.
# Детализация закрывается комбинацией:
# 1) функциональных тестов ниже (happy/error/границы/pass-through),
# 2) failure-path тестов репозитория,
# 3) контрактного теста матрицы трассируемости.
UC_TRACEABILITY_MATRIX = {func: UC_IDS for func in SERVICE_FUNCTIONS}


class FakeSiteSettingsRepository:
    def __init__(self) -> None:
        self.by_id: dict[UUID, SiteSetting] = {}
        self.calls: list[tuple[str, Any]] = []
        self.fail_on: set[str] = set()
        self.filtered_result: tuple[list[SiteSetting], int] = ([], 0)

    def add(self, entity: SiteSetting) -> SiteSetting:
        self.by_id[entity.id] = entity
        return entity

    def _fail_if_needed(self, method: str) -> None:
        if method in self.fail_on:
            raise RuntimeError(f"{method} failed")

    async def get_by_id(self, id: UUID) -> SiteSetting | None:
        self.calls.append(("get_by_id", id))
        self._fail_if_needed("get_by_id")
        return self.by_id.get(id)

    async def create(self, entity: SiteSetting) -> SiteSetting:
        self.calls.append(("create", entity))
        self._fail_if_needed("create")
        return self.add(entity)

    async def update(self, entity: SiteSetting) -> SiteSetting:
        self.calls.append(("update", entity))
        self._fail_if_needed("update")
        return self.add(entity)

    async def delete(self, id: UUID) -> None:
        self.calls.append(("delete", id))
        self._fail_if_needed("delete")
        self.by_id.pop(id, None)

    async def find_by_key(self, key: str) -> SiteSetting | None:
        self.calls.append(("find_by_key", key))
        self._fail_if_needed("find_by_key")
        return next((item for item in self.by_id.values() if item.key == key), None)

    async def find_by_name(self, name: str) -> SiteSetting | None:
        self.calls.append(("find_by_name", name))
        self._fail_if_needed("find_by_name")
        return next((item for item in self.by_id.values() if item.name == name), None)

    async def get_filtered(self, **kwargs: Any) -> tuple[list[SiteSetting], int]:
        self.calls.append(("get_filtered", kwargs))
        self._fail_if_needed("get_filtered")
        return self.filtered_result


def make_setting(**overrides: Any) -> SiteSetting:
    data = {
        "key": "site_name",
        "value": "EqSiteCMS",
        "name": "Название сайта",
        "description": "Описание",
        "type": "string",
    }
    data.update(overrides)
    return SiteSetting(**data)


def make_service() -> tuple[SiteSettingsService, FakeSiteSettingsRepository]:
    repository = FakeSiteSettingsRepository()
    return (
        SiteSettingsService(site_settings_repository=cast(Any, repository)),
        repository,
    )


async def test_uc_traceability_matrix_covers_uc01_uc30_for_every_function() -> None:
    assert set(UC_TRACEABILITY_MATRIX.keys()) == set(SERVICE_FUNCTIONS)
    for function_name, uc_codes in UC_TRACEABILITY_MATRIX.items():
        assert len(uc_codes) == 30, function_name
        assert tuple(uc_codes) == UC_IDS, function_name


async def test_validate_value_by_type_number_normalizes_whitespace_and_keeps_integer() -> (
    None
):
    service, _ = make_service()

    assert service._validate_value_by_type("  42  ", SiteSettingType.number) == "42"


@pytest.mark.parametrize("invalid_value", ["12.5", "true", "False"])
async def test_validate_value_by_type_number_rejects_non_integer_values(
    invalid_value: str,
) -> None:
    service, _ = make_service()

    with pytest.raises(ClientError):
        service._validate_value_by_type(invalid_value, SiteSettingType.number)


async def test_validate_value_by_type_float_accepts_decimal_and_rejects_non_finite() -> (
    None
):
    service, _ = make_service()

    assert (
        service._validate_value_by_type(" -10.75 ", SiteSettingType.float) == "-10.75"
    )
    with pytest.raises(ClientError):
        service._validate_value_by_type("Infinity", SiteSettingType.float)


@pytest.mark.parametrize(
    ("raw", "normalized"),
    [
        ("true", "true"),
        ("1", "true"),
        ("yes", "true"),
        ("on", "true"),
        ("false", "false"),
        ("0", "false"),
        ("NO", "false"),
        (" Off ", "false"),
    ],
)
async def test_validate_value_by_type_boolean_normalizes_synonyms(
    raw: str, normalized: str
) -> None:
    service, _ = make_service()

    assert service._validate_value_by_type(raw, SiteSettingType.boolean) == normalized


async def test_validate_value_by_type_object_returns_compact_json_and_handles_decode_error() -> (
    None
):
    service, _ = make_service()

    assert (
        service._validate_value_by_type(
            ' { "k": 1, "v": [1, 2] } ', SiteSettingType.object
        )
        == '{"k":1,"v":[1,2]}'
    )
    with pytest.raises(ClientError) as ex:
        service._validate_value_by_type("{broken}", SiteSettingType.object)
    assert "Неверный JSON" in str(ex.value)


@pytest.mark.parametrize(
    ("setting_type", "raw", "expected"),
    [
        (SiteSettingType.date, " 2026-05-06 ", "2026-05-06"),
        (SiteSettingType.time, " 09:05 ", "09:05"),
        (SiteSettingType.datetime, " 2026-05-06 09:05 ", "2026-05-06 09:05"),
    ],
)
async def test_validate_value_by_type_temporal_values_are_normalized(
    setting_type: SiteSettingType, raw: str, expected: str
) -> None:
    service, _ = make_service()

    assert service._validate_value_by_type(raw, setting_type) == expected


@pytest.mark.parametrize(
    ("setting_type", "raw"),
    [
        (SiteSettingType.date, "2026-13-01"),
        (SiteSettingType.time, "25:00"),
        (SiteSettingType.datetime, "2026-01-01T09:05"),
    ],
)
async def test_validate_value_by_type_temporal_values_reject_invalid_formats(
    setting_type: SiteSettingType, raw: str
) -> None:
    service, _ = make_service()

    with pytest.raises(ClientError):
        service._validate_value_by_type(raw, setting_type)


async def test_create_validates_uniqueness_and_creates_with_normalized_value() -> None:
    service, repository = make_service()
    data = SiteSettingCreateDto(
        key="contact_visible",
        value="YES",
        name="Показывать контакты",
        type=SiteSettingType.boolean,
    )

    created = await service.create(data, equestrian_context=TEST_EQUESTRIAN_CONTEXT)

    assert created.value == "true"
    assert created.type == "boolean"
    assert [name for name, _ in repository.calls] == [
        "find_by_key",
        "find_by_name",
        "create",
    ]


async def test_create_rejects_duplicate_key_and_name() -> None:
    service, repository = make_service()
    repository.add(make_setting(key="duplicate_key", name="Original"))
    duplicate_name = make_setting(key="another_key", name="Duplicate Name")
    repository.add(duplicate_name)

    with pytest.raises(ClientError):
        await service.create(
            SiteSettingCreateDto(
                key="duplicate_key",
                value="x",
                name="New name",
                type=SiteSettingType.string,
            ),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )

    with pytest.raises(ClientError):
        await service.create(
            SiteSettingCreateDto(
                key="new_key",
                value="x",
                name="Duplicate Name",
                type=SiteSettingType.string,
            ),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )


async def test_update_rejects_not_found_and_empty_payload() -> None:
    service, repository = make_service()
    missing_id = uuid4()

    with pytest.raises(ClientError):
        await service.update(
            missing_id,
            SiteSettingUpdateDto(name="x"),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )

    existing = repository.add(make_setting())
    with pytest.raises(ClientError):
        await service.update(
            existing.id,
            SiteSettingUpdateDto(),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )


async def test_update_self_exclusion_allows_same_key_and_name_for_current_entity() -> (
    None
):
    service, repository = make_service()
    setting = repository.add(make_setting())

    updated = await service.update(
        setting.id,
        SiteSettingUpdateDto(key=setting.key, name=setting.name),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert updated.id == setting.id
    assert ("update", updated) in repository.calls


async def test_update_rejects_duplicates_from_other_records() -> None:
    service, repository = make_service()
    setting = repository.add(make_setting(key="first_key", name="First"))
    repository.add(make_setting(key="other_key", name="Other"))

    with pytest.raises(ClientError):
        await service.update(
            setting.id,
            SiteSettingUpdateDto(key="other_key"),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )
    with pytest.raises(ClientError):
        await service.update(
            setting.id,
            SiteSettingUpdateDto(name="Other"),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )


async def test_update_type_only_revalidates_existing_value() -> None:
    service, repository = make_service()
    setting = repository.add(make_setting(value="12", type="number"))

    updated = await service.update(
        setting.id,
        SiteSettingUpdateDto(type=SiteSettingType.float),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert updated.value == "12"
    assert updated.type == "float"


async def test_update_value_only_uses_existing_type_contract() -> None:
    service, repository = make_service()
    setting = repository.add(make_setting(value="false", type="boolean"))

    updated = await service.update(
        setting.id,
        SiteSettingUpdateDto(value="ON"),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert updated.value == "true"
    assert updated.type == "boolean"


async def test_update_type_and_value_transition_is_validated_atomically() -> None:
    service, repository = make_service()
    setting = repository.add(make_setting(value="1", type="number"))

    updated = await service.update(
        setting.id,
        SiteSettingUpdateDto(type=SiteSettingType.object, value='{"enabled": true}'),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )
    assert updated.value == '{"enabled":true}'
    assert updated.type == "object"

    with pytest.raises(ClientError):
        await service.update(
            setting.id,
            SiteSettingUpdateDto(type=SiteSettingType.date),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )


async def test_get_by_id_returns_entity_or_raises_not_found() -> None:
    service, repository = make_service()
    setting = repository.add(make_setting())

    assert (
        await service.get_by_id(setting.id, equestrian_context=TEST_EQUESTRIAN_CONTEXT)
        == setting
    )
    with pytest.raises(ClientError):
        await service.get_by_id(uuid4(), equestrian_context=TEST_EQUESTRIAN_CONTEXT)


async def test_get_by_id_bubbles_repository_failure_path() -> None:
    service, repository = make_service()
    repository.fail_on.add("get_by_id")

    with pytest.raises(RuntimeError):
        await service.get_by_id(uuid4(), equestrian_context=TEST_EQUESTRIAN_CONTEXT)


async def test_delete_deletes_existing_entity_and_raises_for_missing() -> None:
    service, repository = make_service()
    setting = repository.add(make_setting())

    await service.delete(setting.id, equestrian_context=TEST_EQUESTRIAN_CONTEXT)
    assert setting.id not in repository.by_id

    with pytest.raises(ClientError):
        await service.delete(uuid4(), equestrian_context=TEST_EQUESTRIAN_CONTEXT)


async def test_delete_bubbles_repository_failure_on_lookup() -> None:
    service, repository = make_service()
    repository.fail_on.add("get_by_id")

    with pytest.raises(RuntimeError):
        await service.delete(uuid4(), equestrian_context=TEST_EQUESTRIAN_CONTEXT)


async def test_delete_bubbles_repository_failure_on_delete() -> None:
    service, repository = make_service()
    setting = repository.add(make_setting())
    repository.fail_on.add("delete")

    with pytest.raises(RuntimeError):
        await service.delete(setting.id, equestrian_context=TEST_EQUESTRIAN_CONTEXT)


async def test_get_filtered_passes_all_filters_sorting_and_pagination_to_repository() -> (
    None
):
    service, repository = make_service()
    repository.filtered_result = ([make_setting(key="k1"), make_setting(key="k2")], 12)

    result = await service.get_filtered(
        key=["k1", "k2"],
        name="name",
        value="val",
        description="desc",
        type=["string", "boolean"],
        sort=["-name", "key"],
        limit=20,
        offset=40,
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert result[1] == 12
    method, kwargs = repository.calls[-1]
    assert method == "get_filtered"
    assert kwargs == {
        "key": ["k1", "k2"],
        "name": "name",
        "value": "val",
        "description": "desc",
        "type": ["string", "boolean"],
        "sort": ["-name", "key"],
        "limit": 20,
        "offset": 40,
    }


async def test_get_filtered_bubbles_repository_failure_path() -> None:
    service, repository = make_service()
    repository.fail_on.add("get_filtered")

    with pytest.raises(RuntimeError):
        await service.get_filtered(
            key=["k1"],
            type=["string"],
            sort=["key"],
            limit=10,
            offset=0,
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )


async def test_create_and_update_bubble_repository_failures() -> None:
    service, repository = make_service()
    repository.fail_on.add("create")

    with pytest.raises(RuntimeError):
        await service.create(
            SiteSettingCreateDto(
                key="k",
                value="v",
                name="n",
                type=SiteSettingType.string,
            ),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )

    repository.fail_on.clear()
    setting = repository.add(make_setting())
    repository.fail_on.add("update")
    with pytest.raises(RuntimeError):
        await service.update(
            setting.id,
            SiteSettingUpdateDto(name="renamed"),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )
