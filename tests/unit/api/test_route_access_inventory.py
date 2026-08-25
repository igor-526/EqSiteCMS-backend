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

    assert registered == 104
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
