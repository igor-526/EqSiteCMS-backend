from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from core.entities.base import PaginatedEntities
from core.schemas.site_settings import (
    SiteSettingCreateDto,
    SiteSettingOutDto,
    SiteSettingSimpleOutDto,
    SiteSettingUpdateDto,
)
from core.services.site_settings import SiteSettingsService
from depends.services import get_site_settings_service

router = APIRouter()


@router.get(
    "/site_settings",
    tags=["Site Settings"],
    description="Получить список настроек с фильтрацией и сортировкой",
)
async def get_site_settings(
    site_settings_service: Annotated[
        SiteSettingsService, Depends(get_site_settings_service)
    ],
    key: list[str] | None = Query(
        None, description="Фильтр по ключам (множественная фильтрация)"
    ),
    name: str | None = Query(None, description="Фильтр по названию (вхождение)"),
    value: str | None = Query(None, description="Фильтр по значению (вхождение)"),
    description: str | None = Query(None, description="Фильтр по описанию (вхождение)"),
    type: (
        list[
            Literal[
                "string",
                "number",
                "float",
                "boolean",
                "object",
                "date",
                "time",
                "datetime",
            ]
        ]
        | None
    ) = Query(None, description="Фильтр по типу (множественная фильтрация)"),
    sort: list[Literal["key", "name", "type", "-key", "-name", "-type"]] | None = Query(
        None, description="Сортировка"
    ),
    limit: int | None = Query(None, description="Лимит"),
    offset: int | None = Query(None, description="Смещение"),
    full: bool = Query(
        False,
        description="Полный список с пагинацией (по умолчанию только key, value, type)",
    ),
):
    entities, total = await site_settings_service.get_filtered(
        key=key,
        name=name,
        value=value,
        description=description,
        type=type,
        sort=sort,
        limit=limit if full else None,  # Без full=true игнорируем пагинацию
        offset=offset if full else None,
    )

    if not full:
        # Без full=true отдаём только key, value, type без пагинации
        return [SiteSettingSimpleOutDto.model_validate(entity) for entity in entities]

    # С full=true отдаём полный список с пагинацией
    return PaginatedEntities(
        items=[SiteSettingOutDto.model_validate(entity) for entity in entities],
        total=total,
    )


@router.get(
    "/site_settings/{id}",
    response_model=SiteSettingOutDto,
    tags=["Site Settings"],
    description="Получить настройку по UUID",
)
async def get_site_setting(
    id: UUID,
    site_settings_service: Annotated[
        SiteSettingsService, Depends(get_site_settings_service)
    ],
) -> SiteSettingOutDto:
    site_setting = await site_settings_service.get_by_id(id)
    if site_setting is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Настройка не найдена")

    return SiteSettingOutDto.model_validate(site_setting)


@router.post(
    "/site_settings",
    response_model=SiteSettingOutDto,
    tags=["Site Settings"],
    description="Создать новую настройку",
)
async def create_site_setting(
    data: SiteSettingCreateDto,
    site_settings_service: Annotated[
        SiteSettingsService, Depends(get_site_settings_service)
    ],
) -> SiteSettingOutDto:
    site_setting = await site_settings_service.create(data)
    return SiteSettingOutDto.model_validate(site_setting)


@router.patch(
    "/site_settings/{id}",
    response_model=SiteSettingOutDto,
    tags=["Site Settings"],
    description="Обновить настройку",
)
async def update_site_setting(
    id: UUID,
    data: SiteSettingUpdateDto,
    site_settings_service: Annotated[
        SiteSettingsService, Depends(get_site_settings_service)
    ],
) -> SiteSettingOutDto:
    site_setting = await site_settings_service.update(id, data)
    return SiteSettingOutDto.model_validate(site_setting)


@router.delete(
    "/site_settings/{id}",
    status_code=204,
    tags=["Site Settings"],
    description="Удалить настройку",
)
async def delete_site_setting(
    id: UUID,
    site_settings_service: Annotated[
        SiteSettingsService, Depends(get_site_settings_service)
    ],
) -> None:
    await site_settings_service.delete(id)
