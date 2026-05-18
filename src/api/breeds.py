from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from core.entities.base import PaginatedEntities
from core.entities.equestrian import EquestrianContext
from core.entities.horse import HorseKindEnum
from core.schemas.breeds import (
    BreedCreateDto,
    BreedOutDto,
    BreedOutWithPageDataDto,
    BreedUpdateDto,
)
from core.schemas.users import UserOutDto
from core.services.breeds import BreedService
from depends.services import (
    get_breed_service,
    get_current_user,
    get_protected_equestrian_context,
    get_read_equestrian_context,
)

router = APIRouter()


@router.get(
    "/horses/breeds",
    response_model=PaginatedEntities[BreedOutDto],
    tags=["Horse Breeds"],
    description="Получить список пород с фильтрацией и сортировкой",
)
async def get_breeds(
    breed_service: Annotated[BreedService, Depends(get_breed_service)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_read_equestrian_context)
    ],
    name: str | None = Query(None, description="Фильтр по названию (вхождение)"),
    slug: str | None = Query(None, description="Фильтр по slug (вхождение)"),
    description: str | None = Query(None, description="Фильтр по описанию (вхождение)"),
    page_data: str | None = Query(None, description="Фильтр по page_data (вхождение)"),
    kind: list[HorseKindEnum] | None = Query(None, description="Фильтр по виду породы"),
    sort: (
        list[
            Literal[
                "name",
                "description",
                "slug",
                "kind",
                "-name",
                "-description",
                "-slug",
                "-kind",
            ]
        ]
        | None
    ) = Query(None, description="Сортировка"),
    limit: int | None = Query(None, description="Лимит"),
    offset: int | None = Query(None, description="Смещение"),
) -> PaginatedEntities[BreedOutDto]:
    entities, total = await breed_service.get_filtered(
        equestrian_context=equestrian_context,
        name=name,
        slug=slug,
        description=description,
        page_data=page_data,
        kind=kind,
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
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_read_equestrian_context)
    ],
    page_data: bool = Query(False, description="Включить page_data в ответ"),
) -> BreedOutDto | BreedOutWithPageDataDto:
    breed = await breed_service.get_by_slug_or_id(
        slug_or_id, equestrian_context=equestrian_context
    )
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
    current_user: Annotated[UserOutDto, Depends(get_current_user)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_protected_equestrian_context)
    ],
) -> BreedOutDto:
    breed = await breed_service.create(
        data, equestrian_context=equestrian_context, user=current_user
    )
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
    current_user: Annotated[UserOutDto, Depends(get_current_user)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_protected_equestrian_context)
    ],
) -> BreedOutDto:
    breed = await breed_service.update(
        slug_or_id, data, equestrian_context=equestrian_context, user=current_user
    )
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
    current_user: Annotated[UserOutDto, Depends(get_current_user)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_protected_equestrian_context)
    ],
) -> None:
    await breed_service.delete(
        slug_or_id, equestrian_context=equestrian_context, user=current_user
    )
