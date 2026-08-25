from __future__ import annotations

import pytest
from fastapi import FastAPI, Response
from fastapi.testclient import TestClient

from core.middleware.cors import SplitCORSMiddleware
from main import app

CMS_ORIGIN = "http://localhost:3000"
FOREIGN_ORIGIN = "https://evil.com"
CONSUMER_ORIGIN = "https://stable-site.example.com"


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def cors_contract_client() -> TestClient:
    contract_app = FastAPI()

    @contract_app.api_route(
        "/api/callback_requests", methods=["GET", "POST", "PATCH", "DELETE", "PUT"]
    )
    async def callback_response(status_code: int = 201) -> Response:
        return Response(status_code=status_code)

    @contract_app.post("/api/auth/logout")
    async def logout() -> Response:
        return Response(status_code=204)

    @contract_app.patch("/api/callback_requests/{request_id}/status")
    async def callback_status(request_id: int) -> Response:
        return Response(status_code=200)

    @contract_app.patch("/api/service/callback_requests/{request_id}/status")
    async def service_callback_status(request_id: int) -> Response:
        return Response(status_code=200)

    contract_app.add_middleware(
        SplitCORSMiddleware,
        cms_origins=[CMS_ORIGIN],
    )
    return TestClient(contract_app)


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


# ---------------------------------------------------------------------------
# Exact public callback POST exception
# ---------------------------------------------------------------------------


def _preflight(
    client: TestClient,
    *,
    path: str = "/api/callback_requests",
    origin: str = CONSUMER_ORIGIN,
    method: str = "POST",
    requested_headers: str | None = None,
):
    headers = {
        "Origin": origin,
        "Access-Control-Request-Method": method,
    }
    if requested_headers is not None:
        headers["Access-Control-Request-Headers"] = requested_headers
    return client.options(path, headers=headers)


def test_callback_post_preflight_is_public(cors_contract_client: TestClient) -> None:
    response = _preflight(cors_contract_client)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"


def test_callback_preflight_allows_only_post_and_options(
    cors_contract_client: TestClient,
) -> None:
    response = _preflight(cors_contract_client)
    assert response.headers["access-control-allow-methods"] == "POST, OPTIONS"


@pytest.mark.parametrize(
    "requested_headers",
    [
        "Content-Type",
        "X-Equestrian-Service-Key",
        "content-type",
        "x-equestrian-service-key",
        "CONTENT-TYPE, X-EQUESTRIAN-SERVICE-KEY",
        " Content-Type ,  X-Equestrian-Service-Key ",
    ],
)
def test_callback_preflight_accepts_allowed_headers_case_insensitively(
    cors_contract_client: TestClient,
    requested_headers: str,
) -> None:
    response = _preflight(cors_contract_client, requested_headers=requested_headers)
    assert response.status_code == 200
    assert response.headers["access-control-allow-headers"] == (
        "Content-Type, X-Equestrian-Service-Key"
    )


def test_callback_preflight_is_credentialless(
    cors_contract_client: TestClient,
) -> None:
    response = _preflight(cors_contract_client)
    assert "access-control-allow-credentials" not in response.headers


def test_callback_preflight_has_expected_max_age(
    cors_contract_client: TestClient,
) -> None:
    response = _preflight(cors_contract_client)
    assert response.headers["access-control-max-age"] == "600"


@pytest.mark.parametrize(
    "requested_headers",
    ["Authorization", "X-Custom", "Content-Type, X-Custom"],
)
def test_callback_preflight_rejects_unknown_headers_without_acao(
    cors_contract_client: TestClient,
    requested_headers: str,
) -> None:
    response = _preflight(cors_contract_client, requested_headers=requested_headers)
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_callback_get_preflight_uses_public_get_policy(
    cors_contract_client: TestClient,
) -> None:
    response = _preflight(cors_contract_client, method="GET")
    assert response.status_code == 200
    assert response.headers["access-control-allow-methods"] == "GET, OPTIONS"


