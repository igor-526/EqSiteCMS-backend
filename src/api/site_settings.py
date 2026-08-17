from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from core.entities.base import PaginatedEntities
from core.entities.equestrian import EquestrianContext
from core.exceptions.auth import ForbiddenError
from core.schemas.site_settings import (
    SiteSettingCreateDto,
    SiteSettingOutDto,
    SiteSettingSimpleOutDto,
    SiteSettingUpdateDto,
)
from core.schemas.users import UserOutDto
from core.services.site_settings import SiteSettingsService
from depends.services import (
    get_current_user,
    get_protected_equestrian_context,
    get_read_equestrian_context,
    get_site_settings_service,
)

router = APIRouter()
SITE_SETTINGS_WRITE_SCOPES = frozenset({"SUPERUSER", "ADMIN", "DEVELOPER"})


async def require_site_settings_write_scope(
    current_user: Annotated[UserOutDto, Depends(get_current_user)],
) -> UserOutDto:
    if not any(
        scope.scope_name in SITE_SETTINGS_WRITE_SCOPES for scope in current_user.scopes
    ):
        raise ForbiddenError("Недостаточно прав для выполнения операции")
    return current_user


@router.get(
    "/site_settings",
    tags=["Site Settings"],
    description="Получить список настроек с фильтрацией и сортировкой",
)
async def get_site_settings(
    site_settings_service: Annotated[
        SiteSettingsService, Depends(get_site_settings_service)
    ],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_read_equestrian_context)
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
        equestrian_context=equestrian_context,
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
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_read_equestrian_context)
    ],
) -> SiteSettingOutDto:
    site_setting = await site_settings_service.get_by_id(
        id, equestrian_context=equestrian_context
    )
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
    _: Annotated[UserOutDto, Depends(require_site_settings_write_scope)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_protected_equestrian_context)
    ],
) -> SiteSettingOutDto:
    site_setting = await site_settings_service.create(
        data, equestrian_context=equestrian_context
    )
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
    _: Annotated[UserOutDto, Depends(require_site_settings_write_scope)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_protected_equestrian_context)
    ],
) -> SiteSettingOutDto:
    site_setting = await site_settings_service.update(
        id, data, equestrian_context=equestrian_context
    )
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
    _: Annotated[UserOutDto, Depends(require_site_settings_write_scope)],
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_protected_equestrian_context)
    ],
) -> None:
    await site_settings_service.delete(id, equestrian_context=equestrian_context)
