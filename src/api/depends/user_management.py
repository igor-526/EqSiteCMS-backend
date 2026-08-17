from typing import Annotated

from fastapi import Depends

from core.exceptions.auth import ForbiddenError
from core.schemas.users import UserOutDto
from depends.services import get_current_user

USER_MANAGER_SCOPE = "USER_MANAGER"
SUPERUSER_SCOPE = "SUPERUSER"


async def require_user_management(
    current_user: Annotated[UserOutDto, Depends(get_current_user)],
) -> UserOutDto:
    """
    Dependency для проверки наличия роли USER_MANAGER или SUPERUSER.

    Проверяет:
    1. Наличие одной из требуемых ролей
    2. Пользователь не заблокирован
    """
    # Проверяем, что пользователь не заблокирован
    if current_user.is_blocked:
        raise ForbiddenError("Ваш аккаунт заблокирован")

    # Проверяем наличие требуемых ролей
    scope_names = [scope.scope_name for scope in current_user.scopes]

    if USER_MANAGER_SCOPE not in scope_names and SUPERUSER_SCOPE not in scope_names:
        raise ForbiddenError(
            "Доступ запрещен. Требуется роль USER_MANAGER или SUPERUSER"
        )

    return current_user
