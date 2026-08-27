import logging
from typing import Annotated, NoReturn
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError

from clients.vk_service.schemas import (
    VkBindingResponse,
    VkBotInfoResponse,
    VkIssueConfirmationResponse,
)
from core.exceptions.base import ClientError
from core.schemas.users import UserOutDto
from core.services.vk_proxy import VkProxyService
from depends.services import get_current_user, get_vk_proxy_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vks", tags=["VK"])

PASSTHROUGH_STATUS_CODES = frozenset({404, 409, 503})


def _raise_downstream_error(exc: httpx.HTTPStatusError) -> NoReturn:
    """Доменные статусы пробрасываются, остальное скрывается за 502."""
    status_code = exc.response.status_code
    if status_code not in PASSTHROUGH_STATUS_CODES:
        raise HTTPException(status_code=502, detail="VK service unavailable") from exc
    try:
        payload = exc.response.json()
        detail = (
            payload.get("detail", "VK service error")
            if isinstance(payload, dict)
            else "VK service error"
        )
    except ValueError:
        detail = "VK service returned an invalid response"
    raise HTTPException(status_code=status_code, detail=detail) from exc


@router.get("/me", response_model=VkBindingResponse)
async def get_my_vk_binding(
    actor: Annotated[UserOutDto, Depends(get_current_user)],
    service: Annotated[VkProxyService, Depends(get_vk_proxy_service)],
) -> VkBindingResponse:
    try:
        return await service.get_mine(actor=actor)
    except httpx.HTTPStatusError as exc:
        _raise_downstream_error(exc)
    except (httpx.RequestError, ValidationError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="VK service unavailable") from exc


@router.get("/bot-info", response_model=VkBotInfoResponse)
async def get_vk_bot_info(
    service: Annotated[VkProxyService, Depends(get_vk_proxy_service)],
) -> VkBotInfoResponse:
    try:
        return await service.get_bot_info()
    except httpx.HTTPStatusError as exc:
        _raise_downstream_error(exc)
    except (httpx.RequestError, ValidationError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="VK service unavailable") from exc


@router.post(
    "/issue-confirmation", response_model=VkIssueConfirmationResponse, status_code=201
)
async def issue_vk_confirmation(
    actor: Annotated[UserOutDto, Depends(get_current_user)],
    service: Annotated[VkProxyService, Depends(get_vk_proxy_service)],
) -> VkIssueConfirmationResponse:
    try:
        return await service.issue_confirmation(actor=actor)
    except httpx.HTTPStatusError as exc:
        _raise_downstream_error(exc)
    except (httpx.RequestError, ValidationError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="VK service unavailable") from exc


@router.delete("/{user_id}", status_code=204)
async def delete_vk_binding(
    user_id: str,
    actor: Annotated[UserOutDto, Depends(get_current_user)],
    service: Annotated[VkProxyService, Depends(get_vk_proxy_service)],
) -> None:
    try:
        parsed_user_id = UUID(user_id)
    except ValueError as exc:
        raise ClientError("Некорректный user_id") from exc
    try:
        await service.delete(user_id=parsed_user_id, actor=actor)
    except httpx.HTTPStatusError as exc:
        _raise_downstream_error(exc)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail="VK service unavailable") from exc
