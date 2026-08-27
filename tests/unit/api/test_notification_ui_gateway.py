from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from clients.email_service.schemas import EmailResponse
from clients.notification_service.schemas import NotificationSettingResponse
from core.entities.user import UserScope
from core.exceptions.auth import InvalidCredentials
from core.schemas.users import UserOutDto
from core.services.notification_settings import NotificationSettingsService
from depends.services import (
    get_current_user,
    get_email_proxy_service,
    get_notification_settings_service,
)
from main import app


def make_actor(*scopes: str, user_id: UUID | None = None) -> UserOutDto:
    return UserOutDto(
        id=user_id or uuid4(),
        equestrian_id=uuid4(),
        username="notification-owner",
        created_at=datetime.now(UTC),
        scopes=[
            UserScope(scope_name=scope, scope_description=scope) for scope in scopes
        ],
    )


def setting(
    actor: UserOutDto,
    *,
    enabled: bool = False,
    event_code: str = "callback",
    channel_code: str = "email",
) -> NotificationSettingResponse:
    return NotificationSettingResponse(
        user_id=actor.id,
        event_code=event_code,
        event_name="Обратный звонок",
        event_description="Новая заявка на обратный звонок",
        channel_code=channel_code,
        channel_name="Email",
        enabled=enabled,
    )


@pytest.fixture
def client():
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def authenticate(actor: UserOutDto) -> None:
    app.dependency_overrides[get_current_user] = lambda: actor


def deny_auth() -> None:
    async def missing_actor() -> None:
        raise InvalidCredentials("missing")

    app.dependency_overrides[get_current_user] = missing_actor


# U-01
def test_u01_anonymous_email_me_is_401_without_downstream(client: TestClient) -> None:
    service = AsyncMock()
    deny_auth()
    app.dependency_overrides[get_email_proxy_service] = lambda: service
    response = client.get("/api/emails/me")
    assert response.status_code == 401
    service.get_mine.assert_not_awaited()


# U-02
def test_u02_owner_email_is_validated_and_returned(client: TestClient) -> None:
    actor = make_actor()
    authenticate(actor)
    service = AsyncMock()
    service.get_mine.return_value = EmailResponse(
        id=uuid4(), user_id=actor.id, email="owner@example.com", approved=True
    )
    app.dependency_overrides[get_email_proxy_service] = lambda: service
    response = client.get("/api/emails/me")
    assert response.status_code == 200
    assert response.json()["user_id"] == str(actor.id)
    service.get_mine.assert_awaited_once_with(actor=actor)


# U-03
def test_u03_missing_owner_email_is_404(client: TestClient) -> None:
    actor = make_actor()
    authenticate(actor)
    service = AsyncMock()
    service.get_mine.side_effect = httpx.HTTPStatusError(
        "missing",
        request=httpx.Request("GET", "http://email/emails/id"),
        response=httpx.Response(404, json={"detail": "not found"}),
    )
    app.dependency_overrides[get_email_proxy_service] = lambda: service
    assert client.get("/api/emails/me").status_code == 404


# U-04
def test_u04_malformed_email_response_is_502(client: TestClient) -> None:
    actor = make_actor()
    authenticate(actor)
    service = AsyncMock()
    with pytest.raises(ValidationError) as error:
        EmailResponse.model_validate({"email": "broken"})
    service.get_mine.side_effect = error.value
    app.dependency_overrides[get_email_proxy_service] = lambda: service
    assert client.get("/api/emails/me").status_code == 502


# U-05
def test_u05_email_timeout_is_502(client: TestClient) -> None:
    actor = make_actor()
    authenticate(actor)
    service = AsyncMock()
    service.get_mine.side_effect = httpx.ReadTimeout(
        "timeout", request=httpx.Request("GET", "http://email/emails/id")
    )
    app.dependency_overrides[get_email_proxy_service] = lambda: service
    assert client.get("/api/emails/me").status_code == 502


