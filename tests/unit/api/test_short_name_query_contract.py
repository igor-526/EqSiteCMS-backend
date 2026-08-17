from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from api.breeds import get_breeds
from api.coat_color import get_coat_colors
from core.entities.equestrian import EquestrianContext
from depends.services import (
    get_breed_service,
    get_coat_color_service,
    get_read_equestrian_context,
)
from main import app


class CapturingListService:
    def __init__(self) -> None:
        self.kwargs: dict[str, object] = {}

    async def get_filtered(self, **kwargs: object) -> tuple[list[object], int]:
        self.kwargs = kwargs
        return [], 0


CONTEXT = EquestrianContext(
    id=UUID("11111111-1111-4111-8111-111111111111"), source="unit-test"
)


@pytest.mark.asyncio
@pytest.mark.parametrize("sort", [["short_name"], ["-short_name"]])
async def test_breeds_api_passes_short_name_filter_and_sort(sort: list[str]) -> None:
    service = CapturingListService()

    response = await get_breeds(
        breed_service=service,  # type: ignore[arg-type]
        equestrian_context=CONTEXT,
        name=None,
        short_name="AR",
        slug=None,
        description=None,
        page_data=None,
        kind=None,
        sort=sort,  # type: ignore[arg-type]
        limit=5,
        offset=10,
    )

    assert response.total == 0
    assert service.kwargs["short_name"] == "AR"
    assert service.kwargs["sort"] == sort


@pytest.mark.asyncio
@pytest.mark.parametrize("sort", [["short_name"], ["-short_name"]])
async def test_coat_colors_api_passes_short_name_filter_and_sort(
    sort: list[str],
) -> None:
    service = CapturingListService()

    response = await get_coat_colors(
        coat_color_service=service,  # type: ignore[arg-type]
        equestrian_context=CONTEXT,
        name=None,
        short_name="B",
        slug=None,
        description=None,
        page_data=None,
        sort=sort,  # type: ignore[arg-type]
        limit=5,
        offset=10,
    )

    assert response.total == 0
    assert service.kwargs["short_name"] == "B"
    assert service.kwargs["sort"] == sort


@pytest.mark.parametrize(
    ("path", "dependency"),
    [
        ("/api/horses/breeds", get_breed_service),
        ("/api/horses/coat_colors", get_coat_color_service),
    ],
)
def test_list_api_rejects_unknown_sort(
    path: str, dependency: Callable[..., Any]
) -> None:
    app.dependency_overrides[get_read_equestrian_context] = lambda: CONTEXT
    app.dependency_overrides[dependency] = CapturingListService

    try:
        response = TestClient(app).get(path, params={"sort": "unknown"})
    finally:
        app.dependency_overrides.pop(get_read_equestrian_context, None)
        app.dependency_overrides.pop(dependency, None)

    assert response.status_code == 422
