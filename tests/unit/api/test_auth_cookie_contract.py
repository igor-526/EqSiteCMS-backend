from fastapi.testclient import TestClient

from core.entities.equestrian import Equestrian
from core.schemas.auth import AuthTokens
from depends.repositories import get_equestrian_repository
from depends.services import get_auth_service, get_breed_service
from main import app


class StubAuthService:
    async def login(self, **_: object) -> AuthTokens:
        return AuthTokens(access_token="access-token", refresh_token="refresh-token")

    async def refresh(self, refresh_token: str) -> AuthTokens:
        return AuthTokens(
            access_token=f"new-access-for-{refresh_token}",
            refresh_token=f"new-refresh-for-{refresh_token}",
        )


class StubEquestrianRepository:
    def __init__(self) -> None:
        self.equestrian = Equestrian(name="Demo Equestrian", service_key="valid-key")

    async def get_by_service_key(self, service_key: str) -> Equestrian | None:
        if service_key == self.equestrian.service_key:
            return self.equestrian
        return None


class StubBreedService:
    async def get_filtered(self, **_: object) -> tuple[list[object], int]:
        return [], 0


def get_set_cookie_headers(response) -> list[str]:
    return response.headers.get_list("set-cookie")


def override_auth_dependencies() -> None:
    app.dependency_overrides[get_auth_service] = StubAuthService
    app.dependency_overrides[get_equestrian_repository] = StubEquestrianRepository
    app.dependency_overrides[get_breed_service] = StubBreedService


def clear_auth_dependencies() -> None:
    app.dependency_overrides.pop(get_auth_service, None)
    app.dependency_overrides.pop(get_equestrian_repository, None)
    app.dependency_overrides.pop(get_breed_service, None)


def test_login_sets_refresh_cookie_for_api_root_and_clears_legacy_refresh_path():
    client = TestClient(app)
    override_auth_dependencies()

    try:
        response = client.post(
            "/api/auth/login",
            json={"username": "demo", "password": "secret"},
        )
    finally:
        clear_auth_dependencies()

    assert response.status_code == 200
    set_cookie_headers = get_set_cookie_headers(response)
    assert any(
        header.startswith("refresh_token=refresh-token;")
        and "Path=/" in header
        and "Max-Age=" in header
        for header in set_cookie_headers
    )
    assert any(
        header.startswith("refresh_token=")
        and "Path=/api/auth/refresh" in header
        and "Max-Age=0" in header
        for header in set_cookie_headers
    )


def test_refresh_rotates_refresh_cookie_for_api_root_and_clears_legacy_refresh_path():
    client = TestClient(app)
    override_auth_dependencies()
    client.cookies.set("refresh_token", "refresh-token", path="/")

    try:
        response = client.post("/api/auth/refresh")
    finally:
        clear_auth_dependencies()

    assert response.status_code == 200
    set_cookie_headers = get_set_cookie_headers(response)
    assert any(
        header.startswith("refresh_token=new-refresh-for-refresh-token;")
        and "Path=/" in header
        and "Max-Age=" in header
        for header in set_cookie_headers
    )
    assert any(
        header.startswith("refresh_token=")
        and "Path=/api/auth/refresh" in header
        and "Max-Age=0" in header
        for header in set_cookie_headers
    )


def test_logout_deletes_current_and_legacy_refresh_cookie_paths():
    client = TestClient(app)

    response = client.post("/api/auth/logout")

    assert response.status_code == 204
    set_cookie_headers = get_set_cookie_headers(response)
    assert any(
        header.startswith("refresh_token=")
        and "Path=/" in header
        and "Max-Age=0" in header
        for header in set_cookie_headers
    )
    assert any(
        header.startswith("refresh_token=")
        and "Path=/api/auth/refresh" in header
        and "Max-Age=0" in header
        for header in set_cookie_headers
    )


def test_login_refresh_cookie_reaches_dual_mode_read_after_access_cookie_expires():
    client = TestClient(app)
    override_auth_dependencies()

    try:
        login_response = client.post(
            "/api/auth/login",
            json={"username": "demo", "password": "secret"},
        )
        assert login_response.status_code == 200

        client.cookies.delete("access_token", path="/")
        response = client.get("/api/horses/breeds")
    finally:
        clear_auth_dependencies()

    assert response.status_code == 401
