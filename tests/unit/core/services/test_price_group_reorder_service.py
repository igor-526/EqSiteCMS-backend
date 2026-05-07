"""Unit-тесты для PriceGroupService.reorder_prices_in_group."""

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from core.entities.equestrian import EquestrianContext
from core.entities.prices import PriceGroupsRelation
from core.exceptions.base import ClientError
from core.schemas.prices import PriceGroupReorderDto, PriceGroupReorderItemDto
from core.services.prices import PriceGroupService


def make_equestrian_context() -> EquestrianContext:
    return EquestrianContext(id=uuid4(), source="authenticated")


def make_user(scope_names: list[str]):
    """Создать mock UserOutDto с заданными scope_names."""
    user = MagicMock()
    user.scopes = [MagicMock(scope_name=name) for name in scope_names]
    return user


def make_relation(
    price_id: UUID, group_id: UUID, display_order: int | None
) -> PriceGroupsRelation:
    return PriceGroupsRelation(
        id=uuid4(), price_id=price_id, group_id=group_id, display_order=display_order
    )


def make_service(group=None, relations=None):
    """Создать PriceGroupService с mock-репозиториями."""
    price_group_repo = AsyncMock()
    price_repo = AsyncMock()

    group_entity = group or MagicMock()
    group_entity.id = uuid4()
    price_group_repo.get_by_id.return_value = group_entity
    price_repo.get_group_relations_ordered.return_value = relations or []
    price_repo.set_display_orders.return_value = None

    service = PriceGroupService(
        price_group_repository=price_group_repo,
        price_repository=price_repo,
    )
    return service, price_group_repo, price_repo


# ===== Role checks =====


@pytest.mark.asyncio
async def test_reorder_role_superuser_allowed():
    ctx = make_equestrian_context()
    group_id = uuid4()
    pid = uuid4()
    rel = make_relation(pid, group_id, 1)
    service, _, price_repo = make_service(relations=[rel])
    user = make_user(["SUPERUSER"])
    data = PriceGroupReorderDto(changes=[PriceGroupReorderItemDto(id=pid, order=1)])
    await service.reorder_prices_in_group(
        group_id, data, equestrian_context=ctx, user=user
    )
    price_repo.set_display_orders.assert_called_once()


@pytest.mark.asyncio
async def test_reorder_role_admin_allowed():
    ctx = make_equestrian_context()
    group_id = uuid4()
    pid = uuid4()
    rel = make_relation(pid, group_id, 1)
    service, _, price_repo = make_service(relations=[rel])
    user = make_user(["ADMIN"])
    data = PriceGroupReorderDto(changes=[PriceGroupReorderItemDto(id=pid, order=1)])
    await service.reorder_prices_in_group(
        group_id, data, equestrian_context=ctx, user=user
    )
    price_repo.set_display_orders.assert_called_once()


@pytest.mark.asyncio
async def test_reorder_role_developer_allowed():
    ctx = make_equestrian_context()
    group_id = uuid4()
    pid = uuid4()
    rel = make_relation(pid, group_id, 1)
    service, _, price_repo = make_service(relations=[rel])
    user = make_user(["DEVELOPER"])
    data = PriceGroupReorderDto(changes=[PriceGroupReorderItemDto(id=pid, order=1)])
    await service.reorder_prices_in_group(
        group_id, data, equestrian_context=ctx, user=user
    )
    price_repo.set_display_orders.assert_called_once()


@pytest.mark.asyncio
async def test_reorder_role_no_role_raises():
    ctx = make_equestrian_context()
    group_id = uuid4()
    service, _, _ = make_service(relations=[])
    user = make_user(["USER"])
    data = PriceGroupReorderDto(changes=[PriceGroupReorderItemDto(id=uuid4(), order=1)])
    with pytest.raises(ClientError):
        await service.reorder_prices_in_group(
            group_id, data, equestrian_context=ctx, user=user
        )


