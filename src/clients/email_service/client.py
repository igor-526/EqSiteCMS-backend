import logging
from uuid import UUID

import httpx

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
            return resp.json()

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
            return resp.json()
