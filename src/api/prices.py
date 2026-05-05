from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from core.entities.base import PaginatedEntities
from core.entities.photos import Photo
from core.entities.prices import Price, PriceGroup
from core.protocols.repositories.photo_repository import PhotoRepositoryProtocol
from core.protocols.repositories.price_repository import (
    PriceGroupRepositoryProtocol,
    PriceRepositoryProtocol,
)
from core.schemas.photos import PhotoOutShortDto
from core.schemas.prices import (
    PriceCreateDto,
    PriceGroupCreateDto,
    PriceGroupOutDto,
    PriceGroupUpdateDto,
    PriceOutDto,
    PriceOutWithPageDataDto,
    PriceOutWithTablesDto,
    PricePhotosUpdateDto,
    PriceUpdateDto,
)
from core.services.prices import PriceGroupService, PriceService
from depends.repositories import (
    get_photo_repository,
    get_price_group_repository,
    get_price_repository,
)
from depends.services import get_price_group_service, get_price_service

router = APIRouter()


async def _enrich_price_with_relations(
    price: Price,
    price_repository: PriceRepositoryProtocol,
    price_group_repository: PriceGroupRepositoryProtocol,
    photo_repository: PhotoRepositoryProtocol,
    include_page_data: bool = False,
    include_tables: bool = False,
) -> PriceOutDto | PriceOutWithPageDataDto | PriceOutWithTablesDto:
    """Обогащает цену данными о связях (фотографии и группы)."""
    # Получаем связи с группами
    groups_relations = await price_repository.get_price_groups(price.id)
    group_ids = [rel.group_id for rel in groups_relations]
    groups = []
    if group_ids:
        # Получаем группы по ID
        groups_dict = await price_group_repository.get_by_ids(group_ids)
        groups = [
            {"id": group.id, "name": group.name} for group in groups_dict.values()
        ]

    # Получаем связи с фотографиями
    photos_relations = await price_repository.get_price_photos(price.id)
    photo_ids = [rel.photo_id for rel in photos_relations]
    photos_data = []
    if photo_ids:
        # Получаем фотографии по ID
        photos_dict = await photo_repository.get_by_ids(photo_ids)

        # Сортируем фотографии: сначала с is_main=True
        photos_relations_sorted = sorted(
            photos_relations, key=lambda rel: (not rel.is_main, rel.photo_id)
        )

        # Генерируем URL для фотографий
        from settings import settings

        protocol = "https" if not settings.debug else "http"

        for rel in photos_relations_sorted:
            if rel.photo_id in photos_dict:
                photo = photos_dict[rel.photo_id]
                photo_url = (
                    f"{protocol}://{settings.cms_backend_domain}/media/{photo.path}"
                )
                photo_data = PhotoOutShortDto(
                    id=photo.id, is_main=rel.is_main, url=photo_url
                )
                photos_data.append(photo_data)

    # Формируем базовый DTO
    base_data = {
        "id": price.id,
        "name": price.name,
        "slug": price.slug,
        "description": price.description,
        "photos": photos_data,
        "groups": groups,
        "created_at": price.created_at,
        "updated_at": price.updated_at,
    }

    if include_tables:
        return PriceOutWithTablesDto(
            **base_data,
            page_data=price.page_data or "<div></div>",
            price_tables=price.price_tables or [],
        )
    elif include_page_data:
        return PriceOutWithPageDataDto(
            **base_data,
            page_data=price.page_data or "<div></div>",
        )
    else:
        return PriceOutDto(**base_data)


# ==================== PriceGroup API ====================