@pytest.mark.asyncio
async def test_reorder_role_empty_scopes_raises():
    ctx = make_equestrian_context()
    group_id = uuid4()
    service, _, _ = make_service(relations=[])
    user = make_user([])
    data = PriceGroupReorderDto(changes=[PriceGroupReorderItemDto(id=uuid4(), order=1)])
    with pytest.raises(ClientError):
        await service.reorder_prices_in_group(
            group_id, data, equestrian_context=ctx, user=user
        )


# ===== Group not found =====


@pytest.mark.asyncio
async def test_reorder_group_not_found():
    ctx = make_equestrian_context()
    group_id = uuid4()
    service, group_repo, _ = make_service()
    group_repo.get_by_id.return_value = None
    user = make_user(["ADMIN"])
    data = PriceGroupReorderDto(changes=[PriceGroupReorderItemDto(id=uuid4(), order=1)])
    with pytest.raises(ClientError, match="Группа не найдена"):
        await service.reorder_prices_in_group(
            group_id, data, equestrian_context=ctx, user=user
        )


# ===== Unknown price UUID =====


@pytest.mark.asyncio
async def test_reorder_unknown_price_id():
    ctx = make_equestrian_context()
    group_id = uuid4()
    pid = uuid4()
    rel = make_relation(pid, group_id, 1)
    service, _, _ = make_service(relations=[rel])
    user = make_user(["ADMIN"])
    unknown_id = uuid4()
    data = PriceGroupReorderDto(
        changes=[PriceGroupReorderItemDto(id=unknown_id, order=1)]
    )
    with pytest.raises(ClientError):
        await service.reorder_prices_in_group(
            group_id, data, equestrian_context=ctx, user=user
        )


# ===== Empty group =====


@pytest.mark.asyncio
async def test_reorder_empty_group():
    ctx = make_equestrian_context()
    group_id = uuid4()
    service, _, _ = make_service(relations=[])
    user = make_user(["ADMIN"])
    data = PriceGroupReorderDto(changes=[PriceGroupReorderItemDto(id=uuid4(), order=1)])
    with pytest.raises(ClientError):
        await service.reorder_prices_in_group(
            group_id, data, equestrian_context=ctx, user=user
        )


# ===== Reorder algorithm =====


@pytest.mark.asyncio
async def test_reorder_move_forward():
    """Элемент 1→3: промежуточные 2,3 сдвигаются на -1 → 1,2."""
    ctx = make_equestrian_context()
    group_id = uuid4()
    p1, p2, p3 = uuid4(), uuid4(), uuid4()
    relations = [
        make_relation(p1, group_id, 1),
        make_relation(p2, group_id, 2),
        make_relation(p3, group_id, 3),
    ]
    service, _, price_repo = make_service(relations=relations)
    user = make_user(["ADMIN"])
    data = PriceGroupReorderDto(changes=[PriceGroupReorderItemDto(id=p1, order=3)])
    await service.reorder_prices_in_group(
        group_id, data, equestrian_context=ctx, user=user
    )
    order_map = price_repo.set_display_orders.call_args[0][1]
    assert order_map[p1] == 3
    assert order_map[p2] == 1
    assert order_map[p3] == 2


@pytest.mark.asyncio
async def test_reorder_move_backward():
    """Элемент 3→1: промежуточные 1,2 сдвигаются на +1 → 2,3."""
    ctx = make_equestrian_context()
    group_id = uuid4()
    p1, p2, p3 = uuid4(), uuid4(), uuid4()
    relations = [
        make_relation(p1, group_id, 1),
        make_relation(p2, group_id, 2),
        make_relation(p3, group_id, 3),
    ]
    service, _, price_repo = make_service(relations=relations)
    user = make_user(["ADMIN"])
    data = PriceGroupReorderDto(changes=[PriceGroupReorderItemDto(id=p3, order=1)])
    await service.reorder_prices_in_group(
        group_id, data, equestrian_context=ctx, user=user
    )
    order_map = price_repo.set_display_orders.call_args[0][1]
    assert order_map[p3] == 1
    assert order_map[p1] == 2
    assert order_map[p2] == 3


