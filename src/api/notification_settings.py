from typing import Annotated, NoReturn

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError

from clients.notification_service.schemas import (
    NotificationSettingResponse,
    NotificationSettingWrite,
)
from core.schemas.users import UserOutDto
from core.services.notification_settings import NotificationSettingsService
from depends.services import get_current_user, get_notification_settings_service

router = APIRouter(prefix="/notification-settings", tags=["Notification settings"])


def _raise_downstream_error(exc: httpx.HTTPStatusError) -> NoReturn:
    status_code = exc.response.status_code if exc.response.status_code == 404 else 502
    raise HTTPException(
        status_code=status_code,
        detail=(
            "Notification setting not found"
            if status_code == 404
            else "Notification service unavailable"
        ),
    ) from exc


@router.get("", response_model=list[NotificationSettingResponse])
async def get_notification_settings(
    actor: Annotated[UserOutDto, Depends(get_current_user)],
    service: Annotated[
        NotificationSettingsService, Depends(get_notification_settings_service)
    ],
) -> list[NotificationSettingResponse]:
    try:
        return await service.get_settings(actor=actor)
    except httpx.HTTPStatusError as exc:
        _raise_downstream_error(exc)
    except (httpx.RequestError, ValidationError, ValueError) as exc:
        raise HTTPException(
            status_code=502, detail="Notification service unavailable"
        ) from exc


@router.patch(
    "/{event_code}/{channel_code}", response_model=NotificationSettingResponse
)
async def patch_notification_setting(
    event_code: str,
    channel_code: str,
    body: NotificationSettingWrite,
    actor: Annotated[UserOutDto, Depends(get_current_user)],
    service: Annotated[
        NotificationSettingsService, Depends(get_notification_settings_service)
    ],
) -> NotificationSettingResponse:
    try:
        return await service.set_setting(
            actor=actor,
            event_code=event_code,
            channel_code=channel_code,
            enabled=body.enabled,
        )
    except httpx.HTTPStatusError as exc:
        _raise_downstream_error(exc)
    except (httpx.RequestError, ValidationError, ValueError) as exc:
        raise HTTPException(
            status_code=502, detail="Notification service unavailable"
        ) from exc