@router.get(
    "/prices/groups",
    response_model=PaginatedEntities[PriceGroupOutDto],
    tags=["Price Group"],
    description="Получить список групп цен с фильтрацией и сортировкой",
)
async def get_price_groups(
    price_group_service: Annotated[PriceGroupService, Depends(get_price_group_service)],
    name: str | None = Query(None, description="Фильтр по названию (вхождение)"),
    description: str | None = Query(None, description="Фильтр по описанию (вхождение)"),
    sort: list[Literal["name", "-name"]] | None = Query(None, description="Сортировка"),
    limit: int | None = Query(None, description="Лимит"),
    offset: int | None = Query(None, description="Смещение"),
) -> PaginatedEntities[PriceGroupOutDto]:
    entities, total = await price_group_service.get_filtered(
        name=name,
        description=description,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    return PaginatedEntities(
        items=[PriceGroupOutDto.model_validate(entity) for entity in entities],
        total=total,
    )


@router.get(
    "/prices/groups/{id}",
    response_model=PriceGroupOutDto,
    tags=["Price Group"],
    description="Получить группу цен по UUID",
)
async def get_price_group(
    id: UUID,
    price_group_service: Annotated[PriceGroupService, Depends(get_price_group_service)],
) -> PriceGroupOutDto:
    price_group = await price_group_service.get_by_id(id)
    if price_group is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Группа не найдена")

    return PriceGroupOutDto.model_validate(price_group)


@router.post(
    "/prices/groups",
    response_model=PriceGroupOutDto,
    tags=["Price Group"],
    description="Создать новую группу цен",
)
async def create_price_group(
    data: PriceGroupCreateDto,
    price_group_service: Annotated[PriceGroupService, Depends(get_price_group_service)],
) -> PriceGroupOutDto:
    price_group = await price_group_service.create(data)
    return PriceGroupOutDto.model_validate(price_group)


@router.patch(
    "/prices/groups/{id}",
    response_model=PriceGroupOutDto,
    tags=["Price Group"],
    description="Обновить группу цен",
)
async def update_price_group(
    id: UUID,
    data: PriceGroupUpdateDto,
    price_group_service: Annotated[PriceGroupService, Depends(get_price_group_service)],
) -> PriceGroupOutDto:
    price_group = await price_group_service.update(id, data)
    return PriceGroupOutDto.model_validate(price_group)


@router.delete(
    "/prices/groups/{id}",
    status_code=204,
    tags=["Price Group"],
    description="Удалить группу цен",
)
async def delete_price_group(
    id: UUID,
    price_group_service: Annotated[PriceGroupService, Depends(get_price_group_service)],
) -> None:
    await price_group_service.delete(id)


# ==================== Price API ====================


@router.get(
    "/prices",
    response_model=PaginatedEntities[PriceOutWithTablesDto],
    tags=["Price"],
    description="Получить список цен с фильтрацией и сортировкой",
)
async def get_prices(
    price_service: Annotated[PriceService, Depends(get_price_service)],
    price_repository: Annotated[PriceRepositoryProtocol, Depends(get_price_repository)],
    price_group_repository: Annotated[
        PriceGroupRepositoryProtocol, Depends(get_price_group_repository)
    ],
    photo_repository: Annotated[PhotoRepositoryProtocol, Depends(get_photo_repository)],
    name: str | list[str] | None = Query(
        None, description="Фильтр по названию (вхождение или список)"
    ),
    description: str | None = Query(None, description="Фильтр по описанию (вхождение)"),
    groups: str | list[str] | None = Query(
        None, description="Фильтр по группам (полное совпадение)"
    ),
    sort: list[Literal["name", "-name"]] | None = Query(None, description="Сортировка"),
    limit: int | None = Query(None, description="Лимит"),
    offset: int | None = Query(None, description="Смещение"),
) -> PaginatedEntities[PriceOutWithTablesDto]:
    # Преобразуем name и groups в список, если это строка
    name_list = name if isinstance(name, list) else [name] if name else None
    groups_list = groups if isinstance(groups, list) else [groups] if groups else None

    entities, total = await price_service.get_filtered(
        name=name_list if name_list else None,
        description=description,
        groups=groups_list if groups_list else None,
        sort=sort,
        limit=limit,
        offset=offset,
    )

    # Обогащаем каждую цену данными о связях
    enriched_items = []
    for entity in entities:
        enriched = await _enrich_price_with_relations(
            entity,
            price_repository,
            price_group_repository,
            photo_repository,
            include_tables=True,
        )
        enriched_items.append(enriched)

    return PaginatedEntities(items=enriched_items, total=total)


@router.get(
    "/prices/{slug_or_id}",
    response_model=PriceOutWithTablesDto,
    tags=["Price"],
    description="Получить цену по slug или UUID",
)
async def get_price(
    slug_or_id: str,
    price_service: Annotated[PriceService, Depends(get_price_service)],
    price_repository: Annotated[PriceRepositoryProtocol, Depends(get_price_repository)],
    price_group_repository: Annotated[
        PriceGroupRepositoryProtocol, Depends(get_price_group_repository)
    ],
    photo_repository: Annotated[PhotoRepositoryProtocol, Depends(get_photo_repository)],
    page_data: bool = Query(False, description="Включить page_data в ответ"),
) -> PriceOutWithTablesDto:
    price = await price_service.get_by_slug_or_id(slug_or_id)
    if price is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Цена не найдена")

    return await _enrich_price_with_relations(
        price,
        price_repository,
        price_group_repository,
        photo_repository,
        include_page_data=page_data,
        include_tables=True,
    )


@router.post(
    "/prices",
    response_model=PriceOutDto,
    tags=["Price"],
    description="Создать новую цену",
)
async def create_price(
    data: PriceCreateDto,
    price_service: Annotated[PriceService, Depends(get_price_service)],
    price_repository: Annotated[PriceRepositoryProtocol, Depends(get_price_repository)],
    price_group_repository: Annotated[
        PriceGroupRepositoryProtocol, Depends(get_price_group_repository)
    ],
    photo_repository: Annotated[PhotoRepositoryProtocol, Depends(get_photo_repository)],
) -> PriceOutDto:
    price = await price_service.create(data)
    return await _enrich_price_with_relations(
        price, price_repository, price_group_repository, photo_repository
    )


@router.patch(
    "/prices/{slug_or_id}",
    response_model=PriceOutDto,
    tags=["Price"],
    description="Обновить цену",
)
async def update_price(
    slug_or_id: str,
    data: PriceUpdateDto,
    price_service: Annotated[PriceService, Depends(get_price_service)],
    price_repository: Annotated[PriceRepositoryProtocol, Depends(get_price_repository)],
    price_group_repository: Annotated[
        PriceGroupRepositoryProtocol, Depends(get_price_group_repository)
    ],
    photo_repository: Annotated[PhotoRepositoryProtocol, Depends(get_photo_repository)],
) -> PriceOutDto:
    price = await price_service.update(slug_or_id, data)
    return await _enrich_price_with_relations(
        price, price_repository, price_group_repository, photo_repository
    )


@router.delete(
    "/prices/{slug_or_id}",
    status_code=204,
    tags=["Price"],
    description="Удалить цену",
)
async def delete_price(
    slug_or_id: str,
    price_service: Annotated[PriceService, Depends(get_price_service)],
) -> None:
    await price_service.delete(slug_or_id)


@router.post(
    "/prices/{slug_or_id}/photos",
    status_code=204,
    tags=["Price"],
    description="Обновить фотографии цены",
)
async def update_price_photos(
    slug_or_id: str,
    data: PricePhotosUpdateDto,
    price_service: Annotated[PriceService, Depends(get_price_service)],
) -> None:
    await price_service.update_price_photos(slug_or_id, data)
