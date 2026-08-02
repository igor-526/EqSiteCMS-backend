from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy.dialects import postgresql

from repositories.coat_color_repository import CoatColorRepository

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
        self.statements: list[object] = []

    async def execute(self, statement: object) -> FakeExecuteResult:
        self.statements.append(statement)
        return FakeExecuteResult()


def compile_sql(statement: object) -> str:
    return str(
        statement.compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )


@pytest.mark.parametrize(
    ("term", "expected"),
    [
        ("BAY", "coat_color.short_name ~* 'BAY'"),
        ("b.y", "coat_color.short_name ~* 'b\\\\.y'"),
    ],
)
async def test_short_name_filter_uses_escaped_case_insensitive_regex(
    term: str, expected: str
) -> None:
    session = FakeAsyncSession()
    repository = CoatColorRepository(session=session)  # type: ignore[arg-type]

    await repository.get_filtered(
        equestrian_id=UUID("22222222-2222-4222-8222-222222222222"), short_name=term
    )

    assert expected in compile_sql(session.statements[0])


async def test_empty_short_name_does_not_add_filter() -> None:
    session = FakeAsyncSession()
    repository = CoatColorRepository(session=session)  # type: ignore[arg-type]

    await repository.get_filtered(
        equestrian_id=UUID("22222222-2222-4222-8222-222222222222"), short_name=""
    )

    assert "short_name ~*" not in compile_sql(session.statements[0])


async def test_short_name_filter_keeps_tenant_predicate() -> None:
    session = FakeAsyncSession()
    repository = CoatColorRepository(session=session)  # type: ignore[arg-type]

    await repository.get_filtered(
        equestrian_id=UUID("22222222-2222-4222-8222-222222222222"), short_name="B"
    )

    sql = compile_sql(session.statements[0])
    assert "coat_color.equestrian_id = '22222222-2222-4222-8222-222222222222'" in sql
    assert "coat_color.short_name ~* 'B'" in sql


async def test_short_name_sort_filter_pagination_and_total() -> None:
    session = FakeAsyncSession()
    repository = CoatColorRepository(session=session)  # type: ignore[arg-type]

    await repository.get_filtered(
        equestrian_id=UUID("22222222-2222-4222-8222-222222222222"),
        short_name="B",
        sort=["short_name", "-short_name"],
        limit=3,
        offset=6,
    )

    list_sql = compile_sql(session.statements[0])
    count_sql = compile_sql(session.statements[1])
    assert "ORDER BY coat_color.short_name ASC, coat_color.short_name DESC" in list_sql
    assert "LIMIT 3 OFFSET 6" in list_sql
    assert "coat_color.short_name ~* 'B'" in count_sql
    assert "LIMIT" not in count_sql
