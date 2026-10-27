"""UT-SEOP-01/02/04: контракт и безопасность изолированной HTTP-границы."""

import json
import logging
from typing import Any
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

METRICS_TABLE = {
    "version": 1,
    "row_key": "id",
    "period": {
        "mode": "week",
        "date_from": "2026-10-19",
        "date_to": "2026-10-26",
        "requested_date_from": None,
        "requested_date_to": None,
        "defaulted": True,
        "adjusted": False,
        "clamped": False,
        "today": "2026-10-26",
    },
    "metric": {"key": "visits", "title": "Визиты", "value_type": "integer"},
    "ordering": None,
    "columns": [
        {
            "key": "metric:2026-10-19",
            "title": "19–25 окт",
            "hint": None,
            "sortable": True,
            "value_type": "integer",
            "align": "right",
            "empty_text": "—",
            "values": {},
        }
    ],
}

TENANT, ITEM = uuid4(), uuid4()
BASE = {"id": str(ITEM), "created_at": "2026-06-01T12:00:00Z"}
BLACKLIST = {**BASE, "value": "utm_source"}
CASES: list[
    tuple[
        str, dict[str, Any], str, str, dict[str, str], dict[str, str] | None, int, Any
    ]
] = [
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
        {
            "items": [{**BASE, "page": "/site"}],
            "total": 5,
            "metrics_table": METRICS_TABLE,
        },
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
        kwargs: dict[str, Any] = {}
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
        return httpx.Response(
            200,
            json={
                "items": [],
                "total": 0,
                **({"metrics_table": METRICS_TABLE} if method == "list_pages" else {}),
            },
        )

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
        "502",
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
        lambda request: httpx.Response(
            200, json={"items": [], "total": 0, "metrics_table": METRICS_TABLE}
        )
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


@pytest.mark.parametrize("invalid", ["missing_table", "missing_key"])
async def test_ut_bp05_invalid_metrics_payload(invalid):
    from copy import deepcopy

    payload = {"items": [], "total": 0, "metrics_table": deepcopy(METRICS_TABLE)}
    if invalid == "missing_table":
        del payload["metrics_table"]
    else:
        del payload["metrics_table"]["columns"][0]["key"]
    client = SeoServiceClient(
        base_url="http://peer.invalid",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload)),
    )
    with pytest.raises(SeoServiceUnavailableError):
        await client.list_pages(equestrian_id=TENANT)


async def test_ut_bp03_06_metrics_wire_and_extensions():
    from copy import deepcopy
    from datetime import date
    from core.schemas.metrics_table import MetricsMode, MetricsMetric

    table = deepcopy(METRICS_TABLE)
    table["future_table"] = {"nested": [1, 2]}
    table["period"]["future_period"] = True
    table["metric"]["future_metric"] = "new"
    column = table["columns"][0]
    column["future_column"] = "new"
    column["value_type"] = "future_type"
    column["values"][str(ITEM)] = {"text": "12", "value": 12, "tone": "positive"}
    payload = {"items": [{**BASE, "page": "/"}], "total": 1, "metrics_table": table}

    def handler(request):
        assert dict(request.url.params) == {
            "limit": "20",
            "offset": "0",
            "mode": "week",
            "metric": "bounce_rate",
            "date_from": "2026-09-01",
            "date_to": "2026-10-26",
            "ordering": "-metric:2026-10-19",
        }
        assert request.headers["X-Equestrian-Id"] == str(TENANT)
        assert "Cookie" not in request.headers
        assert "Authorization" not in request.headers
        return httpx.Response(200, json=payload)

    client = SeoServiceClient(
        base_url="http://peer.invalid", transport=httpx.MockTransport(handler)
    )
    result = await client.list_pages(
        equestrian_id=TENANT,
        mode=MetricsMode.WEEK,
        metric=MetricsMetric.BOUNCE_RATE,
        date_from=date(2026, 9, 1),
        date_to=date(2026, 10, 26),
        ordering="-metric:2026-10-19",
    )
    assert result.model_dump(mode="json", exclude_unset=True) == payload
