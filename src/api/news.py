from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile

from core.entities.base import PaginatedEntities
from core.entities.equestrian import EquestrianContext
from core.entities.news import NewsStatus
from core.schemas.news import (
    NewsCreateDto,
    NewsOutDto,
    NewsPhotosUpdateDto,
    NewsPhotosUploadDto,
    NewsPublicDetailOutDto,
    NewsPublicOutDto,
    NewsUpdateDto,
)
from core.schemas.photos import PhotoBatchUploadResponseDto
from core.schemas.users import UserOutDto
from core.services.news import NewsService
from depends.services import (
    get_current_user,
    get_news_service,
    get_protected_equestrian_context,
    get_public_news_equestrian_context,
)

router = APIRouter()


@router.get(
    "/news-cms",
    response_model=PaginatedEntities[NewsOutDto],
    tags=["News"],
    description="Список новостей для CMS (защищённый GET, требует авторизацию)",
)
async def get_news_cms(
    news_service: Annotated[NewsService, Depends(get_news_service)],
    current_user: Annotated[UserOutDto, Depends(get_current_user)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_protected_equestrian_context)
    ],
    name: str | None = Query(None, description="Поиск по названию (~* regex)"),
    snippet: str | None = Query(None, description="Поиск по сниппету (~* regex)"),
    content: str | None = Query(None, description="Поиск по содержимому (~* regex)"),
    published_at_from: datetime | None = Query(None, description="Дата публикации от"),
    published_at_to: datetime | None = Query(None, description="Дата публикации до"),
    status: list[NewsStatus] | None = Query(None, description="Фильтр по статусам"),
    sort: str = Query("-published_at", description="Сортировка"),
    page: int = Query(1, ge=1, description="Страница"),
    limit: int = Query(25, ge=1, le=100, description="Размер страницы"),
) -> PaginatedEntities[NewsOutDto]:
    offset = (page - 1) * limit
    items, total = await news_service.get_cms_list(
        equestrian_context=equestrian_context,
        user=current_user,
        name=name,
        snippet=snippet,
        content=content,
        published_at_from=published_at_from,
        published_at_to=published_at_to,
        status=status,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    dtos = [
        await news_service.build_out_dto(item, equestrian_context=equestrian_context)
        for item in items
    ]
    return PaginatedEntities(items=dtos, total=total)


@router.get(
    "/news",
    response_model=PaginatedEntities[NewsPublicOutDto],
    tags=["News"],
    description="Список опубликованных новостей (публичный, только не удалённые и published_at <= now())",
)
async def get_news_public(
    news_service: Annotated[NewsService, Depends(get_news_service)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_public_news_equestrian_context)
    ],
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
) -> PaginatedEntities[NewsPublicOutDto]:
    offset = (page - 1) * limit
    items, total = await news_service.get_public_list(
        equestrian_context=equestrian_context,
        limit=limit,
        offset=offset,
    )
    dtos = [
        await news_service.build_public_out_dto(
            item, equestrian_context=equestrian_context
        )
        for item in items
    ]
    return PaginatedEntities(items=dtos, total=total)


@router.get(
    "/news/by-slug/{slug}",
    response_model=NewsPublicDetailOutDto,
    tags=["News"],
    description="Деталь публичной новости по slug (только опубликованные, не удалённые)",
)
async def get_news_detail_by_slug(
    slug: str,
    news_service: Annotated[NewsService, Depends(get_news_service)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_public_news_equestrian_context)
    ],
) -> NewsPublicDetailOutDto:
    news_item = await news_service.get_public_detail_by_slug(
        slug, equestrian_context=equestrian_context
    )
    return await news_service.build_public_detail_out_dto(
        news_item, equestrian_context=equestrian_context
    )


@router.get(
    "/news/{news_id}",
    response_model=NewsPublicDetailOutDto,
    tags=["News"],
    description="Деталь публичной новости (только опубликованные, не удалённые)",
)
async def get_news_detail(
    news_id: UUID,
    news_service: Annotated[NewsService, Depends(get_news_service)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_public_news_equestrian_context)
    ],
) -> NewsPublicDetailOutDto:
    news_item = await news_service.get_public_detail(
        news_id, equestrian_context=equestrian_context
    )
    return await news_service.build_public_detail_out_dto(
        news_item, equestrian_context=equestrian_context
    )


@router.post(
    "/news",
    response_model=NewsOutDto,
    status_code=201,
    tags=["News"],
    description="Создать новость",
)
async def create_news(
    data: NewsCreateDto,
    news_service: Annotated[NewsService, Depends(get_news_service)],
    current_user: Annotated[UserOutDto, Depends(get_current_user)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_protected_equestrian_context)
    ],
) -> NewsOutDto:
    news_item = await news_service.create(
        data, equestrian_context=equestrian_context, user=current_user
    )
    return await news_service.build_out_dto(
        news_item, equestrian_context=equestrian_context
    )


@router.patch(
    "/news/{news_id}",
    response_model=NewsOutDto,
    tags=["News"],
    description="Обновить новость (partial update)",
)
async def update_news(
    news_id: UUID,
    data: NewsUpdateDto,
    news_service: Annotated[NewsService, Depends(get_news_service)],
    current_user: Annotated[UserOutDto, Depends(get_current_user)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_protected_equestrian_context)
    ],
) -> NewsOutDto:
    news_item = await news_service.update(
        news_id, data, equestrian_context=equestrian_context, user=current_user
    )
    return await news_service.build_out_dto(
        news_item, equestrian_context=equestrian_context
    )


@router.delete(
    "/news/{news_id}",
    status_code=204,
    tags=["News"],
    description="Soft delete новости (is_deleted=True, запись не удаляется физически)",
)
async def delete_news(
    news_id: UUID,
    news_service: Annotated[NewsService, Depends(get_news_service)],
    current_user: Annotated[UserOutDto, Depends(get_current_user)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_protected_equestrian_context)
    ],
) -> None:
    await news_service.soft_delete(
        news_id, equestrian_context=equestrian_context, user=current_user
    )


@router.post(
    "/news/{news_id}/photos",
    status_code=204,
    tags=["News"],
    description="Обновить фотографии новости",
)
async def update_news_photos(
    news_id: UUID,
    data: NewsPhotosUpdateDto,
    news_service: Annotated[NewsService, Depends(get_news_service)],
    _: Annotated[object, Depends(get_current_user)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_protected_equestrian_context)
    ],
) -> None:
    await news_service.update_photos(
        news_id, data, equestrian_context=equestrian_context
    )


@router.post(
    "/news/{news_id}/photos/upload",
    response_model=PhotoBatchUploadResponseDto,
    tags=["News"],
    description="Batch upload фотографий и автоматическое присоединение к новости (Protected Write: 401 без auth, 403 не owner, 200 OK owner)",
)
async def upload_and_attach_photos_to_news(
    news_id: UUID,
    news_service: Annotated[NewsService, Depends(get_news_service)],
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
    """Batch upload+attach endpoint для новостей.

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
    data = NewsPhotosUploadDto(
        files=file_contents,
        names=names,
        descriptions=descriptions,
    )

    # Вызываем service method
    return await news_service.upload_and_attach_photos(
        news_id,
        data,
        filenames,
        user=current_user,
        equestrian_context=equestrian_context,
    )
