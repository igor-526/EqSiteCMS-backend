from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import ClauseElement

from core.entities import Horse
from core.entities.horse import HorseKindEnum, HorseSexEnum
from repositories.horse_repository import HorseRepository


class FakePhotoUrlBuilder:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def build(self, filename: str) -> str:
        self.calls.append(filename)
        return f"http://localhost:9000/gallery/{filename}"


class FakeExecuteResult:
    def mappings(self) -> "FakeExecuteResult":
        return self

    def all(self) -> list[dict]:
        return []

    def scalar(self) -> int:
        return 0

    def scalar_one_or_none(self) -> None:
        return None


class FakeAsyncSession:
    def __init__(self) -> None:
        self.statements: list[ClauseElement] = []

    async def execute(self, statement: ClauseElement) -> FakeExecuteResult:
        self.statements.append(statement)
        return FakeExecuteResult()

    async def flush(self) -> None:
        return None


def compile_sql(statement: ClauseElement) -> str:
    return str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


def test_horse_repository_builds_photo_urls_with_injected_builder() -> None:
    builder = FakePhotoUrlBuilder()
    repository = HorseRepository(
        session=object(),  # type: ignore[arg-type]
        photo_url_builder=builder,
    )

    dto = repository._build_horse_dto(
        horse_data={
            "id": UUID("11111111-1111-4111-8111-111111111111"),
            "slug": "winter-star",
            "name": "Winter Star",
            "sex": "female",
        },
        breed_data=None,
        coat_color_data=None,
        horse_owner_data=None,
        photos_data=[
            {
                "photo_id": UUID("22222222-2222-4222-8222-222222222222"),
                "is_main": True,
                "path": "horse.jpg",
            }
        ],
        services_data=[],
    )

    assert builder.calls == ["horse.jpg"]
    assert dto.photos[0].url == "http://localhost:9000/gallery/horse.jpg"
    assert "/media/" not in dto.photos[0].url
    assert "kind" not in dto.model_dump()


def test_horse_repository_full_info_mapper_preserves_pedigree_name() -> None:
    repository = HorseRepository(
        session=object(),  # type: ignore[arg-type]
        photo_url_builder=FakePhotoUrlBuilder(),
    )
    dto = repository._build_horse_dto(
        horse_data={
            "id": uuid4(),
            "slug": "buran",
            "name": "Буран",
            "pedigree_name": " Кличка🐎 ",
            "sex": "male",
        },
        breed_data=None,
        coat_color_data=None,
        horse_owner_data=None,
        photos_data=[],
        services_data=[],
    )

    assert dto.pedigree_name == " Кличка🐎 "


@pytest.mark.asyncio
async def test_horse_repository_insert_and_update_pedigree_name() -> None:
    session = FakeAsyncSession()
    repository = HorseRepository(
        session=session,  # type: ignore[arg-type]
        photo_url_builder=FakePhotoUrlBuilder(),
    )
    tenant_id = uuid4()
    item = Horse(
        equestrian_id=tenant_id,
        name="Буран",
        slug="buran",
        pedigree_name="EXT-1",
    )

    await repository.create(item)
    item.pedigree_name = None
    await repository.update(item)

    insert_sql = compile_sql(session.statements[0])
    update_sql = compile_sql(session.statements[1])
    assert "pedigree_name" in insert_sql and "'EXT-1'" in insert_sql
    assert "pedigree_name=NULL" in update_sql
    assert str(tenant_id) in update_sql


@pytest.mark.asyncio
async def test_horse_list_query_keeps_limit_and_offset_with_pedigree_name() -> None:
    session = FakeAsyncSession()
    repository = HorseRepository(
        session=session,  # type: ignore[arg-type]
        photo_url_builder=FakePhotoUrlBuilder(),
    )

    await repository.get_horse_list_full_info(equestrian_id=uuid4(), limit=7, offset=3)

    sql = compile_sql(session.statements[0])
    assert "horse.pedigree_name" in sql
    assert "LIMIT 7" in sql
    assert "OFFSET 3" in sql


@pytest.mark.asyncio
async def test_horse_repository_kind_filter_uses_breed_kind_column() -> None:
    session = FakeAsyncSession()
    repository = HorseRepository(
        session=session,  # type: ignore[arg-type]
        photo_url_builder=FakePhotoUrlBuilder(),
    )

    await repository.get_horse_list_full_info(
        equestrian_id=UUID("11111111-1111-4111-8111-111111111111"),
        kind=[HorseKindEnum.PONY],
    )

    sql = compile_sql(session.statements[0])
    assert "breeds.kind IN ('pony')" in sql
    assert "horse.kind" not in sql