def wire_settings(actor: UserOutDto, downstream: AsyncMock) -> None:
    authenticate(actor)
    app.dependency_overrides[get_notification_settings_service] = lambda: (
        NotificationSettingsService(downstream)
    )


# U-06
def test_u06_anonymous_settings_get_is_401_without_downstream(
    client: TestClient,
) -> None:
    downstream = AsyncMock()
    deny_auth()
    app.dependency_overrides[get_notification_settings_service] = lambda: (
        NotificationSettingsService(downstream)
    )
    assert client.get("/api/notification-settings").status_code == 401
    downstream.get_settings.assert_not_awaited()


# U-07
def test_u07_admin_sees_disabled_callback_email(client: TestClient) -> None:
    actor, downstream = make_actor("ADMIN"), AsyncMock()
    downstream.get_settings.return_value = [setting(actor)]
    wire_settings(actor, downstream)
    response = client.get("/api/notification-settings")
    assert response.status_code == 200
    assert response.json()[0]["enabled"] is False


# U-08
def test_u08_superuser_sees_callback_email(client: TestClient) -> None:
    actor, downstream = make_actor("SUPERUSER"), AsyncMock()
    downstream.get_settings.return_value = [setting(actor, enabled=True)]
    wire_settings(actor, downstream)
    assert (
        client.get("/api/notification-settings").json()[0]["event_code"] == "callback"
    )


@pytest.mark.parametrize("scope", ["ADMIN", "SUPERUSER"])
def test_supported_catalog_exposes_email_and_vk_but_filters_sms(
    client: TestClient, scope: str
) -> None:
    actor, downstream = make_actor(scope), AsyncMock()
    downstream.get_settings.return_value = [
        setting(actor, enabled=True),
        setting(actor, channel_code="vk"),
        setting(actor, channel_code="sms"),
    ]
    wire_settings(actor, downstream)

    response = client.get("/api/notification-settings")

    assert response.status_code == 200
    assert [(item["event_code"], item["channel_code"]) for item in response.json()] == [
        ("callback", "email"),
        ("callback", "vk"),
    ]


@pytest.mark.parametrize("scope", ["ADMIN", "SUPERUSER"])
def test_eligible_catalog_keeps_the_two_channels_independent(
    client: TestClient, scope: str
) -> None:
    actor, downstream = make_actor(scope), AsyncMock()
    downstream.get_settings.return_value = [
        setting(actor, enabled=True),
        setting(actor, channel_code="vk", enabled=False),
    ]
    wire_settings(actor, downstream)

    body = client.get("/api/notification-settings").json()

    assert {item["channel_code"]: item["enabled"] for item in body} == {
        "email": True,
        "vk": False,
    }


@pytest.mark.parametrize("scope", ["DEVELOPER", "USER_MANAGER"])
def test_ineligible_scope_never_sees_the_vk_channel(
    client: TestClient, scope: str
) -> None:
    actor, downstream = make_actor(scope), AsyncMock()
    downstream.get_settings.return_value = [
        setting(actor, enabled=True),
        setting(actor, channel_code="vk", enabled=True),
    ]
    wire_settings(actor, downstream)

    response = client.get("/api/notification-settings")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize("scope", ["ADMIN", "SUPERUSER"])
@pytest.mark.parametrize("enabled", [True, False])
def test_eligible_owner_toggles_the_vk_channel(
    client: TestClient, scope: str, enabled: bool
) -> None:
    actor, downstream = make_actor(scope), AsyncMock()
    downstream.set_setting.return_value = setting(
        actor, channel_code="vk", enabled=enabled
    )
    wire_settings(actor, downstream)

    response = client.patch(
        "/api/notification-settings/callback/vk", json={"enabled": enabled}
    )

    assert response.status_code == 200
    assert response.json()["enabled"] is enabled
    downstream.set_setting.assert_awaited_once_with(
        user_id=actor.id, event_code="callback", channel_code="vk", enabled=enabled
    )


