from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from core.entities.base import PaginatedEntities
from core.schemas.coat_color import (
    CoatColorCreateDto,
    CoatColorOutDto,
    CoatColorOutWithPageDataDto,
    CoatColorUpdateDto,
)
from core.services.coat_color import CoatColorService
from depends.services import get_coat_color_service

router = APIRouter()


@router.get(
    "/horses/coat_colors",
    response_model=PaginatedEntities[CoatColorOutDto],
    tags=["Horse Coat Color"],
    description="Получить список мастей с фильтрацией и сортировкой",
)
async def get_coat_colors(
    coat_color_service: Annotated[CoatColorService, Depends(get_coat_color_service)],
    name: str | None = Query(None, description="Фильтр по названию (вхождение)"),
    slug: str | None = Query(None, description="Фильтр по slug (вхождение)"),
    description: str | None = Query(None, description="Фильтр по описанию (вхождение)"),
    page_data: str | None = Query(None, description="Фильтр по page_data (вхождение)"),
    sort: (
        list[Literal["name", "description", "slug", "-name", "-description", "-slug"]]
        | None
    ) = Query(None, description="Сортировка"),
    limit: int | None = Query(None, description="Лимит"),
    offset: int | None = Query(None, description="Смещение"),
) -> PaginatedEntities[CoatColorOutDto]:
    entities, total = await coat_color_service.get_filtered(
        name=name,
        slug=slug,
        description=description,
        page_data=page_data,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    return PaginatedEntities(
        items=[CoatColorOutDto.model_validate(entity) for entity in entities],
        total=total,
    )


@router.get(
    "/horses/coat_colors/{slug_or_id}",
    response_model=CoatColorOutDto | CoatColorOutWithPageDataDto,
    tags=["Horse Coat Color"],
    description="Получить масть по slug или UUID",
)
async def get_coat_color(
    coat_color_service: Annotated[CoatColorService, Depends(get_coat_color_service)],
    slug_or_id: str,
    page_data: bool = Query(False, description="Включить page_data в ответ"),
) -> CoatColorOutDto | CoatColorOutWithPageDataDto:
    coat_color = await coat_color_service.get_by_slug_or_id(slug_or_id)
    if coat_color is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Масть не найдена")

    if page_data:
        return CoatColorOutWithPageDataDto.model_validate(coat_color)
    return CoatColorOutDto.model_validate(coat_color)


@router.post(
    "/horses/coat_colors",
    response_model=CoatColorOutDto,
    tags=["Horse Coat Color"],
    description="Создать новую масть",
)
async def create_coat_color(
    data: CoatColorCreateDto,
    coat_color_service: Annotated[CoatColorService, Depends(get_coat_color_service)],
) -> CoatColorOutDto:
    coat_color = await coat_color_service.create(data)
    return CoatColorOutDto.model_validate(coat_color)


@router.patch(
    "/horses/coat_colors/{slug_or_id}",
    response_model=CoatColorOutDto,
    tags=["Horse Coat Color"],
    description="Обновить масть",
)
async def update_coat_color(
    slug_or_id: str,
    data: CoatColorUpdateDto,
    coat_color_service: Annotated[CoatColorService, Depends(get_coat_color_service)],
) -> CoatColorOutDto:
    coat_color = await coat_color_service.update(slug_or_id, data)
    return CoatColorOutDto.model_validate(coat_color)


@router.delete(
    "/horses/coat_colors/{slug_or_id}",
    status_code=204,
    tags=["Horse Coat Color"],
    description="Удалить масть",
)
async def delete_coat_color(
    slug_or_id: str,
    coat_color_service: Annotated[CoatColorService, Depends(get_coat_color_service)],
) -> None:
    await coat_color_service.delete(slug_or_id)
