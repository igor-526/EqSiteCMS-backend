"""UT-SEOP-01/02/04: контракт и безопасность изолированной HTTP-границы."""

import json
import logging
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError

from clients.seo_service.client import REJECTED_DETAIL, SeoServiceClient
from clients.seo_service.schemas import (
    BlacklistItemInDto,
    BlacklistItemOutDto,
    PageOutDto,
    PaginatedEntities,
    SearchQueryOutDto,
)
from core.exceptions.base import ClientError, ConflictError, NotFoundError
from core.protocols.seo_service import SeoServiceUnavailableError
from settings import Settings

TENANT, ITEM = uuid4(), uuid4()
BASE = {"id": str(ITEM), "created_at": "2026-06-01T12:00:00Z"}
BLACKLIST = {**BASE, "value": "utm_source"}
CASES = [
    (
        "list_search_queries",
        {"search": "лошадь", "ordering": "-query", "limit": 3, "offset": 2},
        "GET",
        "/api/search-queries",
        {"search": "лошадь", "ordering": "-query", "limit": "3", "offset": "2"},
        None,
        200,
        {"items": [{**BASE, "query": "лошадь"}], "total": 4},
    ),
    (
        "list_pages",
        {"search": "/site", "ordering": "page", "limit": 4, "offset": 1},
        "GET",
        "/api/pages",
        {"search": "/site", "ordering": "page", "limit": "4", "offset": "1"},
        None,
        200,
        {"items": [{**BASE, "page": "/site"}], "total": 5},
    ),
]
for name, path in [
    ("blacklisted_query_params", "blacklisted-query-params"),
    ("blacklisted_hashes", "blacklisted-hashes"),
]:
    for action, verb, status in [
        ("list", "GET", 200),
        ("create", "POST", 201),
        ("update", "PATCH", 200),
        ("delete", "DELETE", 204),
    ]:
        kwargs = {}
        if action in ("update", "delete"):
            kwargs["item_id"] = ITEM
        body = None
        if action in ("update", "create"):
            kwargs["data"] = BlacklistItemInDto(value="utm_source")
            body = {"value": "utm_source"}
        suffix = f"/{ITEM}" if action in ("update", "delete") else ""
        response = (
            None
            if action == "delete"
            else ({"items": [BLACKLIST], "total": 1} if action == "list" else BLACKLIST)
        )
        CASES.append(
            (
                f"{action}_{name}",
                kwargs,
                verb,
                f"/api/page-normalization/{path}{suffix}",
                {},
                body,
                status,
                response,
            )
        )


@pytest.mark.parametrize("method,kwargs,verb,path,query,body,status,payload", CASES)
async def test_ut_seop_01_all_operations(
    method, kwargs, verb, path, query, body, status, payload
):
    requests = []

    def handler(request):
        requests.append(request)
        assert request.method == verb
        assert request.url.host == "peer.invalid"
        assert request.url.path == path
        assert dict(request.url.params) == query
        assert (json.loads(request.content) if request.content else None) == body
        assert request.headers["X-Equestrian-Id"] == str(TENANT)
        for header in (
            "Cookie",
            "Authorization",
            "X-Service-Key",
            "X-Equestrian-Service-Key",
            "SEO_SERVICE_KEY",
        ):
            assert header not in request.headers
        assert request.extensions["timeout"] == dict.fromkeys(
            ("connect", "read", "write", "pool"), 10.0
        )
        return (
            httpx.Response(status, json=payload)
            if payload is not None
            else httpx.Response(status)
        )

    client = SeoServiceClient(
        base_url="http://peer.invalid/", transport=httpx.MockTransport(handler)
    )
    result = await getattr(client, method)(equestrian_id=TENANT, **kwargs)
    assert len(requests) == 1
    assert (result.model_dump(mode="json") if result is not None else None) == payload


@pytest.mark.parametrize("method", ["list_pages", "list_search_queries"])
async def test_ut_seop_01_optional_query_defaults(method):
    def handler(request):
        assert dict(request.url.params) == {"limit": "20", "offset": "0"}
        return httpx.Response(200, json={"items": [], "total": 0})

    await getattr(
        SeoServiceClient(
            base_url="http://peer.invalid", transport=httpx.MockTransport(handler)
        ),
        method,
    )(equestrian_id=TENANT)


