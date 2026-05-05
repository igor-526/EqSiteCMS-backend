from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from core.entities.base import PaginatedEntities
from core.schemas.breeds import (
    BreedCreateDto,
    BreedOutDto,
    BreedOutWithPageDataDto,
    BreedUpdateDto,
)
from core.services.breeds import BreedService
from depends.services import get_breed_service

router = APIRouter()


@router.get(
    "/horses/breeds",
    response_model=PaginatedEntities[BreedOutDto],
    tags=["Horse Breeds"],
    description="Получить список пород с фильтрацией и сортировкой",
)
async def get_breeds(
    breed_service: Annotated[BreedService, Depends(get_breed_service)],
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
) -> PaginatedEntities[BreedOutDto]:
    entities, total = await breed_service.get_filtered(
        name=name,
        slug=slug,
        description=description,
        page_data=page_data,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    return PaginatedEntities(
        items=[BreedOutDto.model_validate(entity) for entity in entities],
        total=total,
    )


@router.get(
    "/horses/breeds/{slug_or_id}",
    response_model=BreedOutDto | BreedOutWithPageDataDto,
    tags=["Horse Breeds"],
    description="Получить породу по slug или UUID",
)
async def get_breed(
    slug_or_id: str,
    breed_service: Annotated[BreedService, Depends(get_breed_service)],
    page_data: bool = Query(False, description="Включить page_data в ответ"),
) -> BreedOutDto | BreedOutWithPageDataDto:
    breed = await breed_service.get_by_slug_or_id(slug_or_id)
    if breed is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Порода не найдена")

    if page_data:
        return BreedOutWithPageDataDto.model_validate(breed)
    return BreedOutDto.model_validate(breed)


@router.post(
    "/horses/breeds",
    response_model=BreedOutDto,
    tags=["Horse Breeds"],
    description="Создать новую породу",
)
async def create_breed(
    data: BreedCreateDto,
    breed_service: Annotated[BreedService, Depends(get_breed_service)],
) -> BreedOutDto:
    breed = await breed_service.create(data)
    return BreedOutDto.model_validate(breed)


@router.patch(
    "/horses/breeds/{slug_or_id}",
    response_model=BreedOutDto,
    tags=["Horse Breeds"],
    description="Обновить породу",
)
async def update_breed(
    slug_or_id: str,
    data: BreedUpdateDto,
    breed_service: Annotated[BreedService, Depends(get_breed_service)],
) -> BreedOutDto:
    breed = await breed_service.update(slug_or_id, data)
    return BreedOutDto.model_validate(breed)


@router.delete(
    "/horses/breeds/{slug_or_id}",
    status_code=204,
    tags=["Horse Breeds"],
    description="Удалить породу",
)
async def delete_breed(
    slug_or_id: str,
    breed_service: Annotated[BreedService, Depends(get_breed_service)],
) -> None:
    await breed_service.delete(slug_or_id)
