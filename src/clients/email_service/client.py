import logging
from uuid import UUID

import httpx

from settings import settings

logger = logging.getLogger(__name__)


class EmailServiceClient:
    def __init__(self) -> None:
        self._base_url = settings.email_service_url.rstrip("/")
        self._service_key = settings.service_key

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._service_key}",
            "Content-Type": "application/json",
        }

    async def create_email(self, user_id: UUID, email: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/emails",
                json={"user_id": str(user_id), "email": email},
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    async def update_email(self, user_id: UUID, email: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.patch(
                f"{self._base_url}/emails",
                json={"user_id": str(user_id), "email": email},
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    async def delete_email(self, user_id: UUID) -> None:
        async with httpx.AsyncClient() as client:
            resp = await client.delete(
                f"{self._base_url}/emails/{user_id}",
                headers=self._headers(),
            )
            resp.raise_for_status()

    async def confirm_email(self, code: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.patch(
                f"{self._base_url}/emails/confirm",
                json={"code": code},
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    async def send_confirmation(self, user_id: UUID) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/emails/send-confirmation",
                json={"user_id": str(user_id)},
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()
