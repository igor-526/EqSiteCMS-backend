from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from core.entities.equestrian import EquestrianContext
from core.schemas.horse_service_relations import (
    HorseServiceRelationCreateDto,
    HorseServiceRelationOutDto,
    HorseServiceRelationUpdateDto,
)
from core.services.horse_service_relations import HorseServiceRelationsService
from depends.services import (
    get_current_user,
    get_horse_service_relations_service,
    get_protected_equestrian_context,
    get_read_equestrian_context,
)

router = APIRouter()


@router.post(
    "/horses/{horse_id}/services",
    response_model=HorseServiceRelationOutDto,
    status_code=201,
    tags=["Horse Service Relations"],
    description="Создать связь лошадь-услуга",
)
async def create_horse_service_relation(
    horse_id: UUID,
    data: HorseServiceRelationCreateDto,
    service: Annotated[
        HorseServiceRelationsService, Depends(get_horse_service_relations_service)
    ],
    _: Annotated[object, Depends(get_current_user)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_protected_equestrian_context)
    ],
) -> HorseServiceRelationOutDto:
    return await service.create(horse_id, data, equestrian_context=equestrian_context)


@router.patch(
    "/horses/{horse_id}/services/{relation_id}",
    response_model=HorseServiceRelationOutDto,
    tags=["Horse Service Relations"],
    description="Обновить связь лошадь-услуга",
)
async def update_horse_service_relation(
    horse_id: UUID,
    relation_id: UUID,
    data: HorseServiceRelationUpdateDto,
    service: Annotated[
        HorseServiceRelationsService, Depends(get_horse_service_relations_service)
    ],
    _: Annotated[object, Depends(get_current_user)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_protected_equestrian_context)
    ],
) -> HorseServiceRelationOutDto:
    return await service.update(
        horse_id, relation_id, data, equestrian_context=equestrian_context
    )


@router.delete(
    "/horses/{horse_id}/services/{relation_id}",
    status_code=204,
    tags=["Horse Service Relations"],
    description="Удалить связь лошадь-услуга",
)
async def delete_horse_service_relation(
    horse_id: UUID,
    relation_id: UUID,
    service: Annotated[
        HorseServiceRelationsService, Depends(get_horse_service_relations_service)
    ],
    _: Annotated[object, Depends(get_current_user)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_protected_equestrian_context)
    ],
) -> None:
    await service.delete(horse_id, relation_id, equestrian_context=equestrian_context)


@router.get(
    "/horses/{horse_id}/services",
    response_model=list[HorseServiceRelationOutDto],
    tags=["Horse Service Relations"],
    description="Получить список связей лошадь-услуга",
)
async def get_horse_service_relations(
    horse_id: UUID,
    service: Annotated[
        HorseServiceRelationsService, Depends(get_horse_service_relations_service)
    ],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_read_equestrian_context)
    ],
) -> list[HorseServiceRelationOutDto]:
    return await service.get_list_by_horse(
        horse_id, equestrian_context=equestrian_context
    )


@router.get(
    "/horses/{horse_id}/available-services",
    tags=["Horse Service Relations"],
    description="Получить доступные услуги для привязки к лошади",
)
async def get_available_services(
    horse_id: UUID,
    service: Annotated[
        HorseServiceRelationsService, Depends(get_horse_service_relations_service)
    ],
    _: Annotated[object, Depends(get_current_user)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_protected_equestrian_context)
    ],
    search: str | None = Query(None, description="Поиск по названию услуги"),
) -> list[dict]:
    return await service.get_available_services(
        horse_id, equestrian_context=equestrian_context, search=search
    )