@pytest.mark.asyncio
async def test_reorder_no_change_same_position():
    """Элемент уже на нужной позиции — set_display_orders вызывается с тем же order_map."""
    ctx = make_equestrian_context()
    group_id = uuid4()
    p1, p2 = uuid4(), uuid4()
    relations = [make_relation(p1, group_id, 1), make_relation(p2, group_id, 2)]
    service, _, price_repo = make_service(relations=relations)
    user = make_user(["ADMIN"])
    data = PriceGroupReorderDto(changes=[PriceGroupReorderItemDto(id=p1, order=1)])
    await service.reorder_prices_in_group(
        group_id, data, equestrian_context=ctx, user=user
    )
    order_map = price_repo.set_display_orders.call_args[0][1]
    assert order_map[p1] == 1
    assert order_map[p2] == 2


@pytest.mark.asyncio
async def test_reorder_to_first():
    ctx = make_equestrian_context()
    group_id = uuid4()
    p1, p2, p3 = uuid4(), uuid4(), uuid4()
    relations = [
        make_relation(p1, group_id, 1),
        make_relation(p2, group_id, 2),
        make_relation(p3, group_id, 3),
    ]
    service, _, price_repo = make_service(relations=relations)
    user = make_user(["ADMIN"])
    data = PriceGroupReorderDto(changes=[PriceGroupReorderItemDto(id=p3, order=1)])
    await service.reorder_prices_in_group(
        group_id, data, equestrian_context=ctx, user=user
    )
    order_map = price_repo.set_display_orders.call_args[0][1]
    assert order_map[p3] == 1


@pytest.mark.asyncio
async def test_reorder_to_last():
    ctx = make_equestrian_context()
    group_id = uuid4()
    p1, p2, p3 = uuid4(), uuid4(), uuid4()
    relations = [
        make_relation(p1, group_id, 1),
        make_relation(p2, group_id, 2),
        make_relation(p3, group_id, 3),
    ]
    service, _, price_repo = make_service(relations=relations)
    user = make_user(["ADMIN"])
    data = PriceGroupReorderDto(changes=[PriceGroupReorderItemDto(id=p1, order=3)])
    await service.reorder_prices_in_group(
        group_id, data, equestrian_context=ctx, user=user
    )
    order_map = price_repo.set_display_orders.call_args[0][1]
    assert order_map[p1] == 3


@pytest.mark.asyncio
async def test_reorder_order_clips_above_n():
    """order > N → клипируется до N."""
    ctx = make_equestrian_context()
    group_id = uuid4()
    p1, p2 = uuid4(), uuid4()
    relations = [make_relation(p1, group_id, 1), make_relation(p2, group_id, 2)]
    service, _, price_repo = make_service(relations=relations)
    user = make_user(["ADMIN"])
    data = PriceGroupReorderDto(changes=[PriceGroupReorderItemDto(id=p1, order=99)])
    await service.reorder_prices_in_group(
        group_id, data, equestrian_context=ctx, user=user
    )
    order_map = price_repo.set_display_orders.call_args[0][1]
    assert order_map[p1] == 2  # N = 2


@pytest.mark.asyncio
async def test_reorder_order_clips_below_1():
    """order < 1 → клипируется до 1 (Pydantic ge=1 уже блокирует на уровне DTO, но сервис тоже клипирует)."""
    ctx = make_equestrian_context()
    group_id = uuid4()
    p1, p2 = uuid4(), uuid4()
    relations = [make_relation(p1, group_id, 1), make_relation(p2, group_id, 2)]
    service, _, price_repo = make_service(relations=relations)
    user = make_user(["ADMIN"])
    # Simulate: напрямую передаём order=1 (минимум по ge=1)
    data = PriceGroupReorderDto(changes=[PriceGroupReorderItemDto(id=p2, order=1)])
    await service.reorder_prices_in_group(
        group_id, data, equestrian_context=ctx, user=user
    )
    order_map = price_repo.set_display_orders.call_args[0][1]
    assert order_map[p2] == 1


