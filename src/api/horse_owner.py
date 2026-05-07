from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from core.entities.base import PaginatedEntities
from core.entities.equestrian import EquestrianContext
from core.schemas.horse_owner import (
    HorseOwnerCreateInDto,
    HorseOwnerOutDto,
    HorseOwnerUpdateDto,
)
from core.services.horse_owner import HorseOwnerService
from depends.services import (
    get_current_user,
    get_horse_owner_service,
    get_protected_equestrian_context,
    get_read_equestrian_context,
)

router = APIRouter()


@router.get(
    "/horses/owners",
    response_model=PaginatedEntities[HorseOwnerOutDto],
    tags=["Horse Owners"],
    description="Получить список владельцев с фильтрацией и сортировкой",
)
async def get_horse_owners(
    horse_owner_service: Annotated[HorseOwnerService, Depends(get_horse_owner_service)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_read_equestrian_context)
    ],
    name: str | None = Query(None, description="Фильтр по имени (вхождение)"),
    description: str | None = Query(None, description="Фильтр по описанию (вхождение)"),
    type: list[str] | None = Query(
        None, description="Фильтр по типу (множественная фильтрация)"
    ),
    address: str | None = Query(None, description="Фильтр по адресу (вхождение)"),
    phone_numbers: str | None = Query(
        None, description="Фильтр по телефонным номерам (вхождение)"
    ),
    sort: (
        list[Literal["name", "description", "type", "-name", "-description", "-type"]]
        | None
    ) = Query(None, description="Сортировка"),
    limit: int | None = Query(None, description="Лимит"),
    offset: int | None = Query(None, description="Смещение"),
) -> PaginatedEntities[HorseOwnerOutDto]:
    entities, total = await horse_owner_service.get_filtered(
        equestrian_context=equestrian_context,
        name=name,
        description=description,
        type=type,
        address=address,
        phone_numbers=phone_numbers,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    return PaginatedEntities(
        items=[HorseOwnerOutDto.model_validate(entity) for entity in entities],
        total=total,
    )


@router.get(
    "/horses/owners/{id}",
    response_model=HorseOwnerOutDto,
    tags=["Horse Owners"],
    description="Получить владельца по UUID",
)
async def get_horse_owner(
    id: UUID,
    horse_owner_service: Annotated[HorseOwnerService, Depends(get_horse_owner_service)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_read_equestrian_context)
    ],
) -> HorseOwnerOutDto:
    horse_owner = await horse_owner_service.get_by_id_or_raise(
        id, equestrian_context=equestrian_context
    )
    return HorseOwnerOutDto.model_validate(horse_owner)


@router.post(
    "/horses/owners",
    response_model=HorseOwnerOutDto,
    tags=["Horse Owners"],
    description="Создать нового владельца",
)
async def create_horse_owner(
    data: HorseOwnerCreateInDto,
    horse_owner_service: Annotated[HorseOwnerService, Depends(get_horse_owner_service)],
    _: Annotated[object, Depends(get_current_user)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_protected_equestrian_context)
    ],
) -> HorseOwnerOutDto:
    horse_owner = await horse_owner_service.create(
        data, equestrian_context=equestrian_context
    )
    return HorseOwnerOutDto.model_validate(horse_owner)


@router.patch(
    "/horses/owners/{id}",
    response_model=HorseOwnerOutDto,
    tags=["Horse Owners"],
    description="Обновить владельца",
)
async def update_horse_owner(
    id: UUID,
    data: HorseOwnerUpdateDto,
    horse_owner_service: Annotated[HorseOwnerService, Depends(get_horse_owner_service)],
    _: Annotated[object, Depends(get_current_user)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_protected_equestrian_context)
    ],
) -> HorseOwnerOutDto:
    horse_owner = await horse_owner_service.update(
        id, data, equestrian_context=equestrian_context
    )
    return HorseOwnerOutDto.model_validate(horse_owner)


@router.delete(
    "/horses/owners/{id}",
    status_code=204,
    tags=["Horse Owners"],
    description="Удалить владельца",
)
async def delete_horse_owner(
    id: UUID,
    horse_owner_service: Annotated[HorseOwnerService, Depends(get_horse_owner_service)],
    _: Annotated[object, Depends(get_current_user)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_protected_equestrian_context)
    ],
) -> None:
    await horse_owner_service.delete(id, equestrian_context=equestrian_context)
