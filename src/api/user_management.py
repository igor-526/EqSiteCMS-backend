from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from api.depends.user_management import require_user_management
from core.schemas.users import UserOutDto
from core.schemas.user_management import (
    ChangePasswordByAdminIn,
    CreateUserIn,
    UpdateUserIn,
    UserManagementFilters,
    UserManagementOutDto,
    RoleOutDto,
)
from core.services.user_management import UserManagementService
from depends.services import get_user_management_service

router = APIRouter(prefix="/api/user-management", tags=["User Management"])


@router.get("/users", response_model=dict)
async def get_users(
    current_user: Annotated[UserOutDto, Depends(require_user_management)],
    user_management_service: Annotated[
        UserManagementService, Depends(get_user_management_service)
    ],
    username: str | None = Query(
        default=None, description="Фильтр по username (regex)"
    ),
    first_name: str | None = Query(default=None, description="Фильтр по имени (regex)"),
    last_name: str | None = Query(
        default=None, description="Фильтр по фамилии (regex)"
    ),
    middle_name: str | None = Query(
        default=None, description="Фильтр по отчеству (regex)"
    ),
    scope_ids: list[UUID] | None = Query(
        default=None, description="Фильтр по ролям (ИЛИ)"
    ),
    search: str | None = Query(default=None, description="Поиск по ФИО"),
    is_blocked: bool | None = Query(default=None, description="Фильтр по блокировке"),
    limit: int = Query(default=100, ge=1, le=5000, description="Количество элементов"),
    offset: int = Query(default=0, ge=0, description="Смещение"),
) -> dict:
    """
    Получить список пользователей с фильтрацией, пагинацией и сортировкой.

    - **username**: фильтр по username (регистронезависимый regex)
    - **first_name**: фильтр по имени (регистронезависимый regex)
    - **last_name**: фильтр по фамилии (регистронезависимый regex)
    - **middle_name**: фильтр по отчеству (регистронезависимый regex)
    - **scope_ids**: фильтр по ролям (логика ИЛИ)
    - **search**: поиск по first_name, last_name, middle_name (логика ИЛИ)
    - **is_blocked**: фильтр по статусу блокировки
    - **limit**: количество элементов (1-5000)
    - **offset**: смещение

    Сортировка: is_blocked ASC, затем last_name ASC.
    Удалённые пользователи (is_deleted=true) исключаются из выдачи.
    """
    filters = UserManagementFilters(
        username=username,
        first_name=first_name,
        last_name=last_name,
        middle_name=middle_name,
        scope_ids=scope_ids,
        search=search,
        is_blocked=is_blocked,
    )

    return await user_management_service.get_users(
        current_user=current_user,
        filters=filters,
        limit=limit,
        offset=offset,
    )


@router.get("/users/{user_id}", response_model=UserManagementOutDto)
async def get_user(
    user_id: UUID,
    current_user: Annotated[UserOutDto, Depends(require_user_management)],
    user_management_service: Annotated[
        UserManagementService, Depends(get_user_management_service)
    ],
) -> UserManagementOutDto:
    """
    Получить конкретного пользователя по ID.

    Удалённые пользователи (is_deleted=true) не возвращаются.
    """
    return await user_management_service.get_user_by_id(
        current_user=current_user,
        user_id=user_id,
    )


@router.post("/users", response_model=UserManagementOutDto, status_code=201)
async def create_user(
    data: CreateUserIn,
    current_user: Annotated[UserOutDto, Depends(require_user_management)],
    user_management_service: Annotated[
        UserManagementService, Depends(get_user_management_service)
    ],
) -> UserManagementOutDto:
    """
    Создать нового пользователя.

    - **equestrian_id**: идентификатор конюшни (обязательно)
    - **username**: имя пользователя (3-63 символа, уникальное)
    - **password**: пароль (минимум 8 символов, хотя бы одна заглавная буква и цифра)
    - **confirm_password**: подтверждение пароля (должно совпадать)
    - **first_name**: имя (опционально)
    - **last_name**: фамилия (опционально)
    - **middle_name**: отчество (опционально)
    - **scope_ids**: список идентификаторов ролей (опционально)

    USER_MANAGER не может назначать роль SUPERUSER.
    """
    return await user_management_service.create_user(
        current_user=current_user,
        data=data,
    )


