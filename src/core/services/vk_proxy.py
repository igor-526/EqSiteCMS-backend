from uuid import UUID

from clients.vk_service.schemas import (
    VkBindingResponse,
    VkBotInfoResponse,
    VkIssueConfirmationResponse,
)
from core.exceptions.auth import ForbiddenError
from core.exceptions.base import NotFoundError
from core.protocols.vk_service import VkServiceClientProtocol
from core.schemas.users import UserOutDto


class VkProxyService:
    """Owner-only проксирование приватного vk-service."""

    def __init__(self, client: VkServiceClientProtocol) -> None:
        self._client = client

    @staticmethod
    def _require_owner(*, user_id: UUID, actor: UserOutDto) -> None:
        if actor.id != user_id:
            raise ForbiddenError("Управлять привязкой VK может только её владелец")

    async def get_mine(self, *, actor: UserOutDto) -> VkBindingResponse:
        binding = await self._client.get_binding(user_id=actor.id)
        if binding is None:
            raise NotFoundError("Привязка VK не найдена")
        return binding

    async def get_bot_info(self) -> VkBotInfoResponse:
        return await self._client.get_bot_info()

    async def issue_confirmation(
        self, *, actor: UserOutDto
    ) -> VkIssueConfirmationResponse:
        return await self._client.issue_confirmation(user_id=actor.id)

    async def delete(self, *, user_id: UUID, actor: UserOutDto) -> None:
        self._require_owner(user_id=user_id, actor=actor)
        await self._client.delete_binding(user_id=user_id)
