from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from core.entities.user import UserScope
from core.exceptions.auth import InvalidCredentials
from core.schemas.users import UserOutDto
from depends.services import get_current_user, get_email_proxy_service
from main import app


def actor(*, user_id: UUID | None = None, scope: str | None = None) -> UserOutDto:
    return UserOutDto(
        id=user_id or uuid4(),
        equestrian_id=uuid4(),
        username="email-owner",
        created_at=datetime.now(UTC),
        scopes=[]
        if scope is None
        else [UserScope(scope_name=scope, scope_description="test scope")],
    )


@pytest.fixture
def client_and_service():
    service = AsyncMock()
    app.dependency_overrides[get_email_proxy_service] = lambda: service
    try:
        yield TestClient(app), service
    finally:
        app.dependency_overrides.clear()


def authenticate(user: UserOutDto) -> None:
    app.dependency_overrides[get_current_user] = lambda: user


def test_anonymous_create_is_401_before_client(client_and_service) -> None:
    client, service = client_and_service

    async def no_actor() -> None:
        raise InvalidCredentials("Отсутствуют учетные данные")

    app.dependency_overrides[get_current_user] = no_actor
    response = client.post(
        "/api/emails", json={"user_id": str(uuid4()), "email": "a@example.com"}
    )
    assert response.status_code == 401
    service.create.assert_not_awaited()


def test_owner_create_returns_201_email_response(client_and_service) -> None:
    client, service = client_and_service
    owner = actor()
    authenticate(owner)
    expected = {
        "id": str(uuid4()),
        "user_id": str(owner.id),
        "email": "a@example.com",
        "approved": False,
    }
    service.create.return_value = expected
    response = client.post(
        "/api/emails", json={"user_id": str(owner.id), "email": "a@example.com"}
    )
    assert response.status_code == 201
    assert response.json() == expected


@pytest.mark.parametrize("scope", [None, "SUPERUSER", "ADMIN"])
def test_foreign_create_has_no_privileged_override(
    client_and_service, scope: str | None
) -> None:
    client, service = client_and_service
    authenticate(actor(scope=scope))
    foreign_id = uuid4()
    # Exercise the real boundary service rather than a permissive API mock.
    from core.services.email_proxy import EmailProxyService

    boundary = EmailProxyService(AsyncMock())
    app.dependency_overrides[get_email_proxy_service] = lambda: boundary
    response = client.post(
        "/api/emails", json={"user_id": str(foreign_id), "email": "a@example.com"}
    )
    assert response.status_code == 403
    service.create.assert_not_awaited()


@pytest.mark.parametrize(
    ("payload", "path"),
    [
        ({"user_id": "not-a-uuid", "email": "a@example.com"}, "/api/emails"),
        ({"user_id": str(uuid4())}, "/api/emails"),
        ({"user_id": str(uuid4()), "email": "not-an-email"}, "/api/emails"),
    ],
)
def test_invalid_create_is_400(client_and_service, payload: dict, path: str) -> None:
    client, service = client_and_service
    authenticate(
        actor(user_id=UUID(payload["user_id"]))
        if payload.get("user_id") not in {None, "not-a-uuid"}
        else actor()
    )
    response = client.post(path, json=payload)
    assert response.status_code == 400
    service.create.assert_not_awaited()


def test_anonymous_update_is_401(client_and_service) -> None:
    client, service = client_and_service

    async def no_actor() -> None:
        raise InvalidCredentials("missing")

    app.dependency_overrides[get_current_user] = no_actor
    response = client.patch(
        "/api/emails", json={"user_id": str(uuid4()), "email": "a@example.com"}
    )
    assert response.status_code == 401
    service.update.assert_not_awaited()


def test_owner_update_succeeds(client_and_service) -> None:
    client, service = client_and_service
    owner = actor()
    authenticate(owner)
    service.update.return_value = {"user_id": str(owner.id), "email": "b@example.com"}
    response = client.patch(
        "/api/emails", json={"user_id": str(owner.id), "email": "b@example.com"}
    )
    assert response.status_code == 200


@pytest.mark.parametrize("scope", [None, "SUPERUSER"])
def test_foreign_update_is_403_before_client(
    client_and_service, scope: str | None
) -> None:
    client, service = client_and_service
    user = actor(scope=scope)
    authenticate(user)
    from core.services.email_proxy import EmailProxyService

    downstream = AsyncMock()
    app.dependency_overrides[get_email_proxy_service] = lambda: EmailProxyService(
        downstream
    )
    response = client.patch(
        "/api/emails", json={"user_id": str(uuid4()), "email": "b@example.com"}
    )
    assert response.status_code == 403
    downstream.update_email.assert_not_awaited()


def test_invalid_update_is_400(client_and_service) -> None:
    client, service = client_and_service
    owner = actor()
    authenticate(owner)
    response = client.patch(
        "/api/emails", json={"user_id": str(owner.id), "email": "bad"}
    )
    assert response.status_code == 400
    service.update.assert_not_awaited()


def test_anonymous_delete_is_401(client_and_service) -> None:
    client, service = client_and_service

    async def no_actor() -> None:
        raise InvalidCredentials("missing")

    app.dependency_overrides[get_current_user] = no_actor
    response = client.delete(f"/api/emails/{uuid4()}")
    assert response.status_code == 401
    service.delete.assert_not_awaited()


