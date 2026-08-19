from typing import Protocol
from uuid import UUID

from clients.notification_service.schemas import NotificationSettingResponse


class NotificationServiceClientProtocol(Protocol):
    async def get_settings(
        self, *, user_id: UUID
    ) -> list[NotificationSettingResponse]: ...

    async def set_setting(
        self,
        *,
        user_id: UUID,
        event_code: str,
        channel_code: str,
        enabled: bool,
    ) -> NotificationSettingResponse: ...
