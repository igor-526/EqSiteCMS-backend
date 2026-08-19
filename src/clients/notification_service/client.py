from uuid import UUID

import httpx
from pydantic import TypeAdapter

from clients.notification_service.schemas import NotificationSettingResponse
from settings import settings


class NotificationServiceClient:
    def __init__(self, *, base_url: str | None = None) -> None:
        self._base_url = (base_url or settings.notification_service_url).rstrip("/")

    async def get_settings(self, *, user_id: UUID) -> list[NotificationSettingResponse]:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self._base_url}/internal/notification-settings/{user_id}"
            )
            response.raise_for_status()
            return TypeAdapter(list[NotificationSettingResponse]).validate_python(
                response.json()
            )

    async def set_setting(
        self,
        *,
        user_id: UUID,
        event_code: str,
        channel_code: str,
        enabled: bool,
    ) -> NotificationSettingResponse:
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{self._base_url}/internal/notification-settings/"
                f"{user_id}/{event_code}/{channel_code}",
                json={"enabled": enabled},
            )
            response.raise_for_status()
            return NotificationSettingResponse.model_validate(response.json())
