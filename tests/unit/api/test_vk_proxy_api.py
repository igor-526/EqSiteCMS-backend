"""Access matrix VK-прокси: anonymous, owner, foreign, downstream, валидация."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from clients.vk_service.schemas import (
    VkBindingResponse,
    VkBotInfoResponse,
    VkIssueConfirmationResponse,
)
from core.entities.user import UserScope
from core.exceptions.auth import InvalidCredentials
from core.schemas.users import UserOutDto
from depends.services import get_current_user, get_vk_proxy_service
from main import app

GROUP_SCREEN_NAME = "eqsitecms_bot"


def actor(*, user_id: UUID | None = None, scope: str | None = None) -> UserOutDto:
    return UserOutDto(
        id=user_id or uuid4(),
        equestrian_id=uuid4(),
        username="vk-owner",
        created_at=datetime.now(UTC),
        scopes=(
            []
            if scope is None
            else [UserScope(scope_name=scope, scope_description="test scope")]
        ),
    )


@pytest.fixture
def client_and_service():
    service = AsyncMock()
    app.dependency_overrides[get_vk_proxy_service] = lambda: service
    try:
        yield TestClient(app), service
    finally:
        app.dependency_overrides.clear()


def authenticate(user: UserOutDto) -> None:
    app.dependency_overrides[get_current_user] = lambda: user


def anonymous() -> None:
    async def no_actor() -> None:
        raise InvalidCredentials("Отсутствуют учетные данные")

    app.dependency_overrides[get_current_user] = no_actor


def binding(owner: UserOutDto, *, state: str = "ACTIVE") -> VkBindingResponse:
    return VkBindingResponse(
        id=uuid4(),
        user_id=owner.id,
        vk_peer_id=424242 if state == "ACTIVE" else None,
        state=state,
        vk_screen_name="durov" if state == "ACTIVE" else None,
        vk_display_name="Pavel" if state == "ACTIVE" else None,
    )


def status_error(code: int, payload: dict | None = None) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "http://vk-service/vks")
    response = httpx.Response(
        code,
        json=payload if payload is not None else {"detail": "downstream"},
        request=request,
    )
    return httpx.HTTPStatusError("downstream", request=request, response=response)


# ---------- GET /api/vks/me ----------


def test_anonymous_read_is_401_before_downstream(client_and_service) -> None:
    client, service = client_and_service
    anonymous()

    response = client.get("/api/vks/me")

    assert response.status_code == 401
    service.get_mine.assert_not_awaited()


def test_owner_read_returns_the_binding(client_and_service) -> None:
    client, service = client_and_service
    owner = actor()
    authenticate(owner)
    service.get_mine.return_value = binding(owner)

    response = client.get("/api/vks/me")

    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == str(owner.id)
    assert (body["state"], body["vk_peer_id"]) == ("ACTIVE", 424242)


def test_owner_read_exposes_a_pending_state(client_and_service) -> None:
    client, service = client_and_service
    owner = actor()
    authenticate(owner)
    service.get_mine.return_value = binding(owner, state="PENDING")

    response = client.get("/api/vks/me")

    assert response.status_code == 200
    assert response.json()["state"] == "PENDING"
    assert response.json()["vk_peer_id"] is None


def test_missing_binding_is_404(client_and_service) -> None:
    client, service = client_and_service
    authenticate(actor())
    service.get_mine.side_effect = status_error(404)

    response = client.get("/api/vks/me")

    assert response.status_code == 404


def test_read_request_cannot_select_a_foreign_owner(client_and_service) -> None:
    client, service = client_and_service
    owner = actor()
    authenticate(owner)
    service.get_mine.return_value = binding(owner)

    client.get("/api/vks/me", params={"user_id": str(uuid4())})

    service.get_mine.assert_awaited_once_with(actor=owner)


def test_read_downstream_timeout_is_502(client_and_service) -> None:
    client, service = client_and_service
    authenticate(actor())
    service.get_mine.side_effect = httpx.ConnectTimeout("timeout")

    response = client.get("/api/vks/me")

    assert response.status_code == 502
    assert "vk-service" not in response.text.lower()


def test_read_downstream_invalid_body_is_502(client_and_service) -> None:
    client, service = client_and_service
    authenticate(actor())
    service.get_mine.side_effect = ValueError("ambiguous owner response")

    response = client.get("/api/vks/me")

    assert response.status_code == 502


def test_read_unexpected_downstream_status_is_502(client_and_service) -> None:
    client, service = client_and_service
    authenticate(actor())
    service.get_mine.side_effect = status_error(500)

    response = client.get("/api/vks/me")

    assert response.status_code == 502


# ---------- GET /api/vks/bot-info ----------


def test_bot_info_is_public(client_and_service) -> None:
    client, service = client_and_service
    anonymous()
    service.get_bot_info.return_value = VkBotInfoResponse(
        group_id=224466,
        group_screen_name=GROUP_SCREEN_NAME,
        link_command="/link",
        group_url=f"https://vk.com/{GROUP_SCREEN_NAME}",
        dialog_url=f"https://vk.me/{GROUP_SCREEN_NAME}",
    )

    response = client.get("/api/vks/bot-info")

    assert response.status_code == 200
    assert response.json()["dialog_url"] == f"https://vk.me/{GROUP_SCREEN_NAME}"


def test_bot_info_is_identical_for_authenticated(client_and_service) -> None:
    client, service = client_and_service
    expected = VkBotInfoResponse(
        group_id=224466,
        group_screen_name=GROUP_SCREEN_NAME,
        link_command="/link",
        group_url=f"https://vk.com/{GROUP_SCREEN_NAME}",
        dialog_url=f"https://vk.me/{GROUP_SCREEN_NAME}",
    )
    service.get_bot_info.return_value = expected

    anonymous()
    anonymous_body = client.get("/api/vks/bot-info").json()
    authenticate(actor())
    authenticated_body = client.get("/api/vks/bot-info").json()

    assert anonymous_body == authenticated_body


def test_bot_info_propagates_an_incomplete_configuration(client_and_service) -> None:
    client, service = client_and_service
    anonymous()
    service.get_bot_info.side_effect = status_error(
        503, {"detail": "Конфигурация группы VK не завершена"}
    )

    response = client.get("/api/vks/bot-info")

    assert response.status_code == 503


def test_bot_info_downstream_failure_is_502(client_and_service) -> None:
    client, service = client_and_service
    anonymous()
    service.get_bot_info.side_effect = httpx.ConnectError("refused")

    response = client.get("/api/vks/bot-info")

    assert response.status_code == 502


# ---------- POST /api/vks/issue-confirmation ----------


def issued() -> VkIssueConfirmationResponse:
    return VkIssueConfirmationResponse(
        code="ABC23XYZ",
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
        state="PENDING",
        link_command="/link",
        dialog_url=f"https://vk.me/{GROUP_SCREEN_NAME}",
    )


def test_anonymous_issue_is_401_before_downstream(client_and_service) -> None:
    client, service = client_and_service
    anonymous()

    response = client.post("/api/vks/issue-confirmation")

    assert response.status_code == 401
    service.issue_confirmation.assert_not_awaited()


def test_owner_issue_returns_201_with_the_code(client_and_service) -> None:
    client, service = client_and_service
    owner = actor()
    authenticate(owner)
    service.issue_confirmation.return_value = issued()

    response = client.post("/api/vks/issue-confirmation")

    assert response.status_code == 201
    body = response.json()
    assert (body["code"], body["state"], body["link_command"]) == (
        "ABC23XYZ",
        "PENDING",
        "/link",
    )
    service.issue_confirmation.assert_awaited_once_with(actor=owner)


def test_issue_ignores_a_foreign_user_id_in_the_body(client_and_service) -> None:
    client, service = client_and_service
    owner = actor()
    authenticate(owner)
    service.issue_confirmation.return_value = issued()

    response = client.post(
        "/api/vks/issue-confirmation", json={"user_id": str(uuid4())}
    )

    assert response.status_code == 201
    service.issue_confirmation.assert_awaited_once_with(actor=owner)


@pytest.mark.parametrize("scope", [None, "ADMIN", "SUPERUSER"])
def test_issue_always_uses_the_session_owner(
    client_and_service, scope: str | None
) -> None:
    client, service = client_and_service
    owner = actor(scope=scope)
    authenticate(owner)
    service.issue_confirmation.return_value = issued()

    client.post("/api/vks/issue-confirmation")

    service.issue_confirmation.assert_awaited_once_with(actor=owner)


@pytest.mark.parametrize("state", ["ACTIVE", "BLOCKED"])
def test_issue_propagates_a_state_conflict(client_and_service, state: str) -> None:
    client, service = client_and_service
    authenticate(actor())
    service.issue_confirmation.side_effect = status_error(
        409, {"detail": f"conflict {state}"}
    )

    response = client.post("/api/vks/issue-confirmation")

    assert response.status_code == 409
    assert state in response.json()["detail"]


def test_issue_downstream_failure_is_502(client_and_service) -> None:
    client, service = client_and_service
    authenticate(actor())
    service.issue_confirmation.side_effect = httpx.ReadTimeout("timeout")

    response = client.post("/api/vks/issue-confirmation")

    assert response.status_code == 502


# ---------- DELETE /api/vks/{user_id} ----------


def test_anonymous_delete_is_401_before_downstream(client_and_service) -> None:
    client, service = client_and_service
    anonymous()

    response = client.delete(f"/api/vks/{uuid4()}")

    assert response.status_code == 401
    service.delete.assert_not_awaited()


def test_owner_delete_returns_204(client_and_service) -> None:
    client, service = client_and_service
    owner = actor()
    authenticate(owner)
    service.delete.return_value = None

    response = client.delete(f"/api/vks/{owner.id}")

    assert response.status_code == 204
    service.delete.assert_awaited_once_with(user_id=owner.id, actor=owner)


def test_owner_delete_is_idempotent(client_and_service) -> None:
    client, service = client_and_service
    owner = actor()
    authenticate(owner)
    service.delete.return_value = None

    first = client.delete(f"/api/vks/{owner.id}")
    second = client.delete(f"/api/vks/{owner.id}")

    assert (first.status_code, second.status_code) == (204, 204)


def test_malformed_delete_uuid_is_400_before_downstream(client_and_service) -> None:
    client, service = client_and_service
    authenticate(actor())

    response = client.delete("/api/vks/not-a-uuid")

    assert response.status_code == 400
    service.delete.assert_not_awaited()


def test_delete_downstream_failure_is_502(client_and_service) -> None:
    client, service = client_and_service
    owner = actor()
    authenticate(owner)
    service.delete.side_effect = httpx.ConnectError("refused")

    response = client.delete(f"/api/vks/{owner.id}")

    assert response.status_code == 502


def _vk_routes() -> set[tuple[str, str]]:
    return {
        (route.path, method)
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api/vks")
        for method in route.methods - {"HEAD", "OPTIONS"}
    }


def test_no_public_confirm_route_exists() -> None:
    paths = {path for path, _ in _vk_routes()}

    assert "/api/vks/confirm" not in paths
    assert not [path for path in paths if path.endswith("/confirm")]


def test_the_registered_vk_routes_match_the_access_matrix() -> None:
    assert _vk_routes() == {
        ("/api/vks/me", "GET"),
        ("/api/vks/bot-info", "GET"),
        ("/api/vks/issue-confirmation", "POST"),
        ("/api/vks/{user_id}", "DELETE"),
    }