@pytest.mark.asyncio
async def test_reorder_multiple_changes_sequential():
    """Два последовательных изменения применяются в порядке их следования."""
    ctx = make_equestrian_context()
    group_id = uuid4()
    p1, p2, p3 = uuid4(), uuid4(), uuid4()
    relations = [
        make_relation(p1, group_id, 1),
        make_relation(p2, group_id, 2),
        make_relation(p3, group_id, 3),
    ]
    service, _, price_repo = make_service(relations=relations)
    user = make_user(["ADMIN"])
    # Сначала p1→3, потом p2→1
    data = PriceGroupReorderDto(
        changes=[
            PriceGroupReorderItemDto(id=p1, order=3),
            PriceGroupReorderItemDto(id=p2, order=1),
        ]
    )
    await service.reorder_prices_in_group(
        group_id, data, equestrian_context=ctx, user=user
    )
    order_map = price_repo.set_display_orders.call_args[0][1]
    # Все позиции в 1..3, без дублей
    positions = sorted(order_map.values())
    assert positions == [1, 2, 3]


@pytest.mark.asyncio
async def test_reorder_preserves_range_1_to_n():
    """После любого reorder все display_order в диапазоне 1..N."""
    ctx = make_equestrian_context()
    group_id = uuid4()
    pids = [uuid4() for _ in range(5)]
    relations = [make_relation(pid, group_id, i + 1) for i, pid in enumerate(pids)]
    service, _, price_repo = make_service(relations=relations)
    user = make_user(["ADMIN"])
    data = PriceGroupReorderDto(changes=[PriceGroupReorderItemDto(id=pids[2], order=1)])
    await service.reorder_prices_in_group(
        group_id, data, equestrian_context=ctx, user=user
    )
    order_map = price_repo.set_display_orders.call_args[0][1]
    assert sorted(order_map.values()) == list(range(1, 6))


@pytest.mark.asyncio
async def test_reorder_no_duplicate_positions():
    """Нет дублирующихся позиций после reorder."""
    ctx = make_equestrian_context()
    group_id = uuid4()
    p1, p2, p3, p4 = uuid4(), uuid4(), uuid4(), uuid4()
    relations = [
        make_relation(p1, group_id, 1),
        make_relation(p2, group_id, 2),
        make_relation(p3, group_id, 3),
        make_relation(p4, group_id, 4),
    ]
    service, _, price_repo = make_service(relations=relations)
    user = make_user(["ADMIN"])
    data = PriceGroupReorderDto(changes=[PriceGroupReorderItemDto(id=p4, order=2)])
    await service.reorder_prices_in_group(
        group_id, data, equestrian_context=ctx, user=user
    )
    order_map = price_repo.set_display_orders.call_args[0][1]
    assert len(set(order_map.values())) == 4


@pytest.mark.asyncio
async def test_reorder_swap_adjacent():
    """Обмен двух соседних элементов."""
    ctx = make_equestrian_context()
    group_id = uuid4()
    p1, p2 = uuid4(), uuid4()
    relations = [make_relation(p1, group_id, 1), make_relation(p2, group_id, 2)]
    service, _, price_repo = make_service(relations=relations)
    user = make_user(["ADMIN"])
    data = PriceGroupReorderDto(changes=[PriceGroupReorderItemDto(id=p1, order=2)])
    await service.reorder_prices_in_group(
        group_id, data, equestrian_context=ctx, user=user
    )
    order_map = price_repo.set_display_orders.call_args[0][1]
    assert order_map[p1] == 2
    assert order_map[p2] == 1


@pytest.mark.asyncio
async def test_reorder_middle_to_start():
    """Средний элемент перемещается в начало."""
    ctx = make_equestrian_context()
    group_id = uuid4()
    p1, p2, p3 = uuid4(), uuid4(), uuid4()
    relations = [
        make_relation(p1, group_id, 1),
        make_relation(p2, group_id, 2),
        make_relation(p3, group_id, 3),
    ]
    service, _, price_repo = make_service(relations=relations)
    user = make_user(["ADMIN"])
    data = PriceGroupReorderDto(changes=[PriceGroupReorderItemDto(id=p2, order=1)])
    await service.reorder_prices_in_group(
        group_id, data, equestrian_context=ctx, user=user
    )
    order_map = price_repo.set_display_orders.call_args[0][1]
    assert order_map[p2] == 1
    assert order_map[p1] == 2


