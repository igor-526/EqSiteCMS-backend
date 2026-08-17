from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import String

from core.entities import Horse
from core.schemas import HorseCreateInDto, HorseOutDto, HorseUpdateInDto
from models.horse import horse as horse_table


def make_horse(**values: object) -> Horse:
    data: dict[str, object] = {
        "equestrian_id": uuid4(),
        "name": "Буран",
        "slug": "buran",
    }
    data.update(values)
    return Horse(**data)


@pytest.mark.parametrize(
    "code",
    [None, "", " ", "  AB  ", "КОД-№1/🐎", "a" * 31],
    ids=["null", "empty", "space", "spaces-preserved", "unicode", "max-31"],
)
def test_entity_accepts_and_preserves_valid_code(code: str | None) -> None:
    assert make_horse(code=code).code == code


@pytest.mark.parametrize("size", [32, 33, 64, 128])
def test_entity_rejects_code_over_31(size: int) -> None:
    with pytest.raises(ValidationError):
        make_horse(code="x" * size)


@pytest.mark.parametrize(
    "payload, expected",
    [
        ({"name": "Буран"}, None),
        ({"name": "Буран", "code": None}, None),
        ({"name": "Буран", "code": ""}, ""),
        ({"name": "Буран", "code": "  X  "}, "  X  "),
        ({"name": "Буран", "code": "Юникод/№"}, "Юникод/№"),
        ({"name": "Буран", "code": "x" * 31}, "x" * 31),
    ],
    ids=["omitted", "null", "empty", "spaces", "unicode", "max-31"],
)
def test_create_dto_accepts_and_preserves_code(
    payload: dict[str, object], expected: str | None
) -> None:
    assert HorseCreateInDto.model_validate(payload).code == expected


@pytest.mark.parametrize("size", [32, 40, 63, 100])
def test_create_dto_rejects_code_over_31(size: int) -> None:
    with pytest.raises(ValidationError):
        HorseCreateInDto(name="Буран", code="x" * size)


@pytest.mark.parametrize(
    "payload, is_set, expected",
    [
        ({}, False, None),
        ({"name": "Новое имя"}, False, None),
        ({"code": None}, True, None),
        ({"code": ""}, True, ""),
        ({"code": "  X  "}, True, "  X  "),
        ({"code": "КОД🐎"}, True, "КОД🐎"),
        ({"code": "x" * 31}, True, "x" * 31),
    ],
    ids=[
        "omitted",
        "omitted-with-other",
        "explicit-null",
        "empty",
        "spaces",
        "unicode",
        "max-31",
    ],
)
def test_update_dto_tracks_and_preserves_code(
    payload: dict[str, object], is_set: bool, expected: str | None
) -> None:
    dto = HorseUpdateInDto.model_validate(payload)
    assert ("code" in dto.model_fields_set) is is_set
    assert dto.code == expected
    assert ("code" in dto.model_dump(exclude_unset=True)) is is_set


@pytest.mark.parametrize("size", [32, 48, 99])
def test_update_dto_rejects_code_over_31(size: int) -> None:
    with pytest.raises(ValidationError):
        HorseUpdateInDto(code="x" * size)


@pytest.mark.parametrize("code", [None, "", "ABC", "КОД🐎"])
def test_out_dto_serializes_code_exactly(code: str | None) -> None:
    dto = HorseOutDto(id=uuid4(), slug="buran", name="Буран", code=code)
    assert dto.model_dump(mode="json")["code"] == code


def test_database_column_contract_is_nullable_varchar_31_without_uniqueness() -> None:
    column = horse_table.c.code
    assert column.nullable is True
    assert isinstance(column.type, String)
    assert column.type.length == 31
    assert column.default is None
    assert column.server_default is None
    assert column.unique is not True
    assert column.index is not True


def test_entity_model_dump_contains_code() -> None:
    assert make_horse(code="EXT-1").model_dump()["code"] == "EXT-1"
