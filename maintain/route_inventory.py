from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI
from fastapi.routing import APIRoute


@dataclass(frozen=True)
class AccessRule:
    access_class: str
    roles: str
    tenant_selector: str
    owner_rule: str
    without_auth: str
    with_auth: str
    foreign: str
    validation: str
    tests: str


PUBLIC_POSTS = {
    ("POST", "/api/auth/register"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/refresh"),
    ("POST", "/api/callback_requests"),
    ("POST", "/api/emails/send-confirmation"),
    ("PATCH", "/api/emails/confirm"),
}
PROTECTED_GET_PREFIXES = (
    "/api/auth/me",
    "/api/news-cms",
    "/api/users/me",
    "/api/user-management/",
)
EMAIL_OWNER = {
    ("POST", "/api/emails"),
    ("PATCH", "/api/emails"),
    ("DELETE", "/api/emails/{user_id}"),
}
SERVICE_ROUTES = {("GET", "/api/service/users/")}


def classify(method: str, path: str) -> AccessRule:
    key = (method, path)
    tests = "tests/unit/api; tests/unit/depends/test_auth_dependencies.py"
    if path == "/health":
        return AccessRule(
            "public health",
            "all",
            "N/A",
            "N/A",
            "200",
            "200",
            "N/A",
            "N/A",
            "tests/unit/api/test_route_order.py",
        )
    if key in SERVICE_ROUTES:
        return AccessRule(
            "service API",
            "microservice",
            "N/A",
            "N/A",
            "401",
            "200 with X-Service-Key",
            "401",
            "400 malformed",
            "tests/unit/api/test_service_users_api.py",
        )
    if key in EMAIL_OWNER:
        success = "201" if method == "POST" else ("200" if method == "PATCH" else "204")
        return AccessRule(
            "protected owner write",
            "owner only",
            "actor cookie",
            "target user_id == actor.id; no role override",
            "401",
            success,
            "403 before lookup/downstream",
            "400 malformed/invalid; 404 missing; 409 different create",
            "tests/unit/api/test_email_proxy_api.py",
        )
    if key == ("POST", "/api/auth/refresh"):
        return AccessRule(
            "public auth exception",
            "refresh-cookie holder",
            "N/A",
            "self",
            "401 without refresh cookie",
            "200 with valid refresh cookie",
            "N/A",
            "400 malformed",
            tests,
        )
    if key in PUBLIC_POSTS:
        validation = (
            "400 malformed/invalid"
            if path.startswith("/api/emails/")
            else "400/422 by endpoint contract"
        )
        return AccessRule(
            "public write exception",
            "all",
            "body/host as applicable",
            "N/A",
            "success/domain status without access cookie",
            "same contract",
            "N/A",
            validation,
            tests,
        )
    if method == "GET" and path.startswith(PROTECTED_GET_PREFIXES):
        return AccessRule(
            "protected GET exception",
            "authenticated/scoped",
            "cookie tenant",
            "tenant/role scoped",
            "401",
            "200",
            "403 or tenant-scoped",
            "400 malformed",
            tests,
        )
    if method == "POST" and path == "/api/auth/logout":
        return AccessRule(
            "protected write",
            "authenticated",
            "cookie tenant",
            "self",
            "401",
            "200",
            "N/A",
            "400 malformed",
            tests,
        )
    if method == "GET":
        return AccessRule(
            "public read",
            "all",
            "X-Equestrian-Service-Key or CMS cookie",
            "tenant scoped",
            "401 missing/invalid selector",
            "200",
            "tenant isolated",
            "400 malformed",
            tests,
        )
    if method in {"POST", "PATCH", "DELETE"}:
        success = "201/200/204"
        return AccessRule(
            "protected write",
            "authenticated + endpoint scope",
            "CMS cookie tenant",
            "tenant scoped",
            "401",
            success,
            "403/404 without existence leak",
            "400 malformed/domain validation",
            tests,
        )
    raise AssertionError(f"Unclassified route: {method} {path}")


def inventory(app: FastAPI) -> list[tuple[str, str, AccessRule]]:
    rows = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
            rows.append((method, route.path, classify(method, route.path)))
    return sorted(rows, key=lambda row: (row[1], row[0]))


def render(app: FastAPI) -> str:
    rows = inventory(app)
    header = (
        "| method | path | access class | roles | tenant selector | owner rule | "
        "without auth | with auth | foreign | validation | tests |"
    )
    separator = "|---|---|---|---|---|---|---|---|---|---|---|"
    lines = [
        "# Generated backend route access inventory",
        "",
        "Generated from the registered FastAPI router graph. Do not edit manually.",
        "",
        f"Route entries: **{len(rows)}**",
        "",
        header,
        separator,
    ]
    for method, path, rule in rows:
        values = (
            method,
            f"`{path}`",
            rule.access_class,
            rule.roles,
            rule.tenant_selector,
            rule.owner_rule,
            rule.without_auth,
            rule.with_auth,
            rule.foreign,
            rule.validation,
            rule.tests,
        )
        lines.append(
            "| " + " | ".join(value.replace("|", "\\|") for value in values) + " |"
        )
    return "\n".join(lines) + "\n"


def write(app: FastAPI, destination: Path) -> None:
    destination.write_text(render(app), encoding="utf-8")