def test_owner_delete_is_204(client_and_service) -> None:
    client, service = client_and_service
    owner = actor()
    authenticate(owner)
    response = client.delete(f"/api/emails/{owner.id}")
    assert response.status_code == 204


@pytest.mark.parametrize("scope", [None, "SUPERUSER"])
def test_foreign_delete_is_403_before_client(
    client_and_service, scope: str | None
) -> None:
    client, _ = client_and_service
    authenticate(actor(scope=scope))
    from core.services.email_proxy import EmailProxyService

    downstream = AsyncMock()
    app.dependency_overrides[get_email_proxy_service] = lambda: EmailProxyService(
        downstream
    )
    response = client.delete(f"/api/emails/{uuid4()}")
    assert response.status_code == 403
    downstream.delete_email.assert_not_awaited()


def test_malformed_delete_uuid_is_400(client_and_service) -> None:
    client, service = client_and_service
    authenticate(actor())
    response = client.delete("/api/emails/not-a-uuid")
    assert response.status_code == 400
    service.delete.assert_not_awaited()


def test_public_confirmation_routes(client_and_service) -> None:
    client, service = client_and_service
    service.send_confirmation.return_value = {"detail": "queued"}
    service.confirm.return_value = {
        "status": "confirmed",
        "user_email_id": str(uuid4()),
    }
    user_id = uuid4()
    assert (
        client.post(
            "/api/emails/send-confirmation", json={"user_id": str(user_id)}
        ).status_code
        == 202
    )
    assert (
        client.patch("/api/emails/confirm", json={"code": "valid-code"}).status_code
        == 200
    )


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("post", "/api/emails/send-confirmation", {"user_id": "bad"}),
        ("patch", "/api/emails/confirm", {"code": ""}),
    ],
)
def test_invalid_confirmation_is_400(
    client_and_service, method: str, path: str, payload: dict
) -> None:
    client, service = client_and_service
    response = getattr(client, method)(path, json=payload)
    assert response.status_code == 400
    service.confirm.assert_not_awaited()
    service.send_confirmation.assert_not_awaited()


@pytest.mark.parametrize("non_json", [False, True])
def test_downstream_errors_are_controlled(client_and_service, non_json: bool) -> None:
    client, service = client_and_service
    service.confirm.side_effect = httpx.HTTPStatusError(
        "downstream",
        request=httpx.Request("PATCH", "http://email/emails/confirm"),
        response=httpx.Response(
            503, text="broken" if non_json else '{"detail":"busy"}'
        ),
    )
    response = client.patch("/api/emails/confirm", json={"code": "valid"})
    assert response.status_code == 503
    assert "detail" in response.json()


@pytest.mark.parametrize("status_code", [400, 409, 410])
def test_confirmation_domain_statuses_are_preserved(
    client_and_service, status_code: int
) -> None:
    client, service = client_and_service
    service.confirm.side_effect = httpx.HTTPStatusError(
        "downstream",
        request=httpx.Request("PATCH", "http://email/emails/confirm"),
        response=httpx.Response(status_code, json={"detail": "confirmation outcome"}),
    )

    response = client.patch("/api/emails/confirm", json={"code": "well-formed-code"})

    assert response.status_code == status_code
    assert response.json() == {"detail": "confirmation outcome"}


def test_downstream_timeout_is_controlled(client_and_service) -> None:
    client, service = client_and_service
    service.confirm.side_effect = httpx.ReadTimeout(
        "timeout", request=httpx.Request("PATCH", "http://email/emails/confirm")
    )
    response = client.patch("/api/emails/confirm", json={"code": "valid"})
    assert response.status_code == 502
    assert response.json() == {"detail": "Email service unavailable"}


@pytest.mark.parametrize(
    ("method", "path", "service_method", "payload"),
    [
        ("patch", "/api/emails", "update", {"email": "new@example.com"}),
        ("delete", "/api/emails/{user_id}", "delete", None),
    ],
)
def test_owner_missing_is_404(
    client_and_service,
    method: str,
    path: str,
    service_method: str,
    payload: dict | None,
) -> None:
    client, service = client_and_service
    owner = actor()
    authenticate(owner)
    getattr(service, service_method).side_effect = httpx.HTTPStatusError(
        "missing",
        request=httpx.Request(method.upper(), "http://email/emails"),
        response=httpx.Response(404, json={"detail": "not found"}),
    )
    target = path.format(user_id=owner.id)
    body = None if payload is None else {**payload, "user_id": str(owner.id)}
    response = (
        getattr(client, method)(target, json=body)
        if body is not None
        else getattr(client, method)(target)
    )
    assert response.status_code == 404


def test_email_client_di_is_factory_not_global_instance() -> None:
    import api.emails as email_api
    from core.protocols.email_service import EmailServiceClientProtocol
    from depends.services import get_email_service_client

    assert not hasattr(email_api, "email_service_client")
    assert get_email_service_client.__annotations__["return"] in {
        EmailServiceClientProtocol,
        "EmailServiceClientProtocol",
    }
