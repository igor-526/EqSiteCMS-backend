"""UT-BE-08..12: real HTTP, dependencies, JWT/AuthService and NewsService."""

from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from core.entities.equestrian import Equestrian
from core.entities.news import News
from core.entities.user import User, UserScope
from depends.repositories import (
    get_equestrian_repository,
    get_news_repository,
    get_photo_repository,
    get_user_repository,
)
from main import app
from utils.security import Security


class Harness:
    def __init__(self) -> None:
        self.tenant = Equestrian(name="Public", service_key="public-selector")
        self.other = Equestrian(name="Other", service_key="other-selector")
        self.user = User(
            username="admin", password="unused", equestrian_id=self.other.id
        )
        self.repo = AsyncMock()
        self.users = AsyncMock()
        self.tenants = AsyncMock()
        self.photos = AsyncMock()
        self.users.get_by_username.return_value = self.user
        self.users.get_user_scopes.return_value = [
            UserScope(scope_name="ADMIN", scope_description="Admin")
        ]
        self.tenants.get_by_service_key.side_effect = lambda key: {
            self.tenant.service_key: self.tenant,
            self.other.service_key: self.other,
        }.get(key)
        self.item = News(
            name="Published",
            slug="published-stable",
            content="<p>Full</p>",
            published_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            equestrian_id=self.tenant.id,
        )
        self.repo.get_public_by_id.side_effect = self.public_by_id
        self.repo.get_public_by_slug.side_effect = self.public_by_slug
        self.repo.get_public_filtered.side_effect = self.public_list
        self.repo.get_by_id.side_effect = self.by_id
        self.repo.get_cms_filtered.side_effect = self.cms_list
        self.repo.get_news_photos.return_value = []
        self.repo.create.side_effect = lambda item: item
        self.repo.update.side_effect = lambda item: item
        self.client = TestClient(app)

    def visible(self, tenant: UUID) -> bool:
        return (
            self.item.equestrian_id == tenant
            and not self.item.is_deleted
            and self.item.published_at <= datetime.now(timezone.utc)
        )

    async def public_by_id(self, news_id: UUID, *, equestrian_id: UUID) -> News | None:
        return (
            self.item
            if news_id == self.item.id and self.visible(equestrian_id)
            else None
        )

    async def public_by_slug(self, slug: str, *, equestrian_id: UUID) -> News | None:
        return (
            self.item
            if slug == self.item.slug and self.visible(equestrian_id)
            else None
        )

    async def public_list(
        self, *, equestrian_id: UUID, **_: object
    ) -> tuple[list[News], int]:
        return ([self.item], 1) if self.visible(equestrian_id) else ([], 0)

    async def by_id(self, news_id: UUID, *, equestrian_id: UUID) -> News | None:
        return (
            self.item
            if news_id == self.item.id and equestrian_id == self.item.equestrian_id
            else None
        )

    async def cms_list(
        self, *, equestrian_id: UUID, **_: object
    ) -> tuple[list[News], int]:
        return ([self.item], 1) if equestrian_id == self.item.equestrian_id else ([], 0)

    def login(self) -> None:
        self.client.cookies.set(
            "access_token", Security().create_access_token(self.user.username)
        )
        assert self.client.get("/api/news-cms").status_code == 200
        self.repo.reset_mock()

    def paths(self) -> list[str]:
        return [
            "/api/news",
            f"/api/news/{self.item.id}",
            f"/api/news/by-slug/{self.item.slug}",
        ]

    def protected(self, method: str, payload: dict | None = None):
        path = "/api/news-cms" if method == "GET" else "/api/news"
        if method in {"PATCH", "DELETE"}:
            path += f"/{self.item.id}"
        if payload is None and method in {"POST", "PATCH"}:
            payload = {
                "name": "Updated",
                "content": "<p>Old CMS payload</p>",
                "published_at": "2020-01-01T00:00:00Z",
            }
        return self.client.request(method, path, json=payload)


@pytest.fixture
def h() -> Iterator[Harness]:
    harness = Harness()
    overrides = {
        get_equestrian_repository: lambda: harness.tenants,
        get_user_repository: lambda: harness.users,
        get_news_repository: lambda: harness.repo,
        get_photo_repository: lambda: harness.photos,
    }
    app.dependency_overrides.update(overrides)
    try:
        yield harness
    finally:
        for dependency in overrides:
            app.dependency_overrides.pop(dependency)
        harness.client.close()


@pytest.mark.parametrize("authenticated", [False, True])
def test_public_news_selector_dto(h: Harness, authenticated: bool) -> None:
    if authenticated:
        h.login()
    responses = [
        h.client.get(path, headers={"X-Equestrian-Service-Key": h.tenant.service_key})
        for path in h.paths()
    ]
    assert [r.status_code for r in responses] == [200, 200, 200]
    listing, by_id, by_slug = [r.json() for r in responses]
    assert by_id == by_slug
    assert set(by_id) == {
        "id",
        "slug",
        "name",
        "snippet",
        "published_at",
        "photos",
        "content",
    }
    assert listing["items"] == [{k: v for k, v in by_id.items() if k != "content"}]
    h.repo.get_public_by_id.assert_awaited_once_with(
        h.item.id, equestrian_id=h.tenant.id
    )
    h.repo.get_public_by_slug.assert_awaited_once_with(
        h.item.slug, equestrian_id=h.tenant.id
    )


