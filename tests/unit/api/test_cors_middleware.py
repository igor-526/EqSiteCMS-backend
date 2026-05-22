from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from main import app

CMS_ORIGIN = "http://localhost:3000"
FOREIGN_ORIGIN = "https://evil.com"
CONSUMER_ORIGIN = "https://stable-site.example.com"


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Public GET — любой origin получает Access-Control-Allow-Origin: *
# ---------------------------------------------------------------------------


def test_public_get_returns_wildcard_origin(client: TestClient) -> None:
    response = client.get("/health", headers={"Origin": CONSUMER_ORIGIN})

    assert response.headers.get("access-control-allow-origin") == "*"


def test_public_get_does_not_set_credentials(client: TestClient) -> None:
    response = client.get("/health", headers={"Origin": CONSUMER_ORIGIN})

    assert "access-control-allow-credentials" not in response.headers


def test_public_get_cms_origin_gets_strict_cors(client: TestClient) -> None:
    """CMS origin always receives protected (strict) CORS, even on public GETs."""
    response = client.get("/health", headers={"Origin": CMS_ORIGIN})

    assert response.headers.get("access-control-allow-origin") == CMS_ORIGIN
    assert response.headers.get("access-control-allow-credentials") == "true"


# ---------------------------------------------------------------------------
# Protected POST — разрешённый origin получает строгий CORS
# ---------------------------------------------------------------------------


def test_protected_post_allowed_origin_gets_cors_headers(client: TestClient) -> None:
    response = client.post(
        "/api/auth/logout",
        headers={"Origin": CMS_ORIGIN},
    )

    assert response.headers.get("access-control-allow-origin") == CMS_ORIGIN
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_protected_post_allowed_origin_sets_vary(client: TestClient) -> None:
    response = client.post(
        "/api/auth/logout",
        headers={"Origin": CMS_ORIGIN},
    )

    assert "Origin" in response.headers.get("vary", "")


def test_protected_post_foreign_origin_gets_no_cors_header(client: TestClient) -> None:
    response = client.post(
        "/api/auth/logout",
        headers={"Origin": FOREIGN_ORIGIN},
    )

    assert "access-control-allow-origin" not in response.headers


# ---------------------------------------------------------------------------
# Preflight OPTIONS для мутирующих методов
# ---------------------------------------------------------------------------


def test_preflight_post_allowed_origin_returns_200(client: TestClient) -> None:
    response = client.options(
        "/api/auth/login",
        headers={
            "Origin": CMS_ORIGIN,
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == CMS_ORIGIN
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_preflight_post_foreign_origin_returns_400(client: TestClient) -> None:
    response = client.options(
        "/api/auth/login",
        headers={
            "Origin": FOREIGN_ORIGIN,
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


# ---------------------------------------------------------------------------
# Preflight OPTIONS для публичных GET
# ---------------------------------------------------------------------------


def test_preflight_get_any_origin_returns_wildcard(client: TestClient) -> None:
    response = client.options(
        "/health",
        headers={
            "Origin": CONSUMER_ORIGIN,
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "*"
    assert "access-control-allow-credentials" not in response.headers


# ---------------------------------------------------------------------------
# CMS-only GET — /api/auth/me и /api/news-cms
# ---------------------------------------------------------------------------


def test_cms_only_get_me_allowed_origin_gets_cors_headers(client: TestClient) -> None:
    response = client.get("/api/auth/me", headers={"Origin": CMS_ORIGIN})

    assert response.headers.get("access-control-allow-origin") == CMS_ORIGIN
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_cms_only_get_me_foreign_origin_gets_no_cors_header(client: TestClient) -> None:
    response = client.get("/api/auth/me", headers={"Origin": FOREIGN_ORIGIN})

    assert "access-control-allow-origin" not in response.headers


def test_cms_only_get_news_cms_allowed_origin_gets_cors_headers(
    client: TestClient,
) -> None:
    response = client.get("/api/news-cms", headers={"Origin": CMS_ORIGIN})

    assert response.headers.get("access-control-allow-origin") == CMS_ORIGIN
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_cms_only_get_news_cms_consumer_origin_gets_no_cors_header(
    client: TestClient,
) -> None:
    response = client.get("/api/news-cms", headers={"Origin": CONSUMER_ORIGIN})

    assert "access-control-allow-origin" not in response.headers


# ---------------------------------------------------------------------------
# Запрос без Origin — CORS-заголовки не добавляются
# ---------------------------------------------------------------------------


def test_no_origin_header_no_cors_headers_added(client: TestClient) -> None:
    response = client.get("/health")

    assert "access-control-allow-origin" not in response.headers
    assert "access-control-allow-credentials" not in response.headers


# ---------------------------------------------------------------------------
# CMS origin + public GET — должен получать строгий CORS, не wildcard
# ---------------------------------------------------------------------------


def test_cms_origin_public_get_horses_gets_strict_cors(client: TestClient) -> None:
    """CMS origin + GET /api/horses → ACAO: origin, credentials: true (не wildcard)."""
    response = client.get("/api/horses", headers={"Origin": CMS_ORIGIN})

    assert response.headers.get("access-control-allow-origin") == CMS_ORIGIN
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_consumer_origin_public_get_horses_gets_wildcard(client: TestClient) -> None:
    """Consumer origin + GET /api/horses → ACAO: *, нет credentials."""
    response = client.get("/api/horses", headers={"Origin": CONSUMER_ORIGIN})

    assert response.headers.get("access-control-allow-origin") == "*"
    assert "access-control-allow-credentials" not in response.headers


def test_cms_origin_preflight_get_horses_gets_strict_cors(client: TestClient) -> None:
    """CMS origin + preflight GET /api/horses → 200, строгий CORS (не wildcard)."""
    response = client.options(
        "/api/horses",
        headers={
            "Origin": CMS_ORIGIN,
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == CMS_ORIGIN
    assert response.headers.get("access-control-allow-credentials") == "true"
