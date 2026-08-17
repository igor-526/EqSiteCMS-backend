from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import ClauseElement

from core.entities.horse import HorseKindEnum
from repositories.breed_repository import BreedRepository

pytestmark = pytest.mark.asyncio


class FakeExecuteResult:
    def mappings(self) -> "FakeExecuteResult":
        return self

    def all(self) -> list[dict]:
        return []

    def scalar(self) -> int:
        return 0


class FakeAsyncSession:
    def __init__(self) -> None:
        self.statements: list[ClauseElement] = []

    async def execute(self, statement: ClauseElement) -> FakeExecuteResult:
        self.statements.append(statement)
        return FakeExecuteResult()


def compile_sql(statement: ClauseElement) -> str:
    return str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


async def test_breed_repository_kind_filter_uses_breeds_kind() -> None:
    session = FakeAsyncSession()
    repository = BreedRepository(session=session)  # type: ignore[arg-type]

    await repository.get_filtered(
        equestrian_id=UUID("11111111-1111-4111-8111-111111111111"),
        kind=[HorseKindEnum.HORSE],
    )

    sql = compile_sql(session.statements[0])
    assert "breeds.kind IN ('horse')" in sql


async def test_breed_repository_kind_filter_accepts_both_values_without_duplicates() -> (
    None
):
    session = FakeAsyncSession()
    repository = BreedRepository(session=session)  # type: ignore[arg-type]

    await repository.get_filtered(
        equestrian_id=UUID("11111111-1111-4111-8111-111111111111"),
        kind=[HorseKindEnum.HORSE, HorseKindEnum.PONY],
    )

    sql = compile_sql(session.statements[0])
    assert "breeds.kind IN ('horse', 'pony')" in sql


async def test_breed_repository_kind_sort_asc_and_desc() -> None:
    session = FakeAsyncSession()
    repository = BreedRepository(session=session)  # type: ignore[arg-type]

    await repository.get_filtered(
        equestrian_id=UUID("11111111-1111-4111-8111-111111111111"),
        sort=["kind", "-kind"],
    )

    sql = compile_sql(session.statements[0])
    assert "ORDER BY breeds.kind ASC, breeds.kind DESC" in sql


@pytest.mark.parametrize(
    ("term", "expected"),
    [("AR", "breeds.short_name ~* 'AR'"), ("a.r", "breeds.short_name ~* 'a\\\\.r'")],
)
async def test_breed_short_name_filter_uses_escaped_case_insensitive_regex(
    term: str, expected: str
) -> None:
    session = FakeAsyncSession()
    repository = BreedRepository(session=session)  # type: ignore[arg-type]

    await repository.get_filtered(
        equestrian_id=UUID("11111111-1111-4111-8111-111111111111"),
        short_name=term,
    )

    assert expected in compile_sql(session.statements[0])


async def test_breed_empty_short_name_does_not_add_filter() -> None:
    session = FakeAsyncSession()
    repository = BreedRepository(session=session)  # type: ignore[arg-type]

    await repository.get_filtered(
        equestrian_id=UUID("11111111-1111-4111-8111-111111111111"), short_name=""
    )

    assert "short_name ~*" not in compile_sql(session.statements[0])


async def test_breed_short_name_keeps_or_semantics_and_tenant_predicate() -> None:
    session = FakeAsyncSession()
    repository = BreedRepository(session=session)  # type: ignore[arg-type]

    await repository.get_filtered(
        equestrian_id=UUID("11111111-1111-4111-8111-111111111111"),
        name="Arabian",
        short_name="AR",
    )

    sql = compile_sql(session.statements[0])
    assert "breeds.equestrian_id = '11111111-1111-4111-8111-111111111111'" in sql
    assert "(breeds.name ~* 'Arabian') OR (breeds.short_name ~* 'AR')" in sql


async def test_breed_short_name_sort_and_pagination_do_not_affect_total() -> None:
    session = FakeAsyncSession()
    repository = BreedRepository(session=session)  # type: ignore[arg-type]

    await repository.get_filtered(
        equestrian_id=UUID("11111111-1111-4111-8111-111111111111"),
        short_name="AR",
        sort=["short_name", "-short_name"],
        limit=5,
        offset=10,
    )

    list_sql = compile_sql(session.statements[0])
    count_sql = compile_sql(session.statements[1])
    assert "ORDER BY breeds.short_name ASC, breeds.short_name DESC" in list_sql
    assert "LIMIT 5 OFFSET 10" in list_sql
    assert "breeds.short_name ~* 'AR'" in count_sql
    assert "LIMIT" not in count_sql
