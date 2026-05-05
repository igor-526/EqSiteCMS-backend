from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from core.entities import (
    _HORSE_AVAILABLE_SORT_FIELDS,
    HorseKindEnum,
    HorseSexEnum,
    PaginatedEntities,
)
from core.schemas import (
    HorseCreateInDto,
    HorseOutDto,
    HorseSetPedigreeInDto,
    HorseUpdateInDto,
    HorseWithPedigreeOutDto,
    UserOutDto,
)
from core.services.horse import HorseService
from depends.services import get_current_user, get_horse_service

router = APIRouter()


@router.get(
    "",
    response_model=PaginatedEntities[HorseOutDto | HorseWithPedigreeOutDto],
    description="Получить список лошадей с фильтрацией и сортировкой",
)
async def get_horses(
    horse_service: Annotated[HorseService, Depends(get_horse_service)],
    current_user: Annotated[UserOutDto | None, Depends(get_current_user)],
    sort: list[_HORSE_AVAILABLE_SORT_FIELDS] | None = Query(
        None, description="Сортировка"
    ),
    name: str | None = Query(None, description="Фильтр по имени"),
    description: str | None = Query(None, description="Фильтр по описанию"),
    breed_ids: list[UUID] | None = Query(
        None, description="Фильтр по идентификаторам пород"
    ),
    coat_color_ids: list[UUID] | None = Query(
        None, description="Фильтр по идентификаторам мастей"
    ),
    kind: list[HorseKindEnum] | None = Query(None, description="Фильтр по виду"),
    height_gte: int | None = Query(None, description="Фильтр по минимальному росту"),
    height_lte: int | None = Query(None, description="Фильтр по максимальному росту"),
    sex: list[HorseSexEnum] | None = Query(None, description="Фильтр по полу"),
    bdate_gte: date | None = Query(
        None, description="Фильтр по минимальной дате рождения"
    ),
    bdate_lte: date | None = Query(
        None, description="Фильтр по максимальной дате рождения"
    ),
    ddate_gte: date | None = Query(
        None, description="Фильтр по минимальной дате смерти"
    ),
    ddate_lte: date | None = Query(
        None, description="Фильтр по максимальной дате смерти"
    ),
    horse_owner_ids: list[UUID] | None = Query(
        None, description="Фильтр по идентификаторам владельцев"
    ),
    this_stable: bool | None = Query(None, description="Фильтр по статусу на конюшке"),
    exclude_ids: list[UUID] | None = Query(
        None, description="Идентификаторы лошадей, исключаемые из выдачи"
    ),
    include_ids: list[UUID] | None = Query(
        None, description="Искать только среди лошадей с указанными идентификаторами"
    ),
    pedigree: int | None = Query(None, description="Количество поколений"),
    limit: int | None = Query(None, description="Лимит"),
    offset: int | None = Query(None, description="Смещение"),
) -> PaginatedEntities[HorseOutDto | HorseWithPedigreeOutDto]:
    return await horse_service.get_filtered_horses(
        user=current_user,
        name=name,
        description=description,
        breed_ids=breed_ids,
        coat_color_ids=coat_color_ids,
        kind=kind,
        height_gte=height_gte,
        height_lte=height_lte,
        sex=sex,
        bdate_gte=bdate_gte,
        bdate_lte=bdate_lte,
        ddate_gte=ddate_gte,
        ddate_lte=ddate_lte,
        horse_owner_ids=horse_owner_ids,
        pedigree=pedigree,
        this_stable=this_stable,
        exclude_ids=exclude_ids,
        include_ids=include_ids,
        limit=limit,
        offset=offset,
        sort=sort,
    )


@router.get(
    "/{slug_or_id}",
    response_model=HorseOutDto | HorseWithPedigreeOutDto,
    description="Получить лошадь по slug или UUID",
)
async def get_horse(
    current_user: Annotated[UserOutDto | None, Depends(get_current_user)],
    horse_service: Annotated[HorseService, Depends(get_horse_service)],
    slug_or_id: str,
    pedigree: int | None = Query(None, description="Количество поколений"),
) -> HorseOutDto | HorseWithPedigreeOutDto:
    return await horse_service.get_horse_by_slug_or_id(
        slug_or_id=slug_or_id, pedigree=pedigree, user=current_user
    )


@router.post(
    "",
    response_model=HorseOutDto,
    description="Создать новую лошадь",
)
async def create_new_horse(
    current_user: Annotated[UserOutDto | None, Depends(get_current_user)],
    data: HorseCreateInDto,
    horse_service: Annotated[HorseService, Depends(get_horse_service)],
) -> HorseOutDto:
    return await horse_service.create_horse(create_data=data, user=current_user)


@router.patch(
    "/{horse_id}",
    response_model=HorseOutDto,
    description="Обновить лошадь",
)
async def update_existing_horse(
    current_user: Annotated[UserOutDto | None, Depends(get_current_user)],
    horse_id: UUID,
    data: HorseUpdateInDto,
    horse_service: Annotated[HorseService, Depends(get_horse_service)],
) -> HorseOutDto:
    return await horse_service.update_horse(
        horse_id=horse_id, data=data, user=current_user
    )


@router.delete(
    "/{horse_id}",
    status_code=204,
    description="Удалить лошадь",
)
async def delete_existing_horse(
    current_user: Annotated[UserOutDto | None, Depends(get_current_user)],
    horse_id: UUID,
    horse_service: Annotated[HorseService, Depends(get_horse_service)],
) -> None:
    return await horse_service.delete_horse(horse_id=horse_id, user=current_user)


@router.post(
    "{horse_id}/pedigree",
    description="Установить родословное древо лошади",
    status_code=204,
)
async def set_horse_pedigree(
    current_user: Annotated[UserOutDto | None, Depends(get_current_user)],
    horse_id: UUID,
    data: HorseSetPedigreeInDto,
    horse_service: Annotated[HorseService, Depends(get_horse_service)],
) -> None:
    return await horse_service.set_horse_pedigree(
        horse_id=horse_id, pedigree_data=data, user=current_user
    )


@router.get(
    "{horse_id}/pedigree/{mode}",
    description="Получить родословное древо лошади",
    response_model=PaginatedEntities[HorseOutDto],
)
async def get_horse_pedigree(
    current_user: Annotated[UserOutDto | None, Depends(get_current_user)],
    horse_service: Annotated[HorseService, Depends(get_horse_service)],
    horse_id: UUID,
    mode: Literal["sire", "dame", "children"],
    search: str | None = Query(None, description="Поиск"),
    limit: int | None = Query(None, description="Лимит"),
    offset: int | None = Query(None, description="Смещение"),
) -> PaginatedEntities[HorseOutDto]:
    return await horse_service.get_available_pedigree(
        horse_id=horse_id,
        user=current_user,
        mode=mode,
        search=search,
        limit=limit,
        offset=offset,
    )
