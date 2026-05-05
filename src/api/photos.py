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
from core.schemas.photos import (
    PhotoBatchDeleteDto,
    PhotoCreateDto,
    PhotoOutDto,
    PhotoUpdateDto,
)
from core.services.photos import PhotoService
from depends.services import get_photo_service

router = APIRouter()


@router.get(
    "/photos",
    response_model=PaginatedEntities[PhotoOutDto],
    tags=["Photos"],
    description="Получить список фотографий с фильтрацией и сортировкой",
)
async def get_photos(
    photo_service: Annotated[PhotoService, Depends(get_photo_service)],
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
        name=name,
        description=description,
        price_ids=price_ids,
        horse_ids=horse_ids,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    items = [PhotoOutDto.model_validate(entity) for entity in entities]
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
) -> PhotoOutDto:
    photo = await photo_service.get_by_id(id)
    if photo is None:
        raise HTTPException(status_code=404, detail="Фотография не найдена")

    return PhotoOutDto.model_validate(photo)


@router.post(
    "/photos",
    response_model=PhotoOutDto,
    tags=["Photos"],
    description="Создать новую фотографию",
)
async def create_photo(
    photo_service: Annotated[PhotoService, Depends(get_photo_service)],
    file: UploadFile = File(..., description="Файл фотографии или видео"),
    name: str | None = Form(
        None, description="Название (опционально, генерируется из имени файла)"
    ),
    description: str | None = Form(
        None, description="Описание (опционально, по умолчанию пустая строка)"
    ),
) -> PhotoOutDto:
    data = PhotoCreateDto(name=name, description=description)
    photo = await photo_service.create_from_upload(data, file, file.filename)

    return PhotoOutDto.model_validate(photo)


@router.patch(
    "/photos/{id}",
    response_model=PhotoOutDto,
    tags=["Photos"],
    description="Обновить фотографию",
)
async def update_photo(
    photo_service: Annotated[PhotoService, Depends(get_photo_service)],
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
    photo = await photo_service.update_from_upload(
        id, data, file, file.filename if file else None
    )

    return PhotoOutDto.model_validate(photo)


@router.delete(
    "/photos/{id}",
    status_code=204,
    tags=["Photos"],
    description="Удалить фотографию",
)
async def delete_photo(
    id: UUID,
    photo_service: Annotated[PhotoService, Depends(get_photo_service)],
) -> None:
    await photo_service.delete(id)


@router.post(
    "/photos/batch-delete",
    status_code=204,
    tags=["Photos"],
    description="Массовое удаление фотографий",
)
async def batch_delete_photos(
    photo_service: Annotated[PhotoService, Depends(get_photo_service)],
    data: PhotoBatchDeleteDto = Body(...),
) -> None:
    await photo_service.batch_delete(data.ids)
