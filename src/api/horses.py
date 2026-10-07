from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile

from core.entities import (
    _HORSE_AVAILABLE_SORT_FIELDS,
    HorseKindEnum,
    HorseSexEnum,
    PaginatedEntities,
)
from core.entities.equestrian import EquestrianContext
from core.schemas import (
    HorseCreateInDto,
    HorseOutDto,
    HorsePhotosUpdateInDto,
    HorsePhotosUploadDto,
    HorseSetPedigreeInDto,
    HorseUpdateInDto,
    HorseWithPedigreeOutDto,
    UserOutDto,
)
from core.schemas.photos import PhotoBatchUploadResponseDto
from core.services.horse import HorseService
from depends.services import (
    get_current_user,
    get_horse_service,
    get_protected_equestrian_context,
    get_read_equestrian_context,
)

router = APIRouter()


@router.get(
    "",
    response_model=PaginatedEntities[HorseOutDto | HorseWithPedigreeOutDto],
    description=(
        "Public Read: получить tenant-scoped список лошадей с фильтрацией и "
        "сортировкой. Услуги передаются повторяемыми query-параметрами "
        "`services=<uuid>&services=<uuid>` и объединяются по OR."
    ),
)
async def get_horses(
    horse_service: Annotated[HorseService, Depends(get_horse_service)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_read_equestrian_context)
    ],
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
    kind: list[HorseKindEnum] | None = Query(None, description="Фильтр по виду породы"),
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
    services: list[UUID] | None = Query(
        None,
        description=(
            "Повторяемый фильтр по UUID оказываемых услуг; несколько значений "
            "используют OR-семантику"
        ),
    ),
    service_names: list[str] | None = Query(
        None,
        description=(
            "Фильтр по наименованиям услуг (регистронезависимое полное совпадение); "
            "несколько значений используют OR-семантику"
        ),
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
        equestrian_context=equestrian_context,
        user=None,
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
        services=services,
        service_names=service_names,
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
    horse_service: Annotated[HorseService, Depends(get_horse_service)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_read_equestrian_context)
    ],
    slug_or_id: str,
    pedigree: int | None = Query(None, description="Количество поколений"),
) -> HorseOutDto | HorseWithPedigreeOutDto:
    return await horse_service.get_horse_by_slug_or_id(
        slug_or_id=slug_or_id,
        pedigree=pedigree,
        user=None,
        equestrian_context=equestrian_context,
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
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_protected_equestrian_context)
    ],
) -> HorseOutDto:
    return await horse_service.create_horse(
        create_data=data, user=current_user, equestrian_context=equestrian_context
    )


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
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_protected_equestrian_context)
    ],
) -> HorseOutDto:
    return await horse_service.update_horse(
        horse_id=horse_id,
        data=data,
        user=current_user,
        equestrian_context=equestrian_context,
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
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_protected_equestrian_context)
    ],
) -> None:
    return await horse_service.delete_horse(
        horse_id=horse_id, user=current_user, equestrian_context=equestrian_context
    )


@router.post(
    "/{horse_id}/pedigree",
    description="Установить родословное древо лошади",
    status_code=204,
)
async def set_horse_pedigree(
    current_user: Annotated[UserOutDto | None, Depends(get_current_user)],
    horse_id: UUID,
    data: HorseSetPedigreeInDto,
    horse_service: Annotated[HorseService, Depends(get_horse_service)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_protected_equestrian_context)
    ],
) -> None:
    return await horse_service.set_horse_pedigree(
        horse_id=horse_id,
        pedigree_data=data,
        user=current_user,
        equestrian_context=equestrian_context,
    )


@router.post(
    "/{horse_id}/photos",
    response_model=HorseOutDto,
    description="Обновить список фотографий лошади (полная замена)",
)
async def update_horse_photos(
    current_user: Annotated[UserOutDto, Depends(get_current_user)],
    horse_id: UUID,
    data: HorsePhotosUpdateInDto,
    horse_service: Annotated[HorseService, Depends(get_horse_service)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_protected_equestrian_context)
    ],
) -> HorseOutDto:
    return await horse_service.update_horse_photos(
        horse_id=horse_id,
        data=data,
        user=current_user,
        equestrian_context=equestrian_context,
    )


@router.post(
    "/{horse_id}/photos/upload",
    response_model=PhotoBatchUploadResponseDto,
    description="Batch upload фотографий и автоматическое присоединение к лошади (Protected Write: 401 без auth, 403 не owner, 200 OK owner)",
)
async def upload_and_attach_photos_to_horse(
    horse_id: UUID,
    horse_service: Annotated[HorseService, Depends(get_horse_service)],
    current_user: Annotated[UserOutDto, Depends(get_current_user)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_protected_equestrian_context)
    ],
    files: list[UploadFile] = File(
        ...,
        description="Массив файлов (минимум 1, максимум 20)",
        min_length=1,
        max_length=20,
    ),
    names: list[str] | None = Form(
        None,
        description="Опциональные названия фото (по индексу соответствуют files[])",
    ),
    descriptions: list[str] | None = Form(
        None,
        description="Опциональные описания фото (по индексу соответствуют files[])",
    ),
) -> PhotoBatchUploadResponseDto:
    """Batch upload+attach endpoint для лошадей.

    Multipart/form-data с полями:
    - files[] — массив файлов (обязательно, 1-20 файлов)
    - names[] — опциональные названия (по индексу)
    - descriptions[] — опциональные описания (по индексу)

    Возвращает PhotoBatchUploadResponseDto с photos[] и errors[] (partial success).

    Access control: Protected Write (требует авторизацию и проверку owner).
    """
    # Читаем содержимое файлов
    file_contents = []
    filenames: list[str] = []
    for file in files:
        content = await file.read()
        file_contents.append(content)
        filenames.append(file.filename or f"file_{len(filenames)}")

    # Создаём DTO для service layer
    data = HorsePhotosUploadDto(
        files=file_contents,
        names=names,
        descriptions=descriptions,
    )

    # Вызываем service method
    return await horse_service.upload_and_attach_photos(
        horse_id,
        data,
        filenames,
        user=current_user,
        equestrian_context=equestrian_context,
    )


@router.get(
    "/{horse_id}/pedigree/{mode}",
    description="Получить родословное древо лошади",
    response_model=PaginatedEntities[HorseOutDto],
)
async def get_horse_pedigree(
    horse_service: Annotated[HorseService, Depends(get_horse_service)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_read_equestrian_context)
    ],
    horse_id: UUID,
    mode: Literal["sire", "dam", "children"],
    search: str | None = Query(None, description="Поиск"),
    limit: int | None = Query(None, description="Лимит"),
    offset: int | None = Query(None, description="Смещение"),
) -> PaginatedEntities[HorseOutDto]:
    return await horse_service.get_available_pedigree(
        horse_id=horse_id,
        user=None,
        equestrian_context=equestrian_context,
        mode=mode,
        search=search,
        limit=limit,
        offset=offset,
    )
