from typing import Protocol
from uuid import UUID

from clients.vk_service.schemas import (
    VkBindingResponse,
    VkBotInfoResponse,
    VkIssueConfirmationResponse,
)


class VkServiceClientProtocol(Protocol):
    async def get_binding(self, *, user_id: UUID) -> VkBindingResponse | None: ...

    async def get_bot_info(self) -> VkBotInfoResponse: ...

    async def issue_confirmation(
        self, *, user_id: UUID
    ) -> VkIssueConfirmationResponse: ...

    async def delete_binding(self, *, user_id: UUID) -> None: ...