@pytest.mark.asyncio
async def test_reorder_set_display_orders_called_with_correct_group_id():
    """set_display_orders вызывается с правильным group_id."""
    ctx = make_equestrian_context()
    group_id = uuid4()
    p1 = uuid4()
    relations = [make_relation(p1, group_id, 1)]
    service, _, price_repo = make_service(relations=relations)
    user = make_user(["ADMIN"])
    data = PriceGroupReorderDto(changes=[PriceGroupReorderItemDto(id=p1, order=1)])
    await service.reorder_prices_in_group(
        group_id, data, equestrian_context=ctx, user=user
    )
    call_args = price_repo.set_display_orders.call_args
    assert call_args[0][0] == group_id


@pytest.mark.asyncio
async def test_reorder_null_display_order_initialized_before_reorder():
    """Если display_order у legacy записи равен NULL — инициализируется по позиции."""
    ctx = make_equestrian_context()
    group_id = uuid4()
    p1, p2 = uuid4(), uuid4()
    # display_order=None (legacy)
    relations = [make_relation(p1, group_id, None), make_relation(p2, group_id, None)]
    service, _, price_repo = make_service(relations=relations)
    user = make_user(["ADMIN"])
    data = PriceGroupReorderDto(changes=[PriceGroupReorderItemDto(id=p1, order=2)])
    await service.reorder_prices_in_group(
        group_id, data, equestrian_context=ctx, user=user
    )
    order_map = price_repo.set_display_orders.call_args[0][1]
    # Результирующие позиции должны быть в 1..N
    assert sorted(order_map.values()) == [1, 2]


@pytest.mark.asyncio
async def test_reorder_large_list_boundary():
    """Список из 10 элементов, крайние значения (1 и 10)."""
    ctx = make_equestrian_context()
    group_id = uuid4()
    pids = [uuid4() for _ in range(10)]
    relations = [make_relation(pid, group_id, i + 1) for i, pid in enumerate(pids)]
    service, _, price_repo = make_service(relations=relations)
    user = make_user(["ADMIN"])
    # Перемещаем последний на первое место
    data = PriceGroupReorderDto(changes=[PriceGroupReorderItemDto(id=pids[9], order=1)])
    await service.reorder_prices_in_group(
        group_id, data, equestrian_context=ctx, user=user
    )
    order_map = price_repo.set_display_orders.call_args[0][1]
    assert order_map[pids[9]] == 1
    assert sorted(order_map.values()) == list(range(1, 11))


@pytest.mark.asyncio
async def test_reorder_idempotent_same_order():
    """Reorder с тем же порядком — set_display_orders вызывается с тем же order_map."""
    ctx = make_equestrian_context()
    group_id = uuid4()
    p1, p2 = uuid4(), uuid4()
    relations = [make_relation(p1, group_id, 1), make_relation(p2, group_id, 2)]
    service, _, price_repo = make_service(relations=relations)
    user = make_user(["ADMIN"])
    data = PriceGroupReorderDto(
        changes=[
            PriceGroupReorderItemDto(id=p1, order=1),
            PriceGroupReorderItemDto(id=p2, order=2),
        ]
    )
    await service.reorder_prices_in_group(
        group_id, data, equestrian_context=ctx, user=user
    )
    order_map = price_repo.set_display_orders.call_args[0][1]
    assert order_map[p1] == 1
    assert order_map[p2] == 2


@pytest.mark.asyncio
async def test_reorder_single_element_group():
    """Группа из одного элемента — любой order клипируется до 1."""
    ctx = make_equestrian_context()
    group_id = uuid4()
    p1 = uuid4()
    relations = [make_relation(p1, group_id, 1)]
    service, _, price_repo = make_service(relations=relations)
    user = make_user(["ADMIN"])
    data = PriceGroupReorderDto(changes=[PriceGroupReorderItemDto(id=p1, order=5)])
    await service.reorder_prices_in_group(
        group_id, data, equestrian_context=ctx, user=user
    )
    order_map = price_repo.set_display_orders.call_args[0][1]
    assert order_map[p1] == 1
