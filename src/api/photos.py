from typing import Annotated, Literal
from uuid import UUID

from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)

from core.entities.base import PaginatedEntities
from core.entities.equestrian import EquestrianContext
from core.schemas.photos import (
    PhotoBatchDeleteDto,
    PhotoCreateDto,
    PhotoOutDto,
    PhotoUpdateDto,
    PhotoUploadDto,
)
from core.services.photos import PhotoService
from depends.services import (
    get_current_user,
    get_photo_service,
    get_protected_equestrian_context,
    get_read_equestrian_context,
)

router = APIRouter()


def to_photo_out_dto(photo_service: PhotoService, photo) -> PhotoOutDto:
    return PhotoOutDto.model_validate(
        {
            **photo.model_dump(),
            "url": photo_service.build_url(photo.path),
        }
    )


async def to_photo_upload_dto(file: UploadFile) -> PhotoUploadDto:
    return PhotoUploadDto(
        filename=file.filename or "",
        content=await file.read(),
        content_type=file.content_type,
    )


@router.get(
    "/photos",
    response_model=PaginatedEntities[PhotoOutDto],
    tags=["Photos"],
    description="Получить список фотографий с фильтрацией и сортировкой",
)
async def get_photos(
    photo_service: Annotated[PhotoService, Depends(get_photo_service)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_read_equestrian_context)
    ],
    name: str | None = Query(None, description="Фильтр по названию (вхождение)"),
    description: str | None = Query(None, description="Фильтр по описанию (вхождение)"),
    price_ids: list[UUID] | None = Query(None, description="Фильтр по UUID услуг"),
    horse_ids: list[UUID] | None = Query(None, description="Фильтр по UUID лошадей"),
    sort: (
        list[
            Literal[
                "name",
                "description",
                "created_at",
                "-name",
                "-description",
                "-created_at",
            ]
        ]
        | None
    ) = Query(None, description="Сортировка"),
    limit: int | None = Query(None, description="Лимит"),
    offset: int | None = Query(None, description="Смещение"),
) -> PaginatedEntities[PhotoOutDto]:
    entities, total = await photo_service.get_filtered(
        equestrian_context=equestrian_context,
        name=name,
        description=description,
        price_ids=price_ids,
        horse_ids=horse_ids,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    items = [to_photo_out_dto(photo_service, entity) for entity in entities]
    return PaginatedEntities(items=items, total=total)


@router.get(
    "/photos/{id}",
    response_model=PhotoOutDto,
    tags=["Photos"],
    description="Получить фотографию по UUID",
)
async def get_photo(
    id: UUID,
    photo_service: Annotated[PhotoService, Depends(get_photo_service)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_read_equestrian_context)
    ],
) -> PhotoOutDto:
    photo = await photo_service.get_by_id(id, equestrian_context=equestrian_context)
    if photo is None:
        raise HTTPException(status_code=404, detail="Фотография не найдена")

    return to_photo_out_dto(photo_service, photo)


@router.post(
    "/photos",
    response_model=PhotoOutDto,
    tags=["Photos"],
    description="Создать новую фотографию",
)
async def create_photo(
    photo_service: Annotated[PhotoService, Depends(get_photo_service)],
    _: Annotated[object, Depends(get_current_user)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_protected_equestrian_context)
    ],
    file: UploadFile = File(..., description="Файл фотографии или видео"),
    name: str | None = Form(
        None, description="Название (опционально, генерируется из имени файла)"
    ),
    description: str | None = Form(
        None, description="Описание (опционально, по умолчанию пустая строка)"
    ),
) -> PhotoOutDto:
    data = PhotoCreateDto(name=name, description=description)
    upload = await to_photo_upload_dto(file)
    photo = await photo_service.create(
        data, upload, equestrian_context=equestrian_context
    )

    return to_photo_out_dto(photo_service, photo)


@router.patch(
    "/photos/{id}",
    response_model=PhotoOutDto,
    tags=["Photos"],
    description="Обновить фотографию",
)
async def update_photo(
    photo_service: Annotated[PhotoService, Depends(get_photo_service)],
    _: Annotated[object, Depends(get_current_user)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_protected_equestrian_context)
    ],
    id: UUID,
    file: UploadFile | None = File(
        None, description="Новый файл фотографии или видео (опционально)"
    ),
    name: str | None = Form(None, description="Название (опционально)"),
    description: str | None = Form(
        None, description="Описание (опционально, пустая строка если не указано)"
    ),
) -> PhotoOutDto:
    data = PhotoUpdateDto(name=name, description=description)
    upload = None
    if file is not None:
        upload = await to_photo_upload_dto(file)
    photo = await photo_service.update(
        id, data, upload=upload, equestrian_context=equestrian_context
    )

    return to_photo_out_dto(photo_service, photo)


@router.delete(
    "/photos/{id}",
    status_code=204,
    tags=["Photos"],
    description="Удалить фотографию",
)
async def delete_photo(
    id: UUID,
    photo_service: Annotated[PhotoService, Depends(get_photo_service)],
    _: Annotated[object, Depends(get_current_user)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_protected_equestrian_context)
    ],
) -> None:
    await photo_service.delete(id, equestrian_context=equestrian_context)


@router.post(
    "/photos/batch-delete",
    status_code=204,
    tags=["Photos"],
    description="Массовое удаление фотографий",
)
async def batch_delete_photos(
    photo_service: Annotated[PhotoService, Depends(get_photo_service)],
    _: Annotated[object, Depends(get_current_user)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_protected_equestrian_context)
    ],
    data: PhotoBatchDeleteDto = Body(...),
) -> None:
    await photo_service.batch_delete(data.ids, equestrian_context=equestrian_context)
