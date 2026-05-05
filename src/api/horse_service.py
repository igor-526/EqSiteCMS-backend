from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from core.entities.base import PaginatedEntities
from core.schemas.horse_service import (
    HorseServiceCreateDto,
    HorseServiceOutDto,
    HorseServiceOutWithPageDataDto,
    HorseServiceUpdateDto,
)
from core.services.horse_service import HorseServiceService
from depends.services import get_horse_service_service

router = APIRouter()


@router.get(
    "/horses/services",
    response_model=PaginatedEntities[HorseServiceOutDto],
    tags=["Horse Service"],
    description="Получить список услуг с фильтрацией и сортировкой",
)
async def get_horse_services(
    horse_service_service: Annotated[
        HorseServiceService, Depends(get_horse_service_service)
    ],
    name: str | None = Query(None, description="Фильтр по названию (вхождение)"),
    slug: str | None = Query(None, description="Фильтр по slug (вхождение)"),
    description: str | None = Query(None, description="Фильтр по описанию (вхождение)"),
    page_data: str | None = Query(None, description="Фильтр по page_data (вхождение)"),
    sort: (
        list[
            Literal[
                "name",
                "description",
                "slug",
                "price",
                "-name",
                "-description",
                "-slug",
                "-price",
            ]
        ]
        | None
    ) = Query(None, description="Сортировка"),
    limit: int | None = Query(None, description="Лимит"),
    offset: int | None = Query(None, description="Смещение"),
) -> PaginatedEntities[HorseServiceOutDto]:
    entities, total = await horse_service_service.get_filtered(
        name=name,
        slug=slug,
        description=description,
        page_data=page_data,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    return PaginatedEntities(
        items=[HorseServiceOutDto.model_validate(entity) for entity in entities],
        total=total,
    )


@router.get(
    "/horses/services/{slug_or_id}",
    response_model=HorseServiceOutDto | HorseServiceOutWithPageDataDto,
    tags=["Horse Service"],
    description="Получить услугу по slug или UUID",
)
async def get_horse_service(
    horse_service_service: Annotated[
        HorseServiceService, Depends(get_horse_service_service)
    ],
    slug_or_id: str,
    page_data: bool = Query(False, description="Включить page_data в ответ"),
) -> HorseServiceOutDto | HorseServiceOutWithPageDataDto:
    horse_service = await horse_service_service.get_by_slug_or_id(slug_or_id)
    if horse_service is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Услуга не найдена")

    if page_data:
        return HorseServiceOutWithPageDataDto.model_validate(horse_service)
    return HorseServiceOutDto.model_validate(horse_service)


@router.post(
    "/horses/services",
    response_model=HorseServiceOutDto,
    tags=["Horse Service"],
    description="Создать новую услугу",
)
async def create_horse_service(
    data: HorseServiceCreateDto,
    horse_service_service: Annotated[
        HorseServiceService, Depends(get_horse_service_service)
    ],
) -> HorseServiceOutDto:
    horse_service = await horse_service_service.create(data)
    return HorseServiceOutDto.model_validate(horse_service)


@router.patch(
    "/horses/services/{slug_or_id}",
    response_model=HorseServiceOutDto,
    tags=["Horse Service"],
    description="Обновить услугу",
)
async def update_horse_service(
    slug_or_id: str,
    data: HorseServiceUpdateDto,
    horse_service_service: Annotated[
        HorseServiceService, Depends(get_horse_service_service)
    ],
) -> HorseServiceOutDto:
    horse_service = await horse_service_service.update(slug_or_id, data)
    return HorseServiceOutDto.model_validate(horse_service)


@router.delete(
    "/horses/services/{slug_or_id}",
    status_code=204,
    tags=["Horse Service"],
    description="Удалить услугу",
)
async def delete_horse_service(
    slug_or_id: str,
    horse_service_service: Annotated[
        HorseServiceService, Depends(get_horse_service_service)
    ],
) -> None:
    await horse_service_service.delete(slug_or_id)
