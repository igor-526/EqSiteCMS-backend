import logging
from typing import Annotated, NoReturn
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException

from clients.email_service.schemas import (
    EmailConfirmRequest,
    EmailCreateRequest,
    EmailSendConfirmationRequest,
    EmailUpdateRequest,
)
from core.exceptions.base import ClientError
from core.schemas.users import UserOutDto
from core.services.email_proxy import EmailProxyService
from depends.services import get_current_user, get_email_proxy_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/emails", tags=["Emails"])


def _raise_downstream_error(exc: httpx.HTTPStatusError) -> NoReturn:
    try:
        payload = exc.response.json()
        detail = (
            payload.get("detail", str(exc)) if isinstance(payload, dict) else str(exc)
        )
    except ValueError:
        detail = "Email service returned an invalid response"
    raise HTTPException(status_code=exc.response.status_code, detail=detail) from exc


@router.post("", response_model=dict, status_code=201)
async def create_email(
    body: EmailCreateRequest,
    actor: Annotated[UserOutDto, Depends(get_current_user)],
    service: Annotated[EmailProxyService, Depends(get_email_proxy_service)],
) -> dict:
    try:
        return await service.create(user_id=body.user_id, email=body.email, actor=actor)
    except httpx.HTTPStatusError as exc:
        _raise_downstream_error(exc)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502, detail="Email service unavailable"
        ) from exc


@router.patch("", response_model=dict)
async def update_email(
    body: EmailUpdateRequest,
    actor: Annotated[UserOutDto, Depends(get_current_user)],
    service: Annotated[EmailProxyService, Depends(get_email_proxy_service)],
) -> dict:
    try:
        return await service.update(user_id=body.user_id, email=body.email, actor=actor)
    except httpx.HTTPStatusError as exc:
        _raise_downstream_error(exc)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502, detail="Email service unavailable"
        ) from exc


@router.delete("/{user_id}", status_code=204)
async def delete_email(
    user_id: str,
    actor: Annotated[UserOutDto, Depends(get_current_user)],
    service: Annotated[EmailProxyService, Depends(get_email_proxy_service)],
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
        raise HTTPException(
            status_code=502, detail="Email service unavailable"
        ) from exc


@router.patch("/confirm", response_model=dict)
async def confirm_email(
    body: EmailConfirmRequest,
    service: Annotated[EmailProxyService, Depends(get_email_proxy_service)],
) -> dict:
    try:
        return await service.confirm(code=body.code)
    except httpx.HTTPStatusError as exc:
        _raise_downstream_error(exc)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502, detail="Email service unavailable"
        ) from exc


@router.post("/send-confirmation", status_code=202)
async def send_confirmation(
    body: EmailSendConfirmationRequest,
    service: Annotated[EmailProxyService, Depends(get_email_proxy_service)],
) -> dict:
    try:
        return await service.send_confirmation(user_id=body.user_id)
    except httpx.HTTPStatusError as exc:
        _raise_downstream_error(exc)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502, detail="Email service unavailable"
        ) from exc