@router.patch("/users/{user_id}", response_model=UserManagementOutDto)
async def update_user(
    user_id: UUID,
    data: UpdateUserIn,
    current_user: Annotated[UserOutDto, Depends(require_user_management)],
    user_management_service: Annotated[
        UserManagementService, Depends(get_user_management_service)
    ],
) -> UserManagementOutDto:
    """
    Обновить пользователя.

    - **username**: имя пользователя (3-63 символа, уникальное)
    - **first_name**: имя
    - **last_name**: фамилия
    - **middle_name**: отчество
    - **scope_ids**: список идентификаторов ролей

    Бизнес-правила:
    - UM не может редактировать SUPERUSER
    - UM не может снять с себя роль USER_MANAGER
    - SU не может снять с себя роль SUPERUSER
    - UM не может назначать роль SUPERUSER
    """
    return await user_management_service.update_user(
        current_user=current_user,
        user_id=user_id,
        data=data,
    )


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: UUID,
    current_user: Annotated[UserOutDto, Depends(require_user_management)],
    user_management_service: Annotated[
        UserManagementService, Depends(get_user_management_service)
    ],
) -> None:
    """
    Удалить пользователя (soft-delete).

    Пользователь помечается как is_deleted=true, deleted_at=now().
    Физически из БД не удаляется.

    Бизнес-правила:
    - Нельзя удалить самого себя
    - UM не может удалить SUPERUSER
    """
    await user_management_service.soft_delete_user(
        current_user=current_user,
        user_id=user_id,
    )


@router.patch("/users/{user_id}/block", response_model=dict)
async def block_user(
    user_id: UUID,
    current_user: Annotated[UserOutDto, Depends(require_user_management)],
    user_management_service: Annotated[
        UserManagementService, Depends(get_user_management_service)
    ],
) -> dict:
    """
    Заблокировать пользователя.

    Устанавливает is_blocked=true.

    Бизнес-правила:
    - Нельзя заблокировать самого себя
    - UM не может заблокировать SUPERUSER
    """
    return await user_management_service.block_user(
        current_user=current_user,
        user_id=user_id,
    )


@router.patch("/users/{user_id}/unblock", response_model=dict)
async def unblock_user(
    user_id: UUID,
    current_user: Annotated[UserOutDto, Depends(require_user_management)],
    user_management_service: Annotated[
        UserManagementService, Depends(get_user_management_service)
    ],
) -> dict:
    """
    Разблокировать пользователя.

    Устанавливает is_blocked=false.

    Бизнес-правила:
    - UM не может разблокировать SUPERUSER
    """
    return await user_management_service.unblock_user(
        current_user=current_user,
        user_id=user_id,
    )


@router.patch("/users/{user_id}/password", status_code=204)
async def change_password(
    user_id: UUID,
    data: ChangePasswordByAdminIn,
    current_user: Annotated[UserOutDto, Depends(require_user_management)],
    user_management_service: Annotated[
        UserManagementService, Depends(get_user_management_service)
    ],
) -> None:
    """
    Сменить пароль пользователя (администратором).

    - **new_password**: новый пароль (минимум 8 символов, хотя бы одна заглавная буква и цифра)
    - **confirm_password**: подтверждение пароля (должно совпадать)

    Бизнес-правила:
    - UM не может менять пароль SUPERUSER
    """
    await user_management_service.change_password(
        current_user=current_user,
        user_id=user_id,
        data=data,
    )


@router.get("/roles", response_model=list[RoleOutDto])
async def get_roles(
    current_user: Annotated[UserOutDto, Depends(require_user_management)],
    user_management_service: Annotated[
        UserManagementService, Depends(get_user_management_service)
    ],
    scope_name: str | None = Query(
        default=None, description="Фильтр по имени роли (regex)"
    ),
) -> list[RoleOutDto]:
    """
    Получить все доступные роли.

    - **scope_name**: фильтр по имени роли (регистронезависимый regex)
    """
    return await user_management_service.get_all_roles(
        current_user=current_user,
        scope_name=scope_name,
    )