@pytest.mark.parametrize("authenticated", [False, True])
@pytest.mark.parametrize("selector", [None, "", "   ", "invalid"])
def test_public_news_selector_401(
    h: Harness, authenticated: bool, selector: str | None
) -> None:
    if authenticated:
        h.login()
    headers = {} if selector is None else {"X-Equestrian-Service-Key": selector}
    for path in h.paths():
        assert h.client.get(path, headers=headers).status_code == 401
    h.repo.get_public_filtered.assert_not_awaited()
    h.repo.get_public_by_id.assert_not_awaited()
    h.repo.get_public_by_slug.assert_not_awaited()


@pytest.mark.parametrize("authenticated", [False, True])
@pytest.mark.parametrize("hidden", ["future", "deleted", "foreign", "missing"])
def test_public_news_no_privileged_bypass(
    h: Harness, authenticated: bool, hidden: str
) -> None:
    if authenticated:
        h.login()
    paths = h.paths()
    if hidden == "future":
        h.item.published_at = datetime.now(timezone.utc) + timedelta(days=1)
    elif hidden == "deleted":
        h.item.is_deleted = True
    elif hidden == "foreign":
        h.item.equestrian_id = h.other.id
    else:
        h.item.id = uuid4()
        h.item.slug = "different"
    headers = {"X-Equestrian-Service-Key": h.tenant.service_key}
    for path in paths[1:]:
        assert h.client.get(path, headers=headers).status_code == 404
    if hidden != "missing":
        assert h.client.get(paths[0], headers=headers).json() == {
            "items": [],
            "total": 0,
        }
    h.repo.get_by_id.assert_not_awaited()
    h.repo.get_cms_filtered.assert_not_awaited()


@pytest.mark.parametrize("method", ["GET", "POST", "PATCH", "DELETE"])
@pytest.mark.parametrize(
    "credentials",
    [
        "anonymous",
        "invalid",
        "unknown-user",
        "no-scope",
        "ADMIN",
        "SUPERUSER",
        "DEVELOPER",
    ],
)
def test_news_protected_matrix(h: Harness, method: str, credentials: str) -> None:
    h.item.equestrian_id = h.user.equestrian_id
    if credentials == "invalid":
        h.client.cookies.set("access_token", "invalid")
    elif credentials != "anonymous":
        h.login()
        h.users.get_user_scopes.return_value = (
            []
            if credentials == "no-scope"
            else [UserScope(scope_name=credentials, scope_description="Scope")]
        )
        if credentials == "unknown-user":
            h.users.get_by_username.return_value = None
    response = h.protected(method)
    expected = (
        401
        if credentials in {"anonymous", "invalid", "unknown-user"}
        else 403
        if credentials == "no-scope"
        else {"GET": 200, "POST": 201, "PATCH": 200, "DELETE": 204}[method]
    )
    assert response.status_code == expected
    if expected in {401, 403}:
        h.repo.create.assert_not_awaited()
        h.repo.update.assert_not_awaited()
        h.repo.get_by_id.assert_not_awaited()
        h.repo.get_cms_filtered.assert_not_awaited()
    elif method in {"POST", "PATCH"}:
        assert response.json()["slug"]
        assert response.json()["content"] == "<p>Old CMS payload</p>"


@pytest.mark.parametrize("method", ["PATCH", "DELETE"])
@pytest.mark.parametrize("resource", ["foreign", "missing"])
def test_news_foreign_missing_write(h: Harness, method: str, resource: str) -> None:
    h.login()
    if resource == "missing":
        h.repo.get_by_id.side_effect = None
        h.repo.get_by_id.return_value = None
    assert h.protected(method).status_code == 400
    h.repo.get_by_id.assert_awaited_once_with(
        h.item.id, equestrian_id=h.user.equestrian_id
    )
    h.repo.update.assert_not_awaited()
    assert not h.item.is_deleted
    assert h.item.name == "Published"


@pytest.mark.parametrize("method", ["POST", "PATCH"])
@pytest.mark.parametrize(
    "payload, status",
    [
        ({"name": "   ", "published_at": "2020-01-01T00:00:00Z"}, 400),
        ({"name": "Valid", "published_at": "invalid"}, 422),
        ({"name": [], "published_at": "2020-01-01T00:00:00Z"}, 422),
        (
            {
                "name": "Valid",
                "content": {},
                "published_at": "2020-01-01T00:00:00Z",
            },
            422,
        ),
    ],
)
def test_news_validation(h: Harness, method: str, payload: dict, status: int) -> None:
    h.item.equestrian_id = h.user.equestrian_id
    h.login()
    assert h.protected(method, payload).status_code == status
    h.repo.create.assert_not_awaited()
    h.repo.update.assert_not_awaited()
