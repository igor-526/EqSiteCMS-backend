import logging
from uuid import UUID

import httpx
from pydantic import TypeAdapter

from clients.email_service.schemas import EmailResponse
from core.exceptions.email_proxy import EmailServiceResponseError
from settings import settings

logger = logging.getLogger(__name__)


class EmailServiceClient:
    def __init__(self, *, base_url: str | None = None) -> None:
        self._base_url = (base_url or settings.email_service_url).rstrip("/")

    async def create_email(self, *, user_id: UUID, email: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/emails",
                json={"user_id": str(user_id), "email": email},
            )
            resp.raise_for_status()
            try:
                result = EmailResponse.model_validate(resp.json())
                if (
                    result.user_id != user_id
                    or result.email.strip().casefold() != email.strip().casefold()
                ):
                    raise EmailServiceResponseError()
                return result.model_dump(mode="json")
            except ValueError as exc:
                raise EmailServiceResponseError() from exc

    async def get_email(self, *, user_id: UUID) -> EmailResponse | None:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._base_url}/emails", params={"user_ids": str(user_id)}
            )
            resp.raise_for_status()
            emails = TypeAdapter(list[EmailResponse]).validate_python(resp.json())
            if not emails:
                return None
            if len(emails) != 1 or emails[0].user_id != user_id:
                raise ValueError("Email service returned an ambiguous owner response")
            return emails[0]

    async def update_email(self, *, user_id: UUID, email: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.patch(
                f"{self._base_url}/emails",
                json={"user_id": str(user_id), "email": email},
            )
            resp.raise_for_status()
            return resp.json()

    async def delete_email(self, *, user_id: UUID) -> None:
        async with httpx.AsyncClient() as client:
            resp = await client.delete(
                f"{self._base_url}/emails/{user_id}",
            )
            resp.raise_for_status()

    async def confirm_email(self, *, code: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.patch(
                f"{self._base_url}/emails/confirm",
                json={"code": code},
            )
            resp.raise_for_status()
            return resp.json()

    async def send_confirmation(self, *, user_id: UUID) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/emails/send-confirmation",
                json={"user_id": str(user_id)},
            )
            resp.raise_for_status()
            if resp.status_code != 202:
                raise EmailServiceResponseError()
            try:
                payload = resp.json()
            except ValueError as exc:
                raise EmailServiceResponseError() from exc
            if not isinstance(payload, dict):
                raise EmailServiceResponseError()
            return payload
