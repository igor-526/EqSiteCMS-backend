from typing import Any, cast
from uuid import UUID

import pytest
from test_breed_repository import FakeAsyncSession, compile_sql

from repositories.breed_group_repository import BreedGroupRepository

pytestmark = pytest.mark.asyncio
TENANT = UUID("11111111-1111-4111-8111-111111111111")


async def test_text_filters_use_escaped_case_insensitive_regex() -> None:
    session = FakeAsyncSession()
    await BreedGroupRepository(session=cast(Any, session)).get_filtered(
        equestrian_id=TENANT, name="A.B", slug="foo"
    )
    sql = compile_sql(session.statements[0])
    assert "breed_groups.name ~* 'A\\\\.B'" in sql
    assert "breed_groups.slug ~* 'foo'" in sql


async def test_default_order_is_stable() -> None:
    session = FakeAsyncSession()
    await BreedGroupRepository(session=session).get_filtered(equestrian_id=TENANT)  # type: ignore[arg-type]
    assert "ORDER BY breed_groups.created_at DESC, breed_groups.id DESC" in compile_sql(
        session.statements[0]
    )


@pytest.mark.parametrize(
    "sort, expected",
    [
        (["name"], "name ASC"),
        (["-slug"], "slug DESC"),
        (["created_at"], "created_at ASC"),
        (["-updated_at"], "updated_at DESC"),
    ],
)
async def test_supported_sort(sort: list[str], expected: str) -> None:
    session = FakeAsyncSession()
    await BreedGroupRepository(session=cast(Any, session)).get_filtered(
        equestrian_id=TENANT, sort=cast(Any, sort)
    )
    assert expected in compile_sql(session.statements[0])


async def test_pagination_does_not_change_total() -> None:
    session = FakeAsyncSession()
    await BreedGroupRepository(session=cast(Any, session)).get_filtered(
        equestrian_id=TENANT, limit=5, offset=10
    )
    assert "LIMIT 5 OFFSET 10" in compile_sql(session.statements[0])
    assert "LIMIT" not in compile_sql(session.statements[1])