@pytest.mark.parametrize("scope", ["DEVELOPER", "USER_MANAGER"])
def test_ineligible_scope_cannot_toggle_the_vk_channel(
    client: TestClient, scope: str
) -> None:
    actor, downstream = make_actor(scope), AsyncMock()
    wire_settings(actor, downstream)

    response = client.patch(
        "/api/notification-settings/callback/vk", json={"enabled": True}
    )

    assert response.status_code == 403
    downstream.set_setting.assert_not_awaited()


def test_anonymous_cannot_toggle_the_vk_channel(client: TestClient) -> None:
    downstream = AsyncMock()

    async def no_actor() -> None:
        raise InvalidCredentials("Отсутствуют учетные данные")

    app.dependency_overrides[get_current_user] = no_actor
    app.dependency_overrides[get_notification_settings_service] = lambda: (
        NotificationSettingsService(downstream)
    )

    response = client.patch(
        "/api/notification-settings/callback/vk", json={"enabled": True}
    )

    assert response.status_code == 401
    downstream.set_setting.assert_not_awaited()


def test_the_unmapped_sms_channel_is_still_unknown(client: TestClient) -> None:
    actor, downstream = make_actor("SUPERUSER"), AsyncMock()
    wire_settings(actor, downstream)

    response = client.patch(
        "/api/notification-settings/callback/sms", json={"enabled": True}
    )

    assert response.status_code == 404
    downstream.set_setting.assert_not_awaited()


@pytest.mark.parametrize(
    ("scope", "case_id"), [("DEVELOPER", "U-09"), ("USER_MANAGER", "U-10")]
)
def test_u09_u10_ineligible_scope_gets_empty_catalog(
    client: TestClient, scope: str, case_id: str
) -> None:
    actor, downstream = make_actor(scope), AsyncMock()
    wire_settings(actor, downstream)
    assert client.get("/api/notification-settings").json() == []
    downstream.get_settings.assert_not_awaited(), case_id


# U-11
def test_u11_multiple_eligible_scopes_do_not_duplicate_event(
    client: TestClient,
) -> None:
    actor, downstream = make_actor("ADMIN", "SUPERUSER"), AsyncMock()
    downstream.get_settings.return_value = [setting(actor)]
    wire_settings(actor, downstream)
    assert len(client.get("/api/notification-settings").json()) == 1


@pytest.mark.parametrize("case_id", ["U-12 inactive event", "U-13 inactive channel"])
def test_u12_u13_inactive_upstream_items_are_absent_from_catalog(
    client: TestClient, case_id: str
) -> None:
    actor, downstream = make_actor("ADMIN"), AsyncMock()
    downstream.get_settings.return_value = []
    wire_settings(actor, downstream)
    assert client.get("/api/notification-settings").json() == [], case_id


# U-14
def test_u14_unknown_upstream_event_fails_closed_with_502(client: TestClient) -> None:
    actor, downstream = make_actor("ADMIN"), AsyncMock()
    downstream.get_settings.return_value = [setting(actor, event_code="unknown")]
    wire_settings(actor, downstream)
    assert client.get("/api/notification-settings").status_code == 502


def test_malformed_upstream_settings_schema_remains_fail_closed_502(
    client: TestClient,
) -> None:
    actor, downstream = make_actor("ADMIN"), AsyncMock()
    with pytest.raises(ValidationError) as error:
        NotificationSettingResponse.model_validate(
            {"event_code": "callback", "channel_code": "email"}
        )
    downstream.get_settings.side_effect = error.value
    wire_settings(actor, downstream)

    assert client.get("/api/notification-settings").status_code == 502


