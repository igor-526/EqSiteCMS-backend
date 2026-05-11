from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from core.entities.base import PaginatedEntities
from core.entities.equestrian import EquestrianContext
from core.entities.news import NewsStatus
from core.schemas.news import (
    NewsCreateDto,
    NewsOutDto,
    NewsPhotosUpdateDto,
    NewsPublicOutDto,
    NewsUpdateDto,
)
from core.schemas.users import UserOutDto
from core.services.news import NewsService
from depends.services import (
    get_current_user,
    get_news_service,
    get_protected_equestrian_context,
    get_public_equestrian_context,
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
        EquestrianContext, Depends(get_public_equestrian_context)
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
    "/news/{news_id}",
    response_model=NewsPublicOutDto,
    tags=["News"],
    description="Деталь публичной новости (только опубликованные, не удалённые)",
)
async def get_news_detail(
    news_id: UUID,
    news_service: Annotated[NewsService, Depends(get_news_service)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_public_equestrian_context)
    ],
) -> NewsPublicOutDto:
    news_item = await news_service.get_public_detail(
        news_id, equestrian_context=equestrian_context
    )
    return await news_service.build_public_out_dto(
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
