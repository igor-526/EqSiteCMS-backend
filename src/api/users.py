from typing import Annotated

from fastapi import APIRouter, Depends

from core.schemas.users import (
    ChangePasswordIn,
    UpdateProfileIn,
    UserOutDto,
    UserProfileDto,
)
from core.services.users import UserService
from depends.services import get_current_user, get_user_service

router = APIRouter()


@router.get("/me", response_model=UserProfileDto)
async def get_my_profile(
    current_user: Annotated[UserOutDto, Depends(get_current_user)],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> UserProfileDto:
    return await user_service.get_my_profile(current_user)


@router.patch("/me", response_model=UserProfileDto)
async def update_my_profile(
    data: UpdateProfileIn,
    current_user: Annotated[UserOutDto, Depends(get_current_user)],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> UserProfileDto:
    return await user_service.update_my_profile(current_user, data)


@router.patch("/me/password", status_code=204)
async def change_my_password(
    data: ChangePasswordIn,
    current_user: Annotated[UserOutDto, Depends(get_current_user)],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> None:
    return await user_service.change_my_password(current_user, data)
