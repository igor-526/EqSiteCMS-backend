from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from core.entities.price import PriceFormatter
from repositories.horse_repository import HorseRepository


@pytest.fixture
def repo() -> HorseRepository:
    mock_session = MagicMock()
    mock_url_builder = MagicMock()
    mock_url_builder.build = lambda path: f"https://cdn.example.com/{path}"
    return HorseRepository(session=mock_session, photo_url_builder=mock_url_builder)


def _make_horse_data() -> dict[str, Any]:
    return {
        "id": uuid4(),
        "slug": "test-horse",
        "name": "Тестовая лошадь",
        "code": None,
        "description": None,
        "breed_id": None,
        "coat_color_id": None,
        "height": None,
        "sex": "male",
        "bdate": None,
        "ddate": None,
        "bdate_mode": "hide",
        "ddate_mode": "hide",
        "horse_owner_id": None,
        "this_stable": False,
        "equestrian_id": uuid4(),
        "created_at": datetime.now(timezone.utc),
        "updated_at": None,
    }


def _make_service_data(
    *,
    description: str | None = "Default desc",
    price: int = 1000,
    price_formatter: str = "equal",
    description_override: str | None = None,
    price_override: int | None = None,
    price_formatter_override: str | None = None,
) -> dict[str, Any]:
    return {
        "id": uuid4(),
        "name": "Подковка",
        "slug": "podkovka",
        "description": description,
        "price": price,
        "price_formatter": price_formatter,
        "page_data": "<div></div>",
        "equestrian_id": uuid4(),
        "created_at": datetime.now(timezone.utc),
        "updated_at": None,
        "description_override": description_override,
        "price_override": price_override,
        "price_formatter_override": price_formatter_override,
    }


def test_build_horse_dto_uses_default_when_no_overrides(repo: HorseRepository) -> None:
    service_data = _make_service_data()
    result = repo._build_horse_dto(
        _make_horse_data(), None, None, None, [], [service_data]
    )

    assert len(result.services) == 1
    svc = result.services[0]
    assert svc.description == "Default desc"
    assert svc.price == 1000
    assert svc.price_formatter == "equal"


def test_build_horse_dto_applies_description_override(repo: HorseRepository) -> None:
    service_data = _make_service_data(description_override="Override desc")
    result = repo._build_horse_dto(
        _make_horse_data(), None, None, None, [], [service_data]
    )

    svc = result.services[0]
    assert svc.description == "Override desc"


def test_build_horse_dto_applies_price_override(repo: HorseRepository) -> None:
    service_data = _make_service_data(price_override=5000)
    result = repo._build_horse_dto(
        _make_horse_data(), None, None, None, [], [service_data]
    )

    svc = result.services[0]
    assert svc.price == 5000


def test_build_horse_dto_applies_price_formatter_override(repo: HorseRepository) -> None:
    service_data = _make_service_data(price_formatter_override="gt")
    result = repo._build_horse_dto(
        _make_horse_data(), None, None, None, [], [service_data]
    )

    svc = result.services[0]
    assert svc.price_formatter == "gt"


def test_build_horse_dto_applies_all_overrides(repo: HorseRepository) -> None:
    service_data = _make_service_data(
        description_override="Custom",
        price_override=9999,
        price_formatter_override="discuss",
    )
    result = repo._build_horse_dto(
        _make_horse_data(), None, None, None, [], [service_data]
    )

    svc = result.services[0]
    assert svc.description == "Custom"
    assert svc.price == 9999
    assert svc.price_formatter == "discuss"


def test_build_horse_dto_no_services(repo: HorseRepository) -> None:
    result = repo._build_horse_dto(
        _make_horse_data(), None, None, None, [], []
    )
    assert result.services == []


def test_build_horse_dto_null_overrides_use_defaults(repo: HorseRepository) -> None:
    service_data = _make_service_data(
        description_override=None,
        price_override=None,
        price_formatter_override=None,
    )
    result = repo._build_horse_dto(
        _make_horse_data(), None, None, None, [], [service_data]
    )

    svc = result.services[0]
    assert svc.description == "Default desc"
    assert svc.price == 1000
    assert svc.price_formatter == "equal"
