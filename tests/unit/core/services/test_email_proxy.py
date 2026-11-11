from datetime import UTC, datetime
from unittest.mock import AsyncMock, call
from uuid import uuid4

import httpx
import pytest

from core.entities.user import UserScope
from core.exceptions.auth import ForbiddenError
from core.exceptions.email_proxy import (
    EmailConfirmationQueueError,
    EmailServiceResponseError,
)
from core.schemas.users import UserOutDto
from core.services.email_proxy import EmailProxyService


@pytest.fixture
def boundary():
    owner = UserOutDto(
        id=uuid4(),
        equestrian_id=uuid4(),
        username="unit-owner",
        created_at=datetime.now(UTC),
        scopes=[],
    )
    peer = AsyncMock()
    peer.create_email.return_value = {
        "id": str(uuid4()),
        "user_id": str(owner.id),
        "email": "unit@example.invalid",
        "approved": False,
    }
    peer.send_confirmation.return_value = {"detail": "queued"}
    return EmailProxyService(peer), peer, owner


# UT-EM-01/02/03/09: default, opt-out and confirmed do not change the resource.
@pytest.mark.parametrize("flag", [None, True, False])
@pytest.mark.parametrize("approved", [False, True])
async def test_create_order_and_conditional_confirmation(boundary, flag, approved):
    service, peer, owner = boundary
    peer.create_email.return_value["approved"] = approved
    options = {} if flag is None else {"send_confirmation": flag}

    result = await service.create(
        user_id=owner.id, email="unit@example.invalid", actor=owner, **options
    )

    expected = [call.create_email(user_id=owner.id, email="unit@example.invalid")]
    if flag is not False and not approved:
        expected.append(call.send_confirmation(user_id=owner.id))
    assert peer.mock_calls == expected
    assert result == peer.create_email.return_value
    assert result["approved"] is approved


# UT-EM-04: no second step if the create result cannot be trusted.
@pytest.mark.parametrize("failure", [400, 409, 503, "timeout", "invalid"])
async def test_failed_create_never_sends(boundary, failure):
    service, peer, owner = boundary
    if failure == "timeout":
        error = httpx.ReadTimeout("private payload")
    elif failure == "invalid":
        error = EmailServiceResponseError()
    else:
        error = httpx.HTTPStatusError(
            "private payload",
            request=httpx.Request("POST", "http://email/emails"),
            response=httpx.Response(failure),
        )
    peer.create_email.side_effect = error

    with pytest.raises(type(error)) as raised:
        await service.create(
            user_id=owner.id, email="unit@example.invalid", actor=owner
        )

    assert raised.value is error
    peer.send_confirmation.assert_not_awaited()
    peer.delete_email.assert_not_awaited()


# UT-EM-05: safe partial failure, no retries or compensating DELETE.
@pytest.mark.parametrize(
    "failure", [404, 500, "timeout", "transport", "json", "invalid"]
)
async def test_send_failure_is_stage_aware(boundary, failure):
    service, peer, owner = boundary
    if failure == "timeout":
        error = httpx.ReadTimeout("private payload")
    elif failure == "transport":
        error = httpx.ConnectError("private payload")
    elif failure == "json":
        error = ValueError("private payload")
    elif failure == "invalid":
        error = EmailServiceResponseError()
    else:
        error = httpx.HTTPStatusError(
            "private payload",
            request=httpx.Request("POST", "http://email/emails/send-confirmation"),
            response=httpx.Response(failure),
        )
    peer.send_confirmation.side_effect = error

    with pytest.raises(EmailConfirmationQueueError, match="Email сохранён") as raised:
        await service.create(
            user_id=owner.id, email="unit@example.invalid", actor=owner
        )

    assert "private payload" not in str(raised.value)
    assert peer.mock_calls == [
        call.create_email(user_id=owner.id, email="unit@example.invalid"),
        call.send_confirmation(user_id=owner.id),
    ]


# UT-EM-06: this checks orchestration only, not PostgreSQL uniqueness.
async def test_retry_same_unconfirmed_resource_repeats_send(boundary):
    service, peer, owner = boundary
    peer.send_confirmation.side_effect = [
        httpx.ReadTimeout("private"),
        {"detail": "queued"},
    ]
    original = peer.create_email.return_value.copy()
    with pytest.raises(EmailConfirmationQueueError):
        await service.create(
            user_id=owner.id, email="unit@example.invalid", actor=owner
        )
    result = await service.create(
        user_id=owner.id, email="unit@example.invalid", actor=owner
    )
    assert result == original
    assert peer.create_email.await_count == peer.send_confirmation.await_count == 2
    peer.delete_email.assert_not_awaited()


# UT-EM-08: even privileged actors have no owner override.
@pytest.mark.parametrize("scope", [None, "ADMIN", "SUPERUSER"])
@pytest.mark.parametrize("flag", [True, False])
async def test_foreign_owner_denied_before_any_peer_call(boundary, scope, flag):
    service, peer, owner = boundary
    if scope:
        owner.scopes = [UserScope(scope_name=scope, scope_description="test")]
    with pytest.raises(ForbiddenError):
        await service.create(
            user_id=uuid4(),
            email="unit@example.invalid",
            actor=owner,
            send_confirmation=flag,
        )
    assert peer.mock_calls == []


# Unknown programming errors must not be disguised as queue failures.
async def test_programming_error_is_not_swallowed(boundary):
    service, peer, owner = boundary
    peer.send_confirmation.side_effect = RuntimeError("bug")
    with pytest.raises(RuntimeError, match="bug"):
        await service.create(
            user_id=owner.id, email="unit@example.invalid", actor=owner
        )


# UT-EM-10: PATCH retains save-only semantics.
async def test_update_does_not_send_confirmation(boundary):
    service, peer, owner = boundary
    await service.update(user_id=owner.id, email="new@example.invalid", actor=owner)
    assert peer.mock_calls == [
        call.update_email(user_id=owner.id, email="new@example.invalid")
    ]