@pytest.mark.asyncio
async def test_horse_repository_kind_sort_uses_breed_kind_column() -> None:
    session = FakeAsyncSession()
    repository = HorseRepository(
        session=session,  # type: ignore[arg-type]
        photo_url_builder=FakePhotoUrlBuilder(),
    )

    await repository.get_horse_list_full_info(
        equestrian_id=UUID("11111111-1111-4111-8111-111111111111"),
        sort=["-kind"],
    )

    sql = compile_sql(session.statements[0])
    assert "ORDER BY breeds.kind DESC NULLS LAST" in sql
    assert "horse.kind" not in sql


@pytest.mark.asyncio
async def test_horse_repository_can_filter_candidates_without_breed() -> None:
    session = FakeAsyncSession()
    repository = HorseRepository(
        session=session,  # type: ignore[arg-type]
        photo_url_builder=FakePhotoUrlBuilder(),
    )

    await repository.get_horse_list_full_info(
        equestrian_id=UUID("11111111-1111-4111-8111-111111111111"),
        breed_id_is_null=True,
    )

    sql = compile_sql(session.statements[0])
    assert "horse.breed_id IS NULL" in sql
    assert "horse.kind" not in sql


@pytest.mark.parametrize(
    ("method_name", "target_sex", "target_has_breed"),
    [
        ("get_available_sires", HorseSexEnum.FEMALE, True),
        ("get_available_sires", HorseSexEnum.FEMALE, False),
        ("get_available_dams", HorseSexEnum.MALE, True),
        ("get_available_dams", HorseSexEnum.MALE, False),
        ("get_available_children", HorseSexEnum.FEMALE, True),
        ("get_available_children", HorseSexEnum.MALE, False),
    ],
    ids=[
        "sire-target-with-breed",
        "sire-target-without-breed",
        "dam-target-with-breed",
        "dam-target-without-breed",
        "children-target-with-breed",
        "children-target-without-breed",
    ],
)
@pytest.mark.asyncio
async def test_pedigree_candidate_queries_do_not_filter_or_lookup_breed(
    method_name: str,
    target_sex: HorseSexEnum,
    target_has_breed: bool,
) -> None:
    session = FakeAsyncSession()
    repository = HorseRepository(
        session=session,  # type: ignore[arg-type]
        photo_url_builder=FakePhotoUrlBuilder(),
    )
    target = Horse(
        equestrian_id=UUID("11111111-1111-4111-8111-111111111111"),
        name="Target",
        slug="target",
        sex=target_sex,
        breed_id=uuid4() if target_has_breed else None,
    )

    method = getattr(repository, method_name)
    await method(
        target_horse=target,
        search="Cross breed",
        exclude_ids=[UUID("22222222-2222-4222-8222-222222222222")],
        limit=7,
        offset=3,
    )

    sql_statements = [compile_sql(statement) for statement in session.statements]
    assert len(sql_statements) == 2  # result query + count; no breed-kind lookup
    assert all("breeds.kind IN" not in sql for sql in sql_statements)
    assert all("horse.breed_id IS NULL" not in sql for sql in sql_statements)
    assert "ORDER BY horse.name ASC NULLS FIRST" in sql_statements[0]
    assert "LIMIT 7" in sql_statements[0]
    assert "OFFSET 3" in sql_statements[0]


@pytest.mark.parametrize(
    ("method_name", "expected_sql"),
    [
        ("get_available_sires", "horse.sex IN ('male')"),
        ("get_available_dams", "horse.sex IN ('female')"),
        ("get_available_children", "horse.id NOT IN (SELECT horse_children.child_id"),
    ],
)
@pytest.mark.asyncio
async def test_pedigree_candidate_queries_keep_non_breed_filters(
    method_name: str, expected_sql: str
) -> None:
    session = FakeAsyncSession()
    repository = HorseRepository(
        session=session,  # type: ignore[arg-type]
        photo_url_builder=FakePhotoUrlBuilder(),
    )
    target = Horse(
        equestrian_id=uuid4(),
        name="Target",
        slug="target",
        sex=HorseSexEnum.FEMALE,
    )

    await getattr(repository, method_name)(target_horse=target)

    sql = compile_sql(session.statements[0])
    assert expected_sql in sql
    assert str(target.id) in sql


def test_horse_repository_module_does_not_depend_on_backend_media_settings() -> None:
    import inspect

    import repositories.horse_repository as horse_repository_module

    source = inspect.getsource(horse_repository_module)

    assert "cms_backend_domain" not in source
    assert "/media/" not in source
