from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest
from sqlalchemy.dialects import postgresql

from core.entities.horse_service import HorseServiceRelations
from repositories.horse_service_relations_repository import (
    HorseServiceRelationsRepository,
)

HORSE_ID = UUID("11111111-1111-4111-8111-111111111111")
SERVICE_ID = UUID("22222222-2222-4222-8222-222222222222")
RELATION_ID = UUID("33333333-3333-4333-8333-333333333333")
CREATED_AT = datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc)


def _session_with_rows(rows: list[dict], *, total: int = 0) -> MagicMock:
    list_result = MagicMock()
    list_result.mappings.return_value.all.return_value = rows
    count_result = MagicMock()
    count_result.scalar_one.return_value = total
    session = MagicMock()
    session.execute = AsyncMock(side_effect=[list_result, count_result])
    return session


@pytest.mark.asyncio
async def test_create_omits_client_timestamp_and_returns_server_timestamp() -> None:
    client_created_at = datetime(2026, 8, 3, 11, 0, tzinfo=timezone.utc)
    server_created_at = datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc)
    entity = HorseServiceRelations(
        id=RELATION_ID,
        horse_id=HORSE_ID,
        service_id=SERVICE_ID,
        created_at=client_created_at,
    )
    result = MagicMock()
    result.mappings.return_value.one.return_value = {
        **entity.model_dump(),
        "created_at": server_created_at,
    }
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    session.flush = AsyncMock()
    repository = HorseServiceRelationsRepository(session=session)

    created = await repository.create(entity)

    statement = session.execute.await_args_list[0].args[0]
    compiled = statement.compile(dialect=postgresql.dialect())
    assert "created_at" not in compiled.params
    assert "RETURNING horse_service_relations" in str(compiled)
    assert created.created_at == server_created_at
    assert created.created_at != client_created_at


@pytest.mark.asyncio
async def test_ut06_list_orders_by_created_at_desc_then_id_desc() -> None:
    session = _session_with_rows([])
    repository = HorseServiceRelationsRepository(session=session)

    await repository.get_list_by_horse(horse_id=HORSE_ID)

    statement = session.execute.await_args_list[0].args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert (
        "ORDER BY horse_service_relations.created_at DESC, horse_service_relations.id DESC"
        in sql
    )


@pytest.mark.asyncio
async def test_ut07_tie_break_is_id_desc() -> None:
    session = _session_with_rows([])
    repository = HorseServiceRelationsRepository(session=session)

    await repository.get_list_by_horse(horse_id=HORSE_ID)

    statement = session.execute.await_args_list[0].args[0]
    order = [str(item) for item in statement._order_by_clauses]
    assert order == [
        "horse_service_relations.created_at DESC",
        "horse_service_relations.id DESC",
    ]


@pytest.mark.asyncio
async def test_ut08_empty_relation_list_is_valid() -> None:
    repository = HorseServiceRelationsRepository(session=_session_with_rows([]))

    assert await repository.get_list_by_horse(horse_id=HORSE_ID) == ([], 0)


@pytest.mark.asyncio
async def test_relation_list_applies_limit_offset_and_unpaginated_count() -> None:
    session = _session_with_rows([], total=7)
    repository = HorseServiceRelationsRepository(session=session)

    items, total = await repository.get_list_by_horse(
        horse_id=HORSE_ID, limit=2, offset=4
    )

    list_stmt = session.execute.await_args_list[0].args[0]
    count_stmt = session.execute.await_args_list[1].args[0]
    assert list_stmt._limit_clause.value == 2
    assert list_stmt._offset_clause.value == 4
    assert count_stmt._limit_clause is None
    assert count_stmt._offset_clause is None
    assert items == []
    assert total == 7


@pytest.mark.asyncio
async def test_available_services_returns_full_tenant_owned_service_fields() -> None:
    service_id = UUID("55555555-5555-4555-8555-555555555555")
    result = MagicMock()
    result.mappings.return_value.all.return_value = [
        {
            "id": service_id,
            "created_at": CREATED_AT,
            "updated_at": None,
            "equestrian_id": HORSE_ID,
            "name": "Подковка",
            "slug": "podkovka",
            "description": "Полное описание",
            "price": 2500,
            "price_formatter": "gt",
            "page_data": "<div></div>",
        }
    ]
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    repository = HorseServiceRelationsRepository(session=session)

    services = await repository.get_available_services(
        horse_id=HORSE_ID, equestrian_id=HORSE_ID
    )

    statement = session.execute.await_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "horse_service.equestrian_id" in sql
    assert "horse_service_relations.horse_id" in sql
    assert services[0].description == "Полное описание"
    assert services[0].price == 2500
    assert str(services[0].price_formatter) == "gt"


def test_ut09_newest_first_order_is_stable_across_pages() -> None:
    relations = [
        HorseServiceRelations(
            id=UUID(f"00000000-0000-4000-8000-{number:012d}"),
            horse_id=HORSE_ID,
            service_id=SERVICE_ID,
            created_at=CREATED_AT,
        )
        for number in range(5)
    ]

    ordered = sorted(
        relations, key=lambda relation: (relation.created_at, relation.id), reverse=True
    )

    assert [relation.id for relation in ordered[:2] + ordered[2:4]] == [
        relation.id for relation in ordered[:4]
    ]
