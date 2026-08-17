from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from core.entities.equestrian import Equestrian
from core.entities.user import User
from core.exceptions.auth import InvalidCredentials
from core.schemas.users import UserOutDto
from depends.repositories import get_equestrian_repository
from depends.services import (
    get_breed_service,
    get_current_user,
    get_optional_current_user,
    get_read_equestrian_context,
)
from main import app


class StubAuthService:
    def __init__(self) -> None:
        self.tokens: list[str] = []
        self.user = UserOutDto.model_validate(
            User(
                equestrian_id=UUID("11111111-1111-4111-8111-111111111111"),
                username="demo",
                password="hashed-password",
                first_name="Demo",
                last_name="User",
                middle_name=None,
            )
        )

    async def get_current_user(self, token: str) -> UserOutDto:
        self.tokens.append(token)
        if token == "invalid":
            raise InvalidCredentials("Неверный логин или пароль")
        return self.user


class StubEquestrianRepository:
    def __init__(self) -> None:
        self.service_keys: list[str] = []
        self.equestrian = Equestrian(name="Demo Equestrian", service_key="valid-key")

    async def get_by_service_key(self, service_key: str) -> Equestrian | None:
        self.service_keys.append(service_key)
        if service_key == self.equestrian.service_key:
            return self.equestrian
        return None


class StubBreedService:
    async def get_filtered(self, **_: object) -> tuple[list[object], int]:
        return [], 0


@pytest.mark.asyncio
async def test_get_current_user_without_cookie_raises_invalid_credentials():
    auth_service = StubAuthService()

    with pytest.raises(InvalidCredentials):
        await get_current_user(auth_service=auth_service, access_token=None)

    assert auth_service.tokens == []


@pytest.mark.asyncio
async def test_get_current_user_with_cookie_delegates_to_auth_service():
    auth_service = StubAuthService()

    result = await get_current_user(auth_service=auth_service, access_token="token")

    assert result == auth_service.user
    assert auth_service.tokens == ["token"]


@pytest.mark.asyncio
async def test_get_optional_current_user_without_cookie_returns_none():
    auth_service = StubAuthService()

    result = await get_optional_current_user(
        auth_service=auth_service, access_token=None
    )

    assert result is None
    assert auth_service.tokens == []


@pytest.mark.asyncio
async def test_get_optional_current_user_with_cookie_delegates_to_auth_service():
    auth_service = StubAuthService()

    result = await get_optional_current_user(
        auth_service=auth_service, access_token="token"
    )

    assert result == auth_service.user
    assert auth_service.tokens == ["token"]


@pytest.mark.asyncio
async def test_get_optional_current_user_with_invalid_cookie_raises_invalid_credentials():
    auth_service = StubAuthService()

    with pytest.raises(InvalidCredentials):
        await get_optional_current_user(
            auth_service=auth_service, access_token="invalid"
        )

    assert auth_service.tokens == ["invalid"]


@pytest.mark.asyncio
async def test_get_read_equestrian_context_with_current_user_returns_authenticated_context():
    auth_service = StubAuthService()
    repository = StubEquestrianRepository()

    result = await get_read_equestrian_context(
        current_user=auth_service.user,
        equestrian_repository=repository,
        service_key="valid-key",
        refresh_token=None,
    )

    assert result.id == auth_service.user.equestrian_id
    assert result.source == "authenticated"
    assert repository.service_keys == []


@pytest.mark.asyncio
async def test_get_read_equestrian_context_without_cookies_with_service_key_returns_public_context():
    repository = StubEquestrianRepository()

    result = await get_read_equestrian_context(
        current_user=None,
        equestrian_repository=repository,
        service_key=" valid-key ",
        refresh_token=None,
    )

    assert result.id == repository.equestrian.id
    assert result.source == "public"
    assert repository.service_keys == ["valid-key"]


@pytest.mark.asyncio
async def test_get_read_equestrian_context_without_cookies_and_service_key_raises_unauthorized():
    repository = StubEquestrianRepository()

    with pytest.raises(InvalidCredentials):
        await get_read_equestrian_context(
            current_user=None,
            equestrian_repository=repository,
            service_key=None,
            refresh_token=None,
        )

    assert repository.service_keys == []


