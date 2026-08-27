"""Owner-only правило VK-прокси: отказ до downstream, отсутствие role override."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from clients.vk_service.schemas import (
    VkBindingResponse,
    VkBotInfoResponse,
    VkIssueConfirmationResponse,
)
from core.entities.user import UserScope
from core.exceptions.auth import ForbiddenError
from core.exceptions.base import NotFoundError
from core.schemas.users import UserOutDto
from core.services.vk_proxy import VkProxyService


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


def _service() -> tuple[VkProxyService, AsyncMock]:
    client = AsyncMock()
    return VkProxyService(client), client


async def test_get_mine_returns_the_owner_binding() -> None:
    service, client = _service()
    owner = actor()
    expected = VkBindingResponse(
        id=uuid4(),
        user_id=owner.id,
        vk_peer_id=42,
        state="ACTIVE",
        vk_screen_name="durov",
        vk_display_name="Pavel",
    )
    client.get_binding.return_value = expected

    assert await service.get_mine(actor=owner) is expected
    client.get_binding.assert_awaited_once_with(user_id=owner.id)


async def test_get_mine_raises_not_found_for_a_missing_binding() -> None:
    service, client = _service()
    client.get_binding.return_value = None

    with pytest.raises(NotFoundError):
        await service.get_mine(actor=actor())


async def test_issue_confirmation_always_uses_the_session_owner() -> None:
    service, client = _service()
    owner = actor(scope="SUPERUSER")
    client.issue_confirmation.return_value = VkIssueConfirmationResponse(
        code="ABC23XYZ",
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
        state="PENDING",
        link_command="/link",
        dialog_url="https://vk.me/eqsitecms_bot",
    )

    await service.issue_confirmation(actor=owner)

    client.issue_confirmation.assert_awaited_once_with(user_id=owner.id)


async def test_owner_delete_reaches_downstream() -> None:
    service, client = _service()
    owner = actor()

    await service.delete(user_id=owner.id, actor=owner)

    client.delete_binding.assert_awaited_once_with(user_id=owner.id)


@pytest.mark.parametrize("scope", [None, "ADMIN", "SUPERUSER"])
async def test_foreign_delete_is_forbidden_before_downstream(scope: str | None) -> None:
    service, client = _service()
    owner = actor(scope=scope)

    with pytest.raises(ForbiddenError):
        await service.delete(user_id=uuid4(), actor=owner)

    client.delete_binding.assert_not_awaited()


async def test_bot_info_needs_no_actor() -> None:
    service, client = _service()
    expected = VkBotInfoResponse(
        group_id=1,
        group_screen_name="eqsitecms_bot",
        link_command="/link",
        group_url="https://vk.com/eqsitecms_bot",
        dialog_url="https://vk.me/eqsitecms_bot",
    )
    client.get_bot_info.return_value = expected

    assert await service.get_bot_info() is expected


async def test_the_proxy_exposes_no_route_accepting_a_foreign_owner() -> None:
    import inspect

    source = inspect.getsource(VkProxyService)

    assert "user_id=actor.id" in source or "user_id: UUID, actor" in source
    assert "actor.id != user_id" in source
