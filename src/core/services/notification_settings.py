from clients.notification_service.schemas import NotificationSettingResponse
from core.exceptions.auth import ForbiddenError
from core.exceptions.base import NotFoundError
from core.policies.notification_settings import (
    KNOWN_NOTIFICATION_CHANNELS,
    KNOWN_NOTIFICATION_EVENTS,
    NOTIFICATION_ELIGIBILITY,
    eligible_notification_keys,
)
from core.protocols.notification_service import NotificationServiceClientProtocol
from core.schemas.users import UserOutDto


class NotificationSettingsService:
    def __init__(self, client: NotificationServiceClientProtocol) -> None:
        self._client = client

    async def get_settings(
        self, *, actor: UserOutDto
    ) -> list[NotificationSettingResponse]:
        eligible = eligible_notification_keys(actor)
        if not eligible:
            return []
        settings = await self._client.get_settings(user_id=actor.id)
        if any(
            item.event_code not in KNOWN_NOTIFICATION_EVENTS
            or item.channel_code not in KNOWN_NOTIFICATION_CHANNELS
            for item in settings
        ):
            raise ValueError("Unknown notification setting returned by downstream")
        return [
            item
            for item in settings
            if (item.event_code, item.channel_code) in eligible
        ]

    async def set_setting(
        self,
        *,
        actor: UserOutDto,
        event_code: str,
        channel_code: str,
        enabled: bool,
    ) -> NotificationSettingResponse:
        key = (event_code, channel_code)
        if key not in NOTIFICATION_ELIGIBILITY:
            raise NotFoundError("Notification event/channel combination not found")
        if key not in eligible_notification_keys(actor):
            raise ForbiddenError("Недостаточно прав для настройки уведомления")
        return await self._client.set_setting(
            user_id=actor.id,
            event_code=event_code,
            channel_code=channel_code,
            enabled=enabled,
        )