@pytest.mark.parametrize("method", ["PATCH", "DELETE", "PUT"])
def test_callback_other_write_preflights_remain_protected(
    cors_contract_client: TestClient,
    method: str,
) -> None:
    response = _preflight(cors_contract_client, method=method)
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize(
    "path",
    [
        "/api/callback_requests/",
        "/api/callback_requests/42",
        "/api/callback_requests-extra",
        "/api/service/callback_requests/42/status",
    ],
)
def test_callback_public_exception_does_not_leak_to_adjacent_paths(
    cors_contract_client: TestClient,
    path: str,
) -> None:
    response = _preflight(cors_contract_client, path=path)
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_foreign_origin_auth_post_remains_strict(
    cors_contract_client: TestClient,
) -> None:
    response = cors_contract_client.post(
        "/api/auth/logout", headers={"Origin": FOREIGN_ORIGIN}
    )
    assert "access-control-allow-origin" not in response.headers


def test_cms_protected_post_remains_reflected_with_credentials_and_vary(
    cors_contract_client: TestClient,
) -> None:
    response = cors_contract_client.post(
        "/api/auth/logout", headers={"Origin": CMS_ORIGIN}
    )
    assert response.headers["access-control-allow-origin"] == CMS_ORIGIN
    assert response.headers["access-control-allow-credentials"] == "true"
    assert "Origin" in response.headers["vary"]


def _assert_callback_actual_response_is_consumer_readable(
    cors_contract_client: TestClient, status_code: int
) -> None:
    response = cors_contract_client.post(
        f"/api/callback_requests?status_code={status_code}",
        headers={"Origin": CONSUMER_ORIGIN},
    )
    assert response.status_code == status_code
    assert response.headers["access-control-allow-origin"] == "*"
    assert "access-control-allow-credentials" not in response.headers


def test_callback_actual_valid_post_201_is_consumer_readable(
    cors_contract_client: TestClient,
) -> None:
    _assert_callback_actual_response_is_consumer_readable(cors_contract_client, 201)


def test_callback_actual_missing_selector_401_is_consumer_readable(
    cors_contract_client: TestClient,
) -> None:
    _assert_callback_actual_response_is_consumer_readable(cors_contract_client, 401)


def test_callback_actual_invalid_selector_401_is_consumer_readable(
    cors_contract_client: TestClient,
) -> None:
    _assert_callback_actual_response_is_consumer_readable(cors_contract_client, 401)


def test_callback_actual_invalid_body_422_is_consumer_readable(
    cors_contract_client: TestClient,
) -> None:
    _assert_callback_actual_response_is_consumer_readable(cors_contract_client, 422)


def test_callback_actual_post_without_origin_has_no_cors_headers(
    cors_contract_client: TestClient,
) -> None:
    response = cors_contract_client.post("/api/callback_requests")
    assert response.status_code == 201
    assert "access-control-allow-origin" not in response.headers


def test_cms_callback_actual_post_is_public_but_strict_cors(
    cors_contract_client: TestClient,
) -> None:
    response = cors_contract_client.post(
        "/api/callback_requests", headers={"Origin": CMS_ORIGIN}
    )
    assert response.status_code == 201
    assert response.headers["access-control-allow-origin"] == CMS_ORIGIN
    assert response.headers["access-control-allow-credentials"] == "true"
    assert "Origin" in response.headers["vary"]


def test_cms_callback_preflight_keeps_strict_priority(
    cors_contract_client: TestClient,
) -> None:
    response = _preflight(
        cors_contract_client,
        origin=CMS_ORIGIN,
        requested_headers="Content-Type, X-Equestrian-Service-Key",
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == CMS_ORIGIN
    assert response.headers["access-control-allow-credentials"] == "true"
    assert "Origin" in response.headers["vary"]


@pytest.mark.parametrize(
    "path",
    [
        "/api/callback_requests/42/status",
        "/api/service/callback_requests/42/status",
    ],
)
def test_foreign_origin_callback_patches_remain_strict(
    cors_contract_client: TestClient,
    path: str,
) -> None:
    response = cors_contract_client.patch(path, headers={"Origin": FOREIGN_ORIGIN})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
