from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from core.entities.base import PaginatedEntities
from core.entities.equestrian import EquestrianContext
from core.schemas.prices import (
    PriceCreateDto,
    PriceGroupCreateDto,
    PriceGroupOutDto,
    PriceGroupReorderDto,
    PriceGroupUpdateDto,
    PriceOutDto,
    PriceOutWithTablesDto,
    PricePhotosUpdateDto,
    PriceUpdateDto,
)
from core.schemas.users import UserOutDto
from core.services.prices import PriceGroupService, PriceService
from depends.services import (
    get_current_user,
    get_price_group_service,
    get_price_service,
    get_protected_equestrian_context,
    get_read_equestrian_context,
)

router = APIRouter()


# ==================== PriceGroup API ====================


@router.get(
    "/prices/groups",
    response_model=PaginatedEntities[PriceGroupOutDto],
    tags=["Price Group"],
    description="Получить список групп цен с фильтрацией и сортировкой",
)
async def get_price_groups(
    price_group_service: Annotated[PriceGroupService, Depends(get_price_group_service)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_read_equestrian_context)
    ],
    name: str | None = Query(None, description="Фильтр по названию (вхождение)"),
    description: str | None = Query(None, description="Фильтр по описанию (вхождение)"),
    sort: list[Literal["name", "-name"]] | None = Query(None, description="Сортировка"),
    limit: int | None = Query(None, description="Лимит"),
    offset: int | None = Query(None, description="Смещение"),
) -> PaginatedEntities[PriceGroupOutDto]:
    entities, total = await price_group_service.get_filtered(
        equestrian_context=equestrian_context,
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
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_read_equestrian_context)
    ],
) -> PriceGroupOutDto:
    price_group = await price_group_service.get_by_id(
        id, equestrian_context=equestrian_context
    )
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
    _: Annotated[object, Depends(get_current_user)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_protected_equestrian_context)
    ],
) -> PriceGroupOutDto:
    price_group = await price_group_service.create(
        data, equestrian_context=equestrian_context
    )
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
    _: Annotated[object, Depends(get_current_user)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_protected_equestrian_context)
    ],
) -> PriceGroupOutDto:
    price_group = await price_group_service.update(
        id, data, equestrian_context=equestrian_context
    )
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
    _: Annotated[object, Depends(get_current_user)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_protected_equestrian_context)
    ],
) -> None:
    await price_group_service.delete(id, equestrian_context=equestrian_context)


@router.post(
    "/prices/groups/{id}/reorder",
    status_code=204,
    tags=["Price Group"],
    description="Переупорядочить услуги внутри группы (только SUPERUSER/ADMIN/DEVELOPER)",
)
async def reorder_prices_in_group(
    id: UUID,
    data: PriceGroupReorderDto,
    price_group_service: Annotated[PriceGroupService, Depends(get_price_group_service)],
    current_user: Annotated[UserOutDto, Depends(get_current_user)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_protected_equestrian_context)
    ],
) -> None:
    await price_group_service.reorder_prices_in_group(
        id, data, equestrian_context=equestrian_context, user=current_user
    )


# ==================== Price API ====================


@router.get(
    "/prices",
    response_model=PaginatedEntities[PriceOutWithTablesDto],
    tags=["Price"],
    description="Получить список цен с фильтрацией и сортировкой",
)
async def get_prices(
    price_service: Annotated[PriceService, Depends(get_price_service)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_read_equestrian_context)
    ],
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

    items, total = await price_service.get_filtered_out(
        equestrian_context=equestrian_context,
        name=name_list if name_list else None,
        description=description,
        groups=groups_list if groups_list else None,
        sort=sort,
        limit=limit,
        offset=offset,
        include_tables=True,
    )

    return PaginatedEntities(
        items=cast(list[PriceOutWithTablesDto], items),
        total=total,
    )


@router.get(
    "/prices/{slug_or_id}",
    response_model=PriceOutWithTablesDto,
    tags=["Price"],
    description="Получить цену по slug или UUID",
)
async def get_price(
    slug_or_id: str,
    price_service: Annotated[PriceService, Depends(get_price_service)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_read_equestrian_context)
    ],
    page_data: bool = Query(False, description="Включить page_data в ответ"),
) -> PriceOutWithTablesDto:
    price = await price_service.get_by_slug_or_id_out(
        slug_or_id,
        equestrian_context=equestrian_context,
        include_page_data=page_data,
        include_tables=True,
    )
    return cast(PriceOutWithTablesDto, price)


@router.post(
    "/prices",
    response_model=PriceOutDto,
    tags=["Price"],
    description="Создать новую цену",
)
async def create_price(
    data: PriceCreateDto,
    price_service: Annotated[PriceService, Depends(get_price_service)],
    _: Annotated[object, Depends(get_current_user)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_protected_equestrian_context)
    ],
) -> PriceOutDto:
    return await price_service.create_out(data, equestrian_context=equestrian_context)


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
    _: Annotated[object, Depends(get_current_user)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_protected_equestrian_context)
    ],
) -> PriceOutDto:
    return await price_service.update_out(
        slug_or_id, data, equestrian_context=equestrian_context
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
    _: Annotated[object, Depends(get_current_user)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_protected_equestrian_context)
    ],
) -> None:
    await price_service.delete(slug_or_id, equestrian_context=equestrian_context)


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
    _: Annotated[object, Depends(get_current_user)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_protected_equestrian_context)
    ],
) -> None:
    await price_service.update_price_photos(
        slug_or_id, data, equestrian_context=equestrian_context
    )
