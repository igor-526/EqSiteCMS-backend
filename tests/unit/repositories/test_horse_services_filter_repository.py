from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import ClauseElement

from core.entities import HorseKindEnum
from repositories.horse_repository import HorseRepository

TENANT_ID = UUID("11111111-1111-4111-8111-111111111111")
FOREIGN_TENANT_ID = UUID("22222222-2222-4222-8222-222222222222")
SERVICE_A = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
SERVICE_B = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")


class FakePhotoUrlBuilder:
    def build(self, filename: str) -> str:
        return filename


class EmptyResult:
    def mappings(self) -> EmptyResult:
        return self

    def all(self) -> list[dict]:
        return []

    def scalar(self) -> int:
        return 0


class CapturingSession:
    def __init__(self) -> None:
        self.statements: list[ClauseElement] = []

    async def execute(self, statement: ClauseElement) -> EmptyResult:
        self.statements.append(statement)
        return EmptyResult()


class FailingSession(CapturingSession):
    async def execute(self, statement: ClauseElement) -> EmptyResult:
        self.statements.append(statement)
        raise RuntimeError("database unavailable")


def _sql(statement: ClauseElement) -> str:
    return str(
        statement.compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )


async def _queries(**kwargs: object) -> tuple[str, str]:
    session = CapturingSession()
    repository = HorseRepository(
        session=session,  # type: ignore[arg-type]
        photo_url_builder=FakePhotoUrlBuilder(),
    )
    await repository.get_horse_list_full_info(
        equestrian_id=TENANT_ID,
        **kwargs,  # type: ignore[arg-type]
    )
    assert len(session.statements) == 2
    return _sql(session.statements[0]), _sql(session.statements[1])


@pytest.mark.asyncio
@pytest.mark.parametrize("services", [None, []])
async def test_missing_or_empty_services_adds_no_service_predicate(
    services: list[UUID] | None,
) -> None:
    items_sql, count_sql = await _queries(services=services)

    assert "EXISTS" not in items_sql
    assert "EXISTS" not in count_sql


@pytest.mark.asyncio
async def test_one_service_builds_tenant_safe_correlated_exists() -> None:
    items_sql, _ = await _queries(services=[SERVICE_A])

    assert "EXISTS (SELECT 1" in items_sql
    assert "horse_service_relations.horse_id = horse.id" in items_sql
    assert (
        "horse_service.equestrian_id = '11111111-1111-4111-8111-111111111111'"
        in items_sql
    )
    assert str(SERVICE_A) in items_sql


@pytest.mark.asyncio
async def test_two_services_use_one_in_predicate_for_or_semantics() -> None:
    items_sql, _ = await _queries(services=[SERVICE_A, SERVICE_B])

    assert items_sql.count("EXISTS (SELECT 1") == 1
    assert f"horse_service.id IN ('{SERVICE_A}', '{SERVICE_B}')" in items_sql


@pytest.mark.asyncio
async def test_duplicate_service_uuid_is_normalized_before_query() -> None:
    items_sql, _ = await _queries(services=[SERVICE_A, SERVICE_A])

    assert items_sql.count("horse_service.id IN") == 1
    assert items_sql.count(str(SERVICE_A)) == 1


@pytest.mark.asyncio
async def test_service_filter_is_identical_for_items_and_count() -> None:
    items_sql, count_sql = await _queries(services=[SERVICE_A, SERVICE_B])

    for expected in (
        "EXISTS (SELECT 1",
        "horse_service_relations.horse_id = horse.id",
        str(SERVICE_A),
        str(SERVICE_B),
        str(TENANT_ID),
    ):
        assert expected in items_sql
        assert expected in count_sql


@pytest.mark.asyncio
async def test_count_keeps_distinct_horse_semantics() -> None:
    _, count_sql = await _queries(services=[SERVICE_A])

    assert "count(distinct(horse.id))" in count_sql.lower()
    assert "JOIN horse_service_relations ON horse.id" not in count_sql


@pytest.mark.asyncio
async def test_foreign_service_cannot_bypass_requested_tenant_predicate() -> None:
    items_sql, _ = await _queries(services=[SERVICE_B])

    assert str(TENANT_ID) in items_sql
    assert str(FOREIGN_TENANT_ID) not in items_sql
    assert "horse_service.equestrian_id" in items_sql


@pytest.mark.asyncio
async def test_mixed_service_ids_remain_guarded_by_one_tenant_predicate() -> None:
    items_sql, _ = await _queries(services=[SERVICE_A, SERVICE_B])

    assert items_sql.count("horse_service.equestrian_id") == 1
    assert str(SERVICE_A) in items_sql and str(SERVICE_B) in items_sql


@pytest.mark.asyncio
async def test_service_filter_combines_with_name_breed_and_kind() -> None:
    items_sql, _ = await _queries(
        services=[SERVICE_A],
        name="Star",
        breed_ids=[UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")],
        kind=[HorseKindEnum.PONY],
    )

    assert "horse.name ~* 'Star'" in items_sql
    assert "horse.breed_id IN" in items_sql
    assert "breeds.kind IN ('pony')" in items_sql
    assert "EXISTS (SELECT 1" in items_sql


@pytest.mark.asyncio
async def test_service_filter_preserves_sort_limit_and_offset() -> None:
    items_sql, _ = await _queries(
        services=[SERVICE_A], sort=["name"], limit=7, offset=3
    )

    assert "ORDER BY horse.name ASC NULLS FIRST" in items_sql
    assert "LIMIT 7" in items_sql
    assert "OFFSET 3" in items_sql


@pytest.mark.asyncio
async def test_repository_error_is_propagated_without_write_or_partial_state() -> None:
    session = FailingSession()
    repository = HorseRepository(
        session=session,  # type: ignore[arg-type]
        photo_url_builder=FakePhotoUrlBuilder(),
    )

    with pytest.raises(RuntimeError, match="database unavailable"):
        await repository.get_horse_list_full_info(
            equestrian_id=TENANT_ID, services=[SERVICE_A]
        )

    assert len(session.statements) == 1
    assert _sql(session.statements[0]).lstrip().startswith("SELECT")
