from pathlib import Path

from fastapi.routing import APIRoute

from main import app
from maintain.route_inventory import inventory, render


def test_every_registered_api_route_has_exactly_one_access_classification() -> None:
    registered = sum(
        len(route.methods - {"HEAD", "OPTIONS"})
        for route in app.routes
        if isinstance(route, APIRoute)
    )
    rows = inventory(app)

    assert registered == 130
    assert len(rows) == registered
    assert len({(method, path) for method, path, _ in rows}) == registered
    assert all(rule.access_class and rule.tests for _, _, rule in rows)


def test_generated_route_inventory_is_current() -> None:
    artifact = Path("docs/backend-route-inventory.md")
    assert artifact.read_text(encoding="utf-8") == render(app)


def test_email_and_policy_exceptions_are_explicitly_classified() -> None:
    rules = {(method, path): rule for method, path, rule in inventory(app)}

    assert rules[("POST", "/api/emails")].access_class == "protected owner write"
    assert rules[("GET", "/api/emails/me")].access_class == "protected GET exception"
    assert rules[("GET", "/api/vks/me")].access_class == "protected GET exception"
    assert rules[("GET", "/api/vks/bot-info")].access_class == "public read"
    assert (
        rules[("POST", "/api/vks/issue-confirmation")].access_class
        == "protected owner write"
    )
    assert (
        rules[("DELETE", "/api/vks/{user_id}")].access_class == "protected owner write"
    )
    assert (
        rules[("GET", "/api/notification-settings")].access_class
        == "protected GET exception"
    )
    assert (
        rules[
            (
                "PATCH",
                "/api/notification-settings/{event_code}/{channel_code}",
            )
        ].roles
        == "ADMIN or SUPERUSER"
    )
    assert (
        rules[("PATCH", "/api/emails/confirm")].access_class == "public write exception"
    )
    assert rules[("GET", "/api/service/users/")].access_class == "service API"
    assert (
        rules[("GET", "/api/user-management/users")].access_class
        == "protected GET exception"
    )
    assert rules[("GET", "/api/horses")].without_auth == "401 missing/invalid selector"
    assert (
        rules[("GET", "/api/callback_requests")].access_class
        == "protected GET exception"
    )
    assert rules[("GET", "/api/callback_requests/statuses")].without_auth == "200"
    assert (
        rules[("PATCH", "/api/service/callback_requests/{id}/status")].access_class
        == "service API"
    )


def test_ut_yx23_yandex_access_matrix_is_explicitly_classified() -> None:
    rows = [
        (method, path, rule)
        for method, path, rule in inventory(app)
        if path.startswith("/api/yandex/")
    ]
    assert {(method, path) for method, path, _ in rows} == {
        ("GET", "/api/yandex/auth/link"),
        ("POST", "/api/yandex/auth/code"),
        ("GET", "/api/yandex/accounts"),
        ("DELETE", "/api/yandex/accounts/{account_id}"),
        ("GET", "/api/yandex/metrica/counters"),
        ("GET", "/api/yandex/metrica/connection"),
        ("POST", "/api/yandex/metrica/connection"),
        ("DELETE", "/api/yandex/metrica/connection"),
    }
    for method, _, rule in rows:
        assert rule.access_class == (
            "protected GET exception" if method == "GET" else "protected write"
        )
        assert rule.roles == "ADMIN only; no SUPERUSER/DEVELOPER override"
        assert rule.without_auth == "401"
        assert "403 before downstream" in rule.with_auth
        assert "from session" in rule.tenant_selector
        assert rule.tests == "tests/unit/api/test_yandex_proxy_api.py"