# U-15
def test_u15_notification_timeout_is_502(client: TestClient) -> None:
    actor, downstream = make_actor("ADMIN"), AsyncMock()
    downstream.get_settings.side_effect = httpx.ReadTimeout(
        "timeout", request=httpx.Request("GET", "http://notification/settings")
    )
    wire_settings(actor, downstream)
    assert client.get("/api/notification-settings").status_code == 502


# U-16
def test_u16_anonymous_settings_patch_is_401(client: TestClient) -> None:
    downstream = AsyncMock()
    deny_auth()
    app.dependency_overrides[get_notification_settings_service] = lambda: (
        NotificationSettingsService(downstream)
    )
    response = client.patch(
        "/api/notification-settings/callback/email", json={"enabled": True}
    )
    assert response.status_code == 401
    downstream.set_setting.assert_not_awaited()


@pytest.mark.parametrize(
    ("scope", "enabled", "case_id"),
    [("ADMIN", True, "U-17"), ("SUPERUSER", False, "U-18")],
)
def test_u17_u18_eligible_actor_can_set_setting(
    client: TestClient, scope: str, enabled: bool, case_id: str
) -> None:
    actor, downstream = make_actor(scope), AsyncMock()
    downstream.set_setting.return_value = setting(actor, enabled=enabled)
    wire_settings(actor, downstream)
    response = client.patch(
        "/api/notification-settings/callback/email", json={"enabled": enabled}
    )
    assert response.status_code == 200, case_id
    assert response.json()["enabled"] is enabled


@pytest.mark.parametrize(("enabled", "case_id"), [(True, "U-19"), (False, "U-20")])
def test_u19_u20_repeated_writes_remain_idempotent(
    client: TestClient, enabled: bool, case_id: str
) -> None:
    actor, downstream = make_actor("ADMIN"), AsyncMock()
    downstream.set_setting.return_value = setting(actor, enabled=enabled)
    wire_settings(actor, downstream)
    for _ in range(2):
        response = client.patch(
            "/api/notification-settings/callback/email", json={"enabled": enabled}
        )
        assert response.status_code == 200, case_id
        assert response.json()["enabled"] is enabled
    assert downstream.set_setting.await_count == 2


# U-21
def test_u21_ineligible_patch_is_403_without_write(client: TestClient) -> None:
    actor, downstream = make_actor("DEVELOPER"), AsyncMock()
    wire_settings(actor, downstream)
    response = client.patch(
        "/api/notification-settings/callback/email", json={"enabled": True}
    )
    assert response.status_code == 403
    downstream.set_setting.assert_not_awaited()


@pytest.mark.parametrize(
    ("event_code", "channel_code", "case_id"),
    [("missing", "email", "U-22"), ("callback", "missing", "U-23")],
)
def test_u22_u23_unknown_combination_is_404(
    client: TestClient, event_code: str, channel_code: str, case_id: str
) -> None:
    actor, downstream = make_actor("ADMIN"), AsyncMock()
    wire_settings(actor, downstream)
    response = client.patch(
        f"/api/notification-settings/{event_code}/{channel_code}",
        json={"enabled": True},
    )
    assert response.status_code == 404, case_id
    downstream.set_setting.assert_not_awaited()


# U-24
def test_u24_invalid_enabled_body_is_400_without_write(client: TestClient) -> None:
    actor, downstream = make_actor("ADMIN"), AsyncMock()
    wire_settings(actor, downstream)
    response = client.patch(
        "/api/notification-settings/callback/email", json={"enabled": "yes"}
    )
    assert response.status_code == 400
    downstream.set_setting.assert_not_awaited()


# U-25
def test_u25_public_schema_cannot_select_foreign_user_id(client: TestClient) -> None:
    actor, downstream = make_actor("ADMIN"), AsyncMock()
    wire_settings(actor, downstream)
    response = client.patch(
        "/api/notification-settings/callback/email",
        json={"enabled": True, "user_id": str(uuid4())},
    )
    assert response.status_code == 422
    downstream.set_setting.assert_not_awaited()
