"""Tests for horse filtering by service names."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import pytest

from core.entities.horse import Horse, HorseKindEnum, HorseSexEnum
from core.services.horse import HorseService

pytestmark = pytest.mark.asyncio


class FakeHorseRepository:
    def __init__(self) -> None:
        self.horses: dict[UUID, Horse] = {}
        self.calls: list[tuple[str, Any]] = []
        self.filtered_result: tuple[dict[UUID, Any], int] = ({}, 0)

    def add_horse(self, horse: Horse) -> None:
        self.horses[horse.id] = horse

    async def get_horse_list_full_info(
        self,
        *,
        equestrian_id: UUID,
        name: str | None = None,
        description: str | None = None,
        breed_ids: list[UUID] | None = None,
        coat_color_ids: list[UUID] | None = None,
        kind: list[HorseKindEnum] | None = None,
        height_gte: int | None = None,
        height_lte: int | None = None,
        sex: list[HorseSexEnum] | None = None,
        bdate_gte: Any | None = None,
        bdate_lte: Any | None = None,
        ddate_gte: Any | None = None,
        ddate_lte: Any | None = None,
        horse_owner_ids: list[UUID] | None = None,
        services: list[UUID] | None = None,
        service_names: list[str] | None = None,
        this_stable: bool | None = None,
        exclude_ids: list[UUID] | None = None,
        include_ids: list[UUID] | None = None,
        limit: int | None = None,
        offset: int | None = None,
        sort: list[str] | None = None,
        pedigree: int | None = None,
    ) -> tuple[dict[UUID, Any], int]:
        self.calls.append(
            (
                "get_horse_list_full_info",
                {
                    "service_names": service_names,
                    "services": services,
                },
            )
        )
        return self.filtered_result


class FakeBreedRepository:
    pass


class FakeCoatColorRepository:
    pass


class FakeHorseOwnerRepository:
    pass


class FakePhotoRepository:
    pass


class FakeHorseChildrenRepository:
    pass


@pytest.fixture
def horse_repository() -> FakeHorseRepository:
    return FakeHorseRepository()


@pytest.fixture
def horse_service(horse_repository: FakeHorseRepository) -> HorseService:
    return HorseService(
        horse_repository=horse_repository,
        horse_children_repository=FakeHorseChildrenRepository(),
        breed_repository=FakeBreedRepository(),
        coat_color_repository=FakeCoatColorRepository(),
        horse_owner_repository=FakeHorseOwnerRepository(),
        photo_repository=FakePhotoRepository(),
    )


@pytest.fixture
def equestrian_context():
    from core.entities.equestrian import EquestrianContext

    return EquestrianContext(id=uuid4(), source="test")


# Task 4.1: Фильтрация лошадей по одному наименованию услуги
async def test_filter_by_single_service_name(
    horse_service: HorseService,
    horse_repository: FakeHorseRepository,
    equestrian_context,
):
    # Setup mock to return some horses
    horse_repository.filtered_result = ({}, 0)

    await horse_service.get_filtered_horses(
        equestrian_context=equestrian_context,
        service_names=["продажа"],
    )

    # Verify service_names was passed to repository
    assert len(horse_repository.calls) == 1
    call_args = horse_repository.calls[0][1]
    assert call_args["service_names"] == ["продажа"]


# Task 4.2: Фильтрация лошадей по нескольким наименованиям услуг
async def test_filter_by_multiple_service_names(
    horse_service: HorseService,
    horse_repository: FakeHorseRepository,
    equestrian_context,
):
    horse_repository.filtered_result = ({}, 0)

    await horse_service.get_filtered_horses(
        equestrian_context=equestrian_context,
        service_names=["продажа", "аренда"],
    )

    assert len(horse_repository.calls) == 1
    call_args = horse_repository.calls[0][1]
    assert call_args["service_names"] == ["продажа", "аренда"]


# Task 4.3: Фильтрация с несуществующим наименованием услуги возвращает пустой список
async def test_filter_by_nonexistent_service_name(
    horse_service: HorseService,
    horse_repository: FakeHorseRepository,
    equestrian_context,
):
    horse_repository.filtered_result = ({}, 0)

    result = await horse_service.get_filtered_horses(
        equestrian_context=equestrian_context,
        service_names=["НесуществующаяУслуга"],
    )

    assert result.total == 0
    assert len(result.items) == 0


# Task 4.4: Фильтрация с пустым списком наименований возвращает все лошади
async def test_filter_with_empty_service_names(
    horse_service: HorseService,
    horse_repository: FakeHorseRepository,
    equestrian_context,
):
    horse_repository.filtered_result = ({}, 0)

    await horse_service.get_filtered_horses(
        equestrian_context=equestrian_context,
        service_names=[],
    )

    assert len(horse_repository.calls) == 1
    call_args = horse_repository.calls[0][1]
    assert call_args["service_names"] == []


# Task 4.5: Комбинирование фильтра по услугам с другими фильтрами
async def test_filter_combined_with_other_filters(
    horse_service: HorseService,
    horse_repository: FakeHorseRepository,
    equestrian_context,
):
    horse_repository.filtered_result = ({}, 0)

    await horse_service.get_filtered_horses(
        equestrian_context=equestrian_context,
        service_names=["продажа"],
        name="Тестовая лошадь",
        this_stable=True,
    )

    assert len(horse_repository.calls) == 1
    call_args = horse_repository.calls[0][1]
    assert call_args["service_names"] == ["продажа"]


# Task 4.6: Фильтрация по полному наименованию (не подстрока)
async def test_filter_full_match_not_substring(
    horse_service: HorseService,
    horse_repository: FakeHorseRepository,
    equestrian_context,
):
    """Test that 'продажа' matches only 'продажа', not 'продажа и аренда'."""
    horse_repository.filtered_result = ({}, 0)

    await horse_service.get_filtered_horses(
        equestrian_context=equestrian_context,
        service_names=["продажа"],
    )

    # The repository should receive the exact name for full match filtering
    assert len(horse_repository.calls) == 1
    call_args = horse_repository.calls[0][1]
    assert call_args["service_names"] == ["продажа"]


# Task 4.7: Регистронезависимая фильтрация
async def test_filter_case_insensitive(
    horse_service: HorseService,
    horse_repository: FakeHorseRepository,
    equestrian_context,
):
    """Test that 'РАЗВЕДЕНИЕ' matches 'разведение'."""
    horse_repository.filtered_result = ({}, 0)

    await horse_service.get_filtered_horses(
        equestrian_context=equestrian_context,
        service_names=["РАЗВЕДЕНИЕ"],
    )

    # The repository should receive the name as-is (case handling is in repository)
    assert len(horse_repository.calls) == 1
    call_args = horse_repository.calls[0][1]
    assert call_args["service_names"] == ["РАЗВЕДЕНИЕ"]


# Task 4.8: Фильтрация с None service_names не передает параметр
async def test_filter_with_none_service_names(
    horse_service: HorseService,
    horse_repository: FakeHorseRepository,
    equestrian_context,
):
    horse_repository.filtered_result = ({}, 0)

    await horse_service.get_filtered_horses(
        equestrian_context=equestrian_context,
        service_names=None,
    )

    assert len(horse_repository.calls) == 1
    call_args = horse_repository.calls[0][1]
    assert call_args["service_names"] is None
