import logging
from uuid import UUID

import httpx
from pydantic import TypeAdapter

from clients.vk_service.schemas import (
    VkBindingResponse,
    VkBotInfoResponse,
    VkIssueConfirmationResponse,
)
from settings import settings

logger = logging.getLogger(__name__)


class VkServiceClient:
    """HTTP-клиент приватного vk-service.

    Peer-service credential не передаётся: сервис доступен только внутри
    `eqsitecms_network`, а owner-проверку выполняет этот backend.
    """

    def __init__(self, *, base_url: str | None = None) -> None:
        self._base_url = (base_url or settings.vk_service_url).rstrip("/")

    async def get_binding(self, *, user_id: UUID) -> VkBindingResponse | None:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._base_url}/vks", params={"user_ids": str(user_id)}
            )
            resp.raise_for_status()
            bindings = TypeAdapter(list[VkBindingResponse]).validate_python(resp.json())
            if not bindings:
                return None
            if len(bindings) != 1 or bindings[0].user_id != user_id:
                raise ValueError("VK service returned an ambiguous owner response")
            return bindings[0]

    async def get_bot_info(self) -> VkBotInfoResponse:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self._base_url}/vks/bot-info")
            resp.raise_for_status()
            return VkBotInfoResponse.model_validate(resp.json())

    async def issue_confirmation(self, *, user_id: UUID) -> VkIssueConfirmationResponse:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/vks/issue-confirmation",
                json={"user_id": str(user_id)},
            )
            resp.raise_for_status()
            return VkIssueConfirmationResponse.model_validate(resp.json())

    async def delete_binding(self, *, user_id: UUID) -> None:
        async with httpx.AsyncClient() as client:
            resp = await client.delete(f"{self._base_url}/vks/{user_id}")
            resp.raise_for_status()
