from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from core.entities.equestrian import EquestrianContext
from core.services.horse import HorseService

TENANT_ID = UUID("11111111-1111-4111-8111-111111111111")
SERVICE_A = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
SERVICE_B = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")


def _service(repository: AsyncMock) -> HorseService:
    return HorseService(
        horse_repository=repository,
        horse_children_repository=AsyncMock(),
        breed_repository=AsyncMock(),
        coat_color_repository=AsyncMock(),
        horse_owner_repository=AsyncMock(),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("services", [None, [], [SERVICE_A], [SERVICE_A, SERVICE_B]])
async def test_service_passes_services_and_tenant_to_repository(
    services: list[UUID] | None,
) -> None:
    repository = AsyncMock()
    repository.get_horse_list_full_info.return_value = ({}, 0)
    service = _service(repository)

    result = await service.get_filtered_horses(
        equestrian_context=EquestrianContext(id=TENANT_ID, source="unit-test"),
        services=services,
        user=None,
    )

    assert result.items == []
    assert result.total == 0
    call = repository.get_horse_list_full_info.await_args.kwargs
    assert call["equestrian_id"] == TENANT_ID
    assert call["services"] == services


@pytest.mark.asyncio
async def test_service_preserves_filter_sort_and_pagination_together() -> None:
    repository = AsyncMock()
    repository.get_horse_list_full_info.return_value = ({}, 0)
    service = _service(repository)

    await service.get_filtered_horses(
        equestrian_context=EquestrianContext(id=TENANT_ID, source="unit-test"),
        services=[SERVICE_A],
        name="Star",
        sort=["-name"],
        limit=9,
        offset=18,
        user=None,
    )

    call = repository.get_horse_list_full_info.await_args.kwargs
    assert call["services"] == [SERVICE_A]
    assert call["name"] == "Star"
    assert call["sort"] == ["-name"]
    assert call["limit"] == 9
    assert call["offset"] == 18
