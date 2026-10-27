"""UT-SEOP-05..10: HTTP boundary and real use-case, without live peer."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from clients.seo_service.schemas import BlacklistItemInDto
from core.entities.user import UserScope
from core.exceptions.base import ClientError, ConflictError, NotFoundError
from core.protocols.seo_service import (
    SeoServiceClientProtocol,
    SeoServiceUnavailableError,
)
from core.schemas.users import UserOutDto
from core.services.seo_proxy import SeoProxyService
from depends.services import get_current_user, get_seo_proxy_service
from main import app

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

ITEM_ID = uuid4()
SETTINGS = ["blacklisted-query-params", "blacklisted-hashes"]
ROUTES = [
    ("GET", "/search-queries", "list_search_queries"),
    ("GET", "/pages", "list_pages"),
] + [
    (
        method,
        "/page-normalization/" + suffix + detail,
        operation + "_" + suffix.replace("-", "_"),
    )
    for suffix in SETTINGS
    for method, detail, operation in [
        ("GET", "", "list"),
        ("POST", "", "create"),
        ("PATCH", f"/{ITEM_ID}", "update"),
        ("DELETE", f"/{ITEM_ID}", "delete"),
    ]
]


def actor(*scopes):
    return UserOutDto(
        id=uuid4(),
        equestrian_id=uuid4(),
        username="seo-admin",
        created_at=datetime.now(UTC),
        scopes=[
            UserScope(scope_name=scope, scope_description="test") for scope in scopes
        ],
    )


@pytest.fixture
def boundary():
    user = actor("ADMIN")
    peer = AsyncMock(spec=SeoServiceClientProtocol)
    item = {
        "id": str(ITEM_ID),
        "value": "utm_source",
        "created_at": "2026-01-01T00:00:00Z",
    }
    for method, path, operation in ROUTES:
        if method == "DELETE":
            payload = None
        elif method == "GET":
            field = (
                "query"
                if path == "/search-queries"
                else "page"
                if path == "/pages"
                else "value"
            )
            payload = {
                "items": [
                    {
                        **{k: v for k, v in item.items() if k != "value"},
                        field: item["value"],
                    }
                ],
                "total": 1,
            }
        else:
            payload = item
        if path in {"/pages", "/search-queries"}:
            payload["metrics_table"] = METRICS_TABLE
        getattr(peer, operation).return_value = payload
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_seo_proxy_service] = lambda: SeoProxyService(peer)
    try:
        yield TestClient(app), peer, user
    finally:
        app.dependency_overrides.clear()


def request(boundary, method, path, **kwargs):
    if method in {"POST", "PATCH"}:
        kwargs.setdefault("json", {"value": "utm_source"})
    return boundary[0].request(method, "/api/seo" + path, **kwargs)


@pytest.mark.parametrize("method,path,_", ROUTES)
def test_ut05_anonymous_denied_before_peer(boundary, method, path, _):
    del app.dependency_overrides[get_current_user]
    assert request(boundary, method, path).status_code == 401
    assert not boundary[1].mock_calls


@pytest.mark.parametrize(
    "scopes",
    [(), ("SUPERUSER",), ("DEVELOPER",), ("SUPERUSER", "DEVELOPER"), ("USER_MANAGER",)],
)
@pytest.mark.parametrize("method,path,_", ROUTES)
def test_ut06_non_admin_denied_before_peer(boundary, scopes, method, path, _):
    app.dependency_overrides[get_current_user] = lambda: actor(*scopes)
    assert request(boundary, method, path).status_code == 403
    assert not boundary[1].mock_calls


@pytest.mark.parametrize("method,path,operation", ROUTES)
def test_ut07_admin_success(boundary, method, path, operation):
    response = request(boundary, method, path)
    assert response.status_code == (
        204 if method == "DELETE" else 201 if method == "POST" else 200
    )
    call = getattr(boundary[1], operation)
    call.assert_awaited_once()
    expected = {"equestrian_id": boundary[2].equestrian_id}
    if path in {"/search-queries", "/pages"}:
        expected.update(search=None, ordering=None, limit=20, offset=0)
    if path in {"/pages", "/search-queries"}:
        expected.update(mode=None, metric=None, date_from=None, date_to=None)
    if method in {"PATCH", "DELETE"}:
        expected["item_id"] = ITEM_ID
    if method in {"POST", "PATCH"}:
        expected["data"] = BlacklistItemInDto(value="utm_source")
    assert call.await_args.kwargs == expected
    if method == "DELETE":
        assert response.content == b""
    else:
        assert response.json() == call.return_value


@pytest.mark.parametrize(
    "method,path,_", [row for row in ROUTES if row[0] in {"PATCH", "DELETE"}]
)
def test_ut08_malformed_item_id(boundary, method, path, _):
    path = path.rsplit("/", 1)[0] + "/not-a-uuid"
    assert request(boundary, method, path).status_code == 400
    assert not boundary[1].mock_calls


@pytest.mark.parametrize(
    "body",
    [
        {},
        [],
        None,
        {"value": None},
        {"value": 1},
        {"value": "x", "equestrian_id": str(uuid4())},
    ],
)
@pytest.mark.parametrize(
    "method,path,_", [row for row in ROUTES if row[0] in {"POST", "PATCH"}]
)
def test_ut08_invalid_body(boundary, method, path, _, body):
    assert request(boundary, method, path, json=body).status_code == 400
    assert not boundary[1].mock_calls


@pytest.mark.parametrize(
    "method,path,_", [row for row in ROUTES if row[0] in {"POST", "PATCH"}]
)
def test_ut08_malformed_json(boundary, method, path, _):
    response = boundary[0].request(
        method,
        "/api/seo" + path,
        content="{broken",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400
    assert not boundary[1].mock_calls


@pytest.mark.parametrize(
    "path,operation",
    [("/search-queries", "list_search_queries"), ("/pages", "list_pages")],
)
@pytest.mark.parametrize(
    "params,expected",
    [
        ({"limit": "bad"}, None),
        ({"offset": "bad"}, None),
        ({"limit": 500, "offset": -1}, (100, 0)),
        ({"limit": 0}, (1, 0)),
        ({}, (20, 0)),
        ({"limit": 2, "offset": 3}, (2, 3)),
    ],
)
def test_ut08_list_parameters(boundary, path, operation, params, expected):
    response = request(
        boundary,
        "GET",
        path,
        params={**params, "search": "лошад", "ordering": "-created_at"},
    )
    if expected is None:
        assert response.status_code == 400
        assert not boundary[1].mock_calls
    else:
        assert response.status_code == 200
        getattr(boundary[1], operation).assert_awaited_once_with(
            equestrian_id=boundary[2].equestrian_id,
            search="лошад",
            ordering="-created_at",
            limit=expected[0],
            offset=expected[1],
            **(
                dict(mode=None, metric=None, date_from=None, date_to=None)
                if path in {"/pages", "/search-queries"}
                else {}
            ),
        )


@pytest.mark.parametrize("method,path,operation", ROUTES)
def test_ut09_client_tenant_is_ignored(boundary, method, path, operation):
    foreign = str(uuid4())
    response = request(
        boundary,
        method,
        path,
        params={"equestrian_id": foreign},
        headers={"X-Equestrian-Id": foreign},
    )
    assert response.status_code in {200, 201, 204}
    assert (
        getattr(boundary[1], operation).await_args.kwargs["equestrian_id"]
        == boundary[2].equestrian_id
    )


@pytest.mark.parametrize(
    "method,path,operation", [row for row in ROUTES if row[0] in {"PATCH", "DELETE"}]
)
def test_ut09_foreign_or_missing_item(boundary, method, path, operation):
    getattr(boundary[1], operation).side_effect = NotFoundError("Элемент не найден")
    response = request(boundary, method, path)
    assert response.status_code == 404
    assert response.json() == {"detail": "Элемент не найден"}
    assert (
        getattr(boundary[1], operation).await_args.kwargs["equestrian_id"]
        == boundary[2].equestrian_id
    )


@pytest.mark.parametrize("method,path,operation", ROUTES)
@pytest.mark.parametrize("unavailable", [False, True])
def test_ut10_downstream_errors(boundary, method, path, operation, unavailable):
    error = (
        SeoServiceUnavailableError() if unavailable else ClientError("Запрос отклонён")
    )
    error.__cause__ = RuntimeError("private peer detail")
    getattr(boundary[1], operation).side_effect = error
    response = request(boundary, method, path)
    assert response.status_code == (502 if unavailable else 400)
    assert response.json() == {
        "detail": "SEO service unavailable" if unavailable else "Запрос отклонён"
    }
    assert "private peer detail" not in response.text


@pytest.mark.parametrize(
    "method,path,operation", [row for row in ROUTES if row[0] in {"POST", "PATCH"}]
)
def test_ut10_conflict(boundary, method, path, operation):
    getattr(boundary[1], operation).side_effect = ConflictError(
        "Элемент уже существует"
    )
    response = request(boundary, method, path)
    assert response.status_code == 409
    assert response.json() == {"detail": "Элемент уже существует"}


@pytest.mark.parametrize(
    "path,operation",
    [("/search-queries", "list_search_queries"), ("/pages", "list_pages")],
)
def test_ut08_unknown_ordering_is_forwarded_and_rejected(boundary, path, operation):
    getattr(boundary[1], operation).side_effect = ClientError("Некорректная сортировка")
    assert (
        request(boundary, "GET", path, params={"ordering": "unknown"}).status_code
        == 400
    )
    if path == "/search-queries":
        assert not boundary[1].mock_calls
    else:
        assert (
            getattr(boundary[1], operation).await_args.kwargs["ordering"] == "unknown"
        )


@pytest.mark.parametrize(
    "params",
    [
        {"mode": "quarter"},
        {"metric": "x"},
        {"date_from": "abc"},
        {"date_from": "2026-10-01"},
        {"date_to": "2026-10-01"},
        {"date_from": "2026-10-02", "date_to": "2026-10-01"},
    ],
)
def test_ut_bp04_invalid_metrics_before_peer(boundary, params):
    assert request(boundary, "GET", "/pages", params=params).status_code == 400
    assert not boundary[1].mock_calls


@pytest.mark.parametrize(
    "scopes,status", [(None, 401), (("SUPERUSER", "DEVELOPER"), 403)]
)
def test_ut_bp01_02_metrics_access(boundary, scopes, status):
    if scopes is None:
        del app.dependency_overrides[get_current_user]
    else:
        app.dependency_overrides[get_current_user] = lambda: actor(*scopes)
    assert (
        request(boundary, "GET", "/pages", params={"mode": "month"}).status_code
        == status
    )
    assert not boundary[1].mock_calls


def test_ut_bp03_metrics_forwarded_without_calendar_rules(boundary):
    from datetime import date

    params = dict(
        mode="week",
        metric="bounce_rate",
        date_from="2090-01-01",
        date_to="2099-10-26",
        ordering="-metric:2090-01-01",
    )
    response = request(boundary, "GET", "/pages", params=params)
    assert response.status_code == 200
    assert response.json()["metrics_table"] == METRICS_TABLE
    kwargs = boundary[1].list_pages.await_args.kwargs
    assert kwargs == {
        **params,
        "date_from": date(2090, 1, 1),
        "date_to": date(2099, 10, 26),
        "equestrian_id": boundary[2].equestrian_id,
        "search": None,
        "limit": 20,
        "offset": 0,
    }


def test_ut_bp06_extensions_survive_api_serialization(boundary):
    from copy import deepcopy
    from clients.seo_service.schemas import PagesOutDto

    table = deepcopy(METRICS_TABLE)
    table["future_table"] = {"nested": True}
    column = table["columns"][0]
    column["future_column"] = [1, 2]
    column["values"][str(ITEM_ID)] = {"text": "12", "value": 12, "tone": "positive"}
    payload = {"items": [], "total": 0, "metrics_table": table}
    boundary[1].list_pages.return_value = PagesOutDto.model_validate(payload)
    assert request(boundary, "GET", "/pages").json() == payload


@pytest.mark.parametrize(
    "params",
    [
        {"mode": "quarter"},
        {"metric": "secret"},
        {"date_from": "abc"},
        {"date_from": "20261001", "date_to": "2026-10-02"},
        {"date_from": "2026-02-30", "date_to": "2026-03-01"},
        {"date_from": "2026-10-01"},
        {"date_to": "2026-10-01"},
        {"date_from": "2026-10-02", "date_to": "2026-10-01"},
        *[
            {"ordering": value}
            for value in [
                "",
                "page",
                "query,-created_at",
                "+query",
                "--query",
                "metric:",
                "metric:2026-02-30",
                "metric:20261001",
            ]
        ],
    ],
)
def test_ut_gw02_invalid_before_peer(boundary, params):
    assert request(boundary, "GET", "/search-queries", params=params).status_code == 400
    assert not boundary[1].mock_calls


@pytest.mark.parametrize(
    "ordering",
    [
        "query",
        "-query",
        "created_at",
        "-created_at",
        "metric:2000-01-01",
        "-metric:2099-01-01",
    ],
)
def test_ut_gw02_metrics_forwarded_no_period_resolution(boundary, ordering):
    from datetime import date

    params = dict(
        mode="year",
        metric="page_depth",
        date_from="2090-01-01",
        date_to="2099-10-26",
        ordering=ordering,
    )
    assert request(boundary, "GET", "/search-queries", params=params).status_code == 200
    boundary[1].list_search_queries.assert_awaited_once_with(
        **{**params, "date_from": date(2090, 1, 1), "date_to": date(2099, 10, 26)},
        equestrian_id=boundary[2].equestrian_id,
        search=None,
        limit=20,
        offset=0,
    )


@pytest.mark.parametrize(
    "kind",
    [
        "missing",
        "null",
        "column",
        "500",
        "404",
        "409",
        "302",
        "timeout",
        "connect",
        "400",
        "extras",
    ],
)
def test_ut_gw01_02_real_client_boundary(boundary, kind):
    from copy import deepcopy
    import httpx
    from clients.seo_service.client import SeoServiceClient

    payload = {"items": [], "total": 0, "metrics_table": deepcopy(METRICS_TABLE)}
    if kind == "missing":
        del payload["metrics_table"]
    elif kind == "null":
        payload["metrics_table"] = None
    elif kind == "column":
        del payload["metrics_table"]["columns"][0]["key"]
    elif kind == "extras":
        table = payload["metrics_table"]
        for node in [table, table["period"], table["metric"], table["columns"][0]]:
            node["future"] = {"nested": [True, 12]}
        table["columns"][0]["values"][str(ITEM_ID)] = {
            "text": "0",
            "value": 0,
            "future": [1],
        }

    calls = []

    def handler(req):
        calls.append(req)
        assert req.headers["X-Equestrian-Id"] == str(boundary[2].equestrian_id)
        assert "cookie" not in req.headers
        assert "authorization" not in req.headers
        assert "equestrian_id" not in req.url.params
        if kind == "timeout":
            raise httpx.ReadTimeout("private-peer-secret", request=req)
        if kind == "connect":
            raise httpx.ConnectError("private-peer-secret", request=req)
        if kind.isdigit():
            return httpx.Response(
                int(kind),
                json={
                    "detail": "Безопасный отказ"
                    if kind == "400"
                    else "private-peer-secret"
                },
            )
        return httpx.Response(200, json=payload)

    client = SeoServiceClient(
        base_url="http://peer.invalid", transport=httpx.MockTransport(handler)
    )
    app.dependency_overrides[get_seo_proxy_service] = lambda: SeoProxyService(client)
    response = request(
        boundary,
        "GET",
        "/search-queries",
        params={"equestrian_id": str(uuid4()), "mode": "week"},
        headers={
            "X-Equestrian-Id": str(uuid4()),
            "Authorization": "Bearer browser-private",
            "Cookie": "browser-private",
        },
    )
    assert len(calls) == 1
    assert response.status_code == (
        200 if kind == "extras" else 400 if kind == "400" else 502
    )
    if kind == "extras":
        assert response.json() == payload
    else:
        assert response.json() == {
            "detail": "Безопасный отказ" if kind == "400" else "SEO service unavailable"
        }
    assert "private-peer-secret" not in response.text