@pytest.mark.parametrize(
    "payload,expected",
    [
        ({"detail": "Некорректное значение"}, "Некорректное значение"),
        ({"detail": "x" * 300}, "x" * 300),
        ({"detail": "x" * 301}, REJECTED_DETAIL),
        ({"detail": []}, REJECTED_DETAIL),
        ({}, REJECTED_DETAIL),
        (["error"], REJECTED_DETAIL),
        ({"detail": " "}, REJECTED_DETAIL),
        (None, REJECTED_DETAIL),
    ],
)
async def test_ut_seop_02_rejected(payload, expected):
    client = SeoServiceClient(
        base_url="http://peer.invalid",
        transport=httpx.MockTransport(
            lambda request: (
                httpx.Response(400, json=payload)
                if payload is not None
                else httpx.Response(400, content=b"not-json")
            )
        ),
    )
    with pytest.raises(ClientError) as exc:
        await client.list_pages(equestrian_id=TENANT)
    assert str(exc.value) == expected


@pytest.mark.parametrize("status,error", [(404, NotFoundError), (409, ConflictError)])
async def test_ut_seop_02_semantic_errors(status, error, caplog):
    client = SeoServiceClient(
        base_url="http://peer.invalid",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(status, json={"detail": "peer-private-body"})
        ),
    )
    with pytest.raises(error) as exc:
        await client.list_pages(equestrian_id=TENANT)
    assert "peer-private-body" not in str(exc.value) + caplog.text


@pytest.mark.parametrize(
    "kind",
    [
        "401",
        "500",
        "418",
        "201",
        "204",
        "redirect",
        "timeout",
        "connect",
        "json",
        "schema",
        "nested",
        "negative_total",
    ],
)
async def test_ut_seop_02_04_unavailable(kind, caplog):
    caplog.set_level(logging.DEBUG)

    def handler(request):
        if kind == "timeout":
            raise httpx.ReadTimeout("peer-private-body", request=request)
        if kind == "connect":
            raise httpx.ConnectError("peer-private-body", request=request)
        if kind.isdigit():
            return httpx.Response(int(kind), json={"detail": "peer-private-body"})
        if kind == "redirect":
            return httpx.Response(302, headers={"Location": "http://other.invalid"})
        if kind == "json":
            return httpx.Response(200, content=b"peer-private-body")
        if kind == "nested":
            return httpx.Response(
                200, json={"items": [{"page": "peer-private-body"}], "total": 1}
            )
        if kind == "negative_total":
            return httpx.Response(200, json={"items": [], "total": -1})
        return httpx.Response(200, json={"unexpected": "peer-private-body"})

    client = SeoServiceClient(
        base_url="http://peer.invalid", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(SeoServiceUnavailableError) as exc:
        await client.list_pages(equestrian_id=TENANT, search="private-search")
    assert str(exc.value) == "SEO service unavailable"
    assert exc.value.__suppress_context__ or exc.value.__context__ is None
    assert "peer-private-body" not in caplog.text
    assert "private-search" not in caplog.text
    assert "peer.invalid" not in str(exc.value)


async def test_ut_seop_04_httpx_logging_is_task_local(caplog):
    caplog.set_level(logging.INFO, logger="httpx")
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"items": [], "total": 0})
    )
    client = SeoServiceClient(base_url="http://peer.invalid", transport=transport)
    await client.list_pages(equestrian_id=TENANT, search="private-search")
    assert "private-search" not in caplog.text
    async with httpx.AsyncClient(transport=transport) as other:
        await other.get("http://other.invalid/public")
    assert "http://other.invalid/public" in caplog.text


@pytest.mark.parametrize(
    "schema,payload",
    [
        (
            PaginatedEntities[SearchQueryOutDto],
            {"items": [{**BASE, "query": "horse"}], "total": 1},
        ),
        (PaginatedEntities[PageOutDto], {"items": [{**BASE, "page": "/"}], "total": 1}),
        (PaginatedEntities[BlacklistItemOutDto], {"items": [BLACKLIST], "total": 1}),
    ],
)
def test_response_whitelists(schema, payload):
    contaminated = {
        **payload,
        "equestrian_id": str(TENANT),
        "items": [
            {
                **item,
                "equestrian_id": str(TENANT),
                "query_hash": "hidden",
                "page_hash": "hidden",
            }
            for item in payload["items"]
        ],
    }
    assert schema.model_validate(contaminated).model_dump(mode="json") == payload


def test_request_forbids_extra_and_wrong_types():
    for payload in (
        {"value": "x", "equestrian_id": str(TENANT)},
        {"value": 1},
        {},
        {"value": None},
    ):
        with pytest.raises(ValidationError):
            BlacklistItemInDto.model_validate(payload)


def test_ut_seop_04_settings_default_and_env(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("SEO_SERVICE_URL", raising=False)
    assert Settings().seo_service_url == "http://eqsitecms-seo-service:8000"
    monkeypatch.setenv("SEO_SERVICE_URL", "http://override.invalid:8123")
    assert Settings().seo_service_url == "http://override.invalid:8123"
