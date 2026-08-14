import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException
from httpx import HTTPStatusError

from clients.email_service.client import EmailServiceClient
from clients.email_service.schemas import (
    EmailConfirmRequest,
    EmailCreateRequest,
    EmailSendConfirmationRequest,
    EmailUpdateRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/emails", tags=["Emails"])

email_service_client = EmailServiceClient()


@router.post(
    "", response_model=dict, status_code=201, description="Создать email пользователя"
)
async def create_email(body: EmailCreateRequest) -> dict:
    try:
        return await email_service_client.create_email(
            user_id=body.user_id, email=body.email
        )
    except HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=e.response.json().get("detail", str(e)),
        )


@router.patch("", response_model=dict, description="Обновить email пользователя")
async def update_email(body: EmailUpdateRequest) -> dict:
    try:
        return await email_service_client.update_email(
            user_id=body.user_id, email=body.email
        )
    except HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=e.response.json().get("detail", str(e)),
        )


@router.delete(
    "/{user_id}", status_code=204, description="Мягкое удаление email пользователя"
)
async def delete_email(user_id: UUID) -> None:
    try:
        await email_service_client.delete_email(user_id=user_id)
    except HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=e.response.json().get("detail", str(e)),
        )


@router.patch("/confirm", response_model=dict, description="Подтвердить email по коду")
async def confirm_email(body: EmailConfirmRequest) -> dict:
    try:
        return await email_service_client.confirm_email(code=body.code)
    except HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=e.response.json().get("detail", str(e)),
        )


@router.post(
    "/send-confirmation", status_code=202, description="Отправить письмо подтверждения"
)
async def send_confirmation(body: EmailSendConfirmationRequest) -> dict:
    try:
        return await email_service_client.send_confirmation(user_id=body.user_id)
    except HTTPStatusError as e:
        raise HTTPException(
            status_code=e.response.status_code,
            detail=e.response.json().get("detail", str(e)),
        )
