import logging
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Response
from fastapi.responses import JSONResponse

from core.exceptions.auth import InvalidCredentials
from core.schemas.auth import LoginData, RegisterData
from core.schemas.users import UserOutDto
from core.services.auth import AuthService
from depends.services import get_auth_service, get_current_user
from settings import settings

router = APIRouter()

logger = logging.getLogger(__name__)
secure_cookie = settings.debug is False


@router.post(
    "/register",
    response_model=UserOutDto,
    description=(
        "Создаёт нового пользователя и возвращает объект пользователя в формате UserOutDto. "
        "В ответе нет секретных полей (например, пароля)."
    ),
)
async def register(
    data: RegisterData,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserOutDto:
    return await auth_service.register(data=data)


@router.post(
    "/login",
    description=(
        "Аутентифицирует пользователя по предоставленным данным (LoginData). "
        "В ответе тело пустое — сервис устанавливает два HTTP-only cookie: \n"
        " - `access_token` (короткоживущий, доступен всему приложению),\n"
        " - `refresh_token` (долгоживущий, доступен только на пути /auth/refresh)."
    ),
)
async def login(
    data: LoginData,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> JSONResponse:
    try:
        tokens = await auth_service.login(data=data)
    except InvalidCredentials:
        return JSONResponse({"status": "denied"}, status_code=401)

    response = JSONResponse({"status": "ok"}, status_code=200)
    response.set_cookie(
        key="access_token",
        value=tokens.access_token,
        httponly=True,
        secure=secure_cookie,
        samesite="lax",
        max_age=settings.access_token_expires_in_minutes * 60,
        path="/",
    )

    response.set_cookie(
        key="refresh_token",
        value=tokens.refresh_token,
        httponly=True,
        secure=secure_cookie,
        samesite="lax",
        max_age=settings.refresh_token_expires_in_days * 24 * 60 * 60,
        path="/api/auth/refresh",
    )

    logger.info(f"accessToken для локальной разработки: {tokens.access_token}")
    return response


@router.post(
    "/refresh",
    description=(
        "Обновляет access и refresh токены на основании cookie `refresh_token`. "
        "Возвращает пустое тело, но устанавливает новые HTTP-only cookie: `access_token` и `refresh_token`."
    ),
)
async def refresh_access_token(
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    refresh_token: Annotated[str | None, Cookie(alias="refresh_token")] = None,
) -> JSONResponse:
    if not refresh_token:
        return JSONResponse({"status": "denied"}, status_code=401)

    try:
        tokens = await auth_service.refresh(refresh_token=refresh_token)
    except InvalidCredentials:
        return JSONResponse({"status": "denied"}, status_code=401)

    response = JSONResponse({"status": "ok"}, status_code=200)
    response.set_cookie(
        key="access_token",
        value=tokens.access_token,
        httponly=True,
        secure=secure_cookie,
        samesite="lax",
        max_age=settings.access_token_expires_in_minutes * 60,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=tokens.refresh_token,
        httponly=True,
        secure=secure_cookie,
        samesite="lax",
        max_age=settings.refresh_token_expires_in_days * 24 * 60 * 60,
        path="/api/auth/refresh",
    )
    return response


@router.get(
    "/me",
    response_model=UserOutDto,
    description="Возвращает информацию о текущем аутентифицированном пользователе, включая его группы доступа.",
)
async def get_current_user_info(
    current_user: Annotated[UserOutDto, Depends(get_current_user)],
) -> UserOutDto:
    return current_user


@router.post(
    "/logout",
    description=(
        "Выход из системы: удаляет HTTP-only cookie `access_token` и `refresh_token`. "
        "Тело ответа пустое."
    ),
)
async def logout(response: Response) -> Response:
    response.delete_cookie(
        key="access_token",
        path="/",
        httponly=True,
        secure=secure_cookie,
        samesite="lax",
    )
    response.delete_cookie(
        key="refresh_token",
        path="/api/auth/refresh",
        httponly=True,
        secure=secure_cookie,
        samesite="lax",
    )
    response.status_code = 204
    return response
