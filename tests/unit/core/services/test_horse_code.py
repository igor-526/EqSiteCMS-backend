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
    "pedigree_name",
    [None, "", " ", "  AB  ", "Кличка-№1/🐎", "a" * 63],
    ids=["null", "empty", "space", "spaces-preserved", "unicode", "max-63"],
)
def test_entity_accepts_and_preserves_valid_pedigree_name(
    pedigree_name: str | None,
) -> None:
    assert make_horse(pedigree_name=pedigree_name).pedigree_name == pedigree_name


@pytest.mark.parametrize("size", [64, 65, 128])
def test_entity_rejects_pedigree_name_over_63(size: int) -> None:
    with pytest.raises(ValidationError):
        make_horse(pedigree_name="x" * size)


@pytest.mark.parametrize(
    "payload, expected",
    [
        ({"name": "Буран"}, None),
        ({"name": "Буран", "pedigree_name": None}, None),
        ({"name": "Буран", "pedigree_name": ""}, ""),
        ({"name": "Буран", "pedigree_name": "  X  "}, "  X  "),
        ({"name": "Буран", "pedigree_name": "Юникод/№"}, "Юникод/№"),
        ({"name": "Буран", "pedigree_name": "x" * 63}, "x" * 63),
    ],
    ids=["omitted", "null", "empty", "spaces", "unicode", "max-63"],
)
def test_create_dto_accepts_and_preserves_pedigree_name(
    payload: dict[str, object], expected: str | None
) -> None:
    assert HorseCreateInDto.model_validate(payload).pedigree_name == expected


@pytest.mark.parametrize("size", [64, 65, 100])
def test_create_dto_rejects_pedigree_name_over_63(size: int) -> None:
    with pytest.raises(ValidationError):
        HorseCreateInDto(name="Буран", pedigree_name="x" * size)


@pytest.mark.parametrize(
    "payload, is_set, expected",
    [
        ({}, False, None),
        ({"name": "Новое имя"}, False, None),
        ({"pedigree_name": None}, True, None),
        ({"pedigree_name": ""}, True, ""),
        ({"pedigree_name": "  X  "}, True, "  X  "),
        ({"pedigree_name": "Кличка🐎"}, True, "Кличка🐎"),
        ({"pedigree_name": "x" * 63}, True, "x" * 63),
    ],
    ids=[
        "omitted",
        "omitted-with-other",
        "explicit-null",
        "empty",
        "spaces",
        "unicode",
        "max-63",
    ],
)
def test_update_dto_tracks_and_preserves_pedigree_name(
    payload: dict[str, object], is_set: bool, expected: str | None
) -> None:
    dto = HorseUpdateInDto.model_validate(payload)
    assert ("pedigree_name" in dto.model_fields_set) is is_set
    assert dto.pedigree_name == expected
    assert ("pedigree_name" in dto.model_dump(exclude_unset=True)) is is_set


@pytest.mark.parametrize("size", [64, 65, 99])
def test_update_dto_rejects_pedigree_name_over_63(size: int) -> None:
    with pytest.raises(ValidationError):
        HorseUpdateInDto(pedigree_name="x" * size)


@pytest.mark.parametrize("pedigree_name", [None, "", "ABC", "Кличка🐎"])
def test_out_dto_serializes_pedigree_name_exactly(
    pedigree_name: str | None,
) -> None:
    dto = HorseOutDto(
        id=uuid4(), slug="buran", name="Буран", pedigree_name=pedigree_name
    )
    payload = dto.model_dump(mode="json")
    assert payload["pedigree_name"] == pedigree_name
    assert "code" not in payload


def test_database_column_contract_is_nullable_varchar_63_without_uniqueness() -> None:
    column = horse_table.c.pedigree_name
    assert column.nullable is True
    assert isinstance(column.type, String)
    assert column.type.length == 63
    assert column.default is None
    assert column.server_default is None
    assert column.unique is not True
    assert column.index is not True


def test_entity_model_dump_contains_pedigree_name_not_code() -> None:
    payload = make_horse(pedigree_name="EXT-1").model_dump()
    assert payload["pedigree_name"] == "EXT-1"
    assert "code" not in payload