@pytest.mark.asyncio
async def test_get_read_equestrian_context_with_blank_service_key_raises_unauthorized():
    repository = StubEquestrianRepository()

    with pytest.raises(InvalidCredentials):
        await get_read_equestrian_context(
            current_user=None,
            equestrian_repository=repository,
            service_key=" ",
            refresh_token=None,
        )

    assert repository.service_keys == []


@pytest.mark.asyncio
async def test_get_read_equestrian_context_with_refresh_cookie_only_raises_invalid_credentials():
    repository = StubEquestrianRepository()

    with pytest.raises(InvalidCredentials):
        await get_read_equestrian_context(
            current_user=None,
            equestrian_repository=repository,
            service_key=None,
            refresh_token="refresh-token",
        )

    assert repository.service_keys == []


@pytest.mark.asyncio
async def test_get_read_equestrian_context_with_blank_refresh_cookie_returns_unauthorized():
    repository = StubEquestrianRepository()

    with pytest.raises(InvalidCredentials):
        await get_read_equestrian_context(
            current_user=None,
            equestrian_repository=repository,
            service_key=None,
            refresh_token=" ",
        )

    assert repository.service_keys == []


@pytest.mark.asyncio
async def test_get_read_equestrian_context_with_refresh_cookie_and_service_key_returns_public_context():
    repository = StubEquestrianRepository()

    result = await get_read_equestrian_context(
        current_user=None,
        equestrian_repository=repository,
        service_key="valid-key",
        refresh_token="refresh-token",
    )

    assert result.id == repository.equestrian.id
    assert result.source == "public"
    assert repository.service_keys == ["valid-key"]


@pytest.mark.asyncio
async def test_get_read_equestrian_context_with_invalid_service_key_raises_unauthorized():
    repository = StubEquestrianRepository()

    with pytest.raises(InvalidCredentials):
        await get_read_equestrian_context(
            current_user=None,
            equestrian_repository=repository,
            service_key="invalid-key",
            refresh_token=None,
        )

    assert repository.service_keys == ["invalid-key"]


def test_dual_mode_get_with_refresh_cookie_only_returns_401_not_400():
    client = TestClient(app)
    app.dependency_overrides[get_equestrian_repository] = StubEquestrianRepository
    app.dependency_overrides[get_breed_service] = StubBreedService
    client.cookies.set("refresh_token", "refresh-token")

    try:
        response = client.get("/api/horses/breeds")
    finally:
        app.dependency_overrides.pop(get_equestrian_repository, None)
        app.dependency_overrides.pop(get_breed_service, None)

    assert response.status_code == 401


def test_dual_mode_get_without_cookies_and_service_key_returns_401():
    client = TestClient(app)
    app.dependency_overrides[get_equestrian_repository] = StubEquestrianRepository
    app.dependency_overrides[get_breed_service] = StubBreedService

    try:
        response = client.get("/api/horses/breeds")
    finally:
        app.dependency_overrides.pop(get_equestrian_repository, None)
        app.dependency_overrides.pop(get_breed_service, None)

    assert response.status_code == 401


def test_dual_mode_get_with_unknown_service_key_returns_401():
    client = TestClient(app)
    app.dependency_overrides[get_equestrian_repository] = StubEquestrianRepository
    app.dependency_overrides[get_breed_service] = StubBreedService

    try:
        response = client.get(
            "/api/horses/breeds",
            headers={"X-Equestrian-Service-Key": "unknown-key"},
        )
    finally:
        app.dependency_overrides.pop(get_equestrian_repository, None)
        app.dependency_overrides.pop(get_breed_service, None)

    assert response.status_code == 401


def test_dual_mode_get_with_valid_service_key_returns_200():
    client = TestClient(app)
    app.dependency_overrides[get_equestrian_repository] = StubEquestrianRepository
    app.dependency_overrides[get_breed_service] = StubBreedService

    try:
        response = client.get(
            "/api/horses/breeds",
            headers={"X-Equestrian-Service-Key": "valid-key"},
        )
    finally:
        app.dependency_overrides.pop(get_equestrian_repository, None)
        app.dependency_overrides.pop(get_breed_service, None)

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}