def test_yandex_inventory_outcomes_are_route_specific() -> None:
    rules = {(method, path): rule for method, path, rule in inventory(app)}
    account_routes = {
        ("DELETE", "/api/yandex/accounts/{account_id}"),
        ("GET", "/api/yandex/metrica/counters"),
        ("POST", "/api/yandex/metrica/connection"),
    }
    for key, rule in rules.items():
        if not key[1].startswith("/api/yandex/"):
            continue
        assert ("404 foreign/missing account" in rule.foreign) == (
            key in account_routes
        )
        assert ("state mismatch" in rule.foreign) == (
            key == ("POST", "/api/yandex/auth/code")
        )
        assert "peer 400; 502 unavailable downstream" in rule.validation
    expected_validation = {
        ("GET", "/api/yandex/auth/link"): "peer 400; 502 unavailable downstream",
        (
            "POST",
            "/api/yandex/auth/code",
        ): "400 missing/blank code/state or malformed body",
        (
            "GET",
            "/api/yandex/accounts",
        ): "400 nonnumeric limit/offset; limit/offset clamped",
        ("DELETE", "/api/yandex/accounts/{account_id}"): "400 malformed account_id",
        (
            "GET",
            "/api/yandex/metrica/counters",
        ): "400 missing/malformed account_id or nonnumeric limit/offset; limit/offset clamped",
        (
            "GET",
            "/api/yandex/metrica/connection",
        ): "peer 400; 502 unavailable downstream",
        (
            "POST",
            "/api/yandex/metrica/connection",
        ): "400 missing/malformed body/account UUID; counter_id must be 1..31 ASCII digits (number coerced to string)",
        (
            "DELETE",
            "/api/yandex/metrica/connection",
        ): "peer 400; 502 unavailable downstream",
    }
    for key, expected in expected_validation.items():
        assert rules[key].validation.startswith(expected)
    assert rules[("GET", "/api/yandex/metrica/connection")].with_auth.startswith(
        "200 counter or null;"
    )
    assert rules[("DELETE", "/api/yandex/metrica/connection")].with_auth.startswith(
        "204 idempotent;"
    )


def test_ut_seop11_seo_access_matrix_is_explicitly_classified() -> None:
    rows = [row for row in inventory(app) if row[1].startswith("/api/seo/")]
    expected = {("GET", "/api/seo/search-queries"), ("GET", "/api/seo/pages")}
    for suffix in ("blacklisted-query-params", "blacklisted-hashes"):
        path = "/api/seo/page-normalization/" + suffix
        expected.update(
            {
                ("GET", path),
                ("POST", path),
                ("PATCH", path + "/{item_id}"),
                ("DELETE", path + "/{item_id}"),
            }
        )
    assert len(rows) == 10
    assert {(method, path) for method, path, _ in rows} == expected
    for method, path, rule in rows:
        assert rule.access_class == (
            "protected GET exception" if method == "GET" else "protected write"
        )
        assert rule.roles == "ADMIN only; no SUPERUSER/DEVELOPER override"
        assert rule.without_auth == "401"
        assert "403 before downstream" in rule.with_auth
        assert "from session" in rule.tenant_selector
        assert "client selector ignored" in rule.tenant_selector
        assert rule.tests == "tests/unit/api/test_seo_proxy_api.py"
        assert rule.with_auth.startswith(
            "201;" if method == "POST" else "204;" if method == "DELETE" else "200;"
        )
        assert "502" in rule.validation
        assert ("404 foreign/missing item" in rule.foreign) == ("{item_id}" in path)
        assert ("409 duplicate" in rule.validation) == (method in {"POST", "PATCH"})
        assert ("400 malformed item_id" in rule.validation) == ("{item_id}" in path)
        assert ("400 malformed body/value" in rule.validation) == (
            method in {"POST", "PATCH"}
        )
        assert ("nonnumeric limit/offset" in rule.validation) == (
            path in {"/api/seo/search-queries", "/api/seo/pages"}
        )


def test_news_access_matrix_is_explicitly_classified() -> None:
    rules = {(method, path): rule for method, path, rule in inventory(app)}
    for path in ("/api/news", "/api/news/by-slug/{slug}", "/api/news/{news_id}"):
        rule = rules[("GET", path)]
        assert rule.access_class == "public read"
        assert "required even with cookie" in rule.tenant_selector
        assert "missing/invalid selector 401" in rule.without_auth
        assert "no privileged bypass" in rule.with_auth
    for method, path in (
        ("GET", "/api/news-cms"),
        ("POST", "/api/news"),
        ("PATCH", "/api/news/{news_id}"),
        ("DELETE", "/api/news/{news_id}"),
    ):
        rule = rules[(method, path)]
        assert rule.roles == "SUPERUSER or ADMIN or DEVELOPER"
        assert "no scope 403" in rule.with_auth
        assert "400 missing/foreign" in rule.foreign


def test_ut_gw02_pages_and_queries_metrics_validation() -> None:
    rules = {(method, path): rule for method, path, rule in inventory(app)}
    metrics_validation = (
        "400 unknown mode/metric, malformed date, unpaired dates or "
        "date_from > date_to before downstream"
    )
    for path in ("/api/seo/pages", "/api/seo/search-queries"):
        rule = rules[("GET", path)]
        assert (metrics_validation in rule.validation) == (
            path in {"/api/seo/pages", "/api/seo/search-queries"}
        )
        assert (metrics_validation in rule.with_auth) == (
            path in {"/api/seo/pages", "/api/seo/search-queries"}
        )
