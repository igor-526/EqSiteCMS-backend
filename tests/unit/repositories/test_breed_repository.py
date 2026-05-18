from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy.dialects import postgresql

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
        self.statements: list[object] = []

    async def execute(self, statement: object) -> FakeExecuteResult:
        self.statements.append(statement)
        return FakeExecuteResult()


def compile_sql(statement: object) -> str:
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
