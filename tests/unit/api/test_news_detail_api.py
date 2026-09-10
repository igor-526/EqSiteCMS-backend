from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from core.entities.equestrian import EquestrianContext
from core.entities.news import News
from core.services.news import NewsService
from depends.services import get_news_service, get_public_news_equestrian_context
from main import app


@pytest.mark.parametrize("credentials", [False, True])
def test_public_news_detail_contract(credentials: bool) -> None:
    tenant = EquestrianContext(id=uuid4(), source="test")
    item = News(
        name="Новость",
        slug="novost-stable",
        content="<p>Текст</p>",
        published_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        equestrian_id=tenant.id,
    )
    repository = AsyncMock()
    repository.get_public_filtered.return_value = ([item], 1)
    repository.get_public_by_id.return_value = item
    repository.get_public_by_slug.return_value = item
    repository.get_news_photos.return_value = []
    service = NewsService(repository, AsyncMock(), Mock())
    app.dependency_overrides[get_news_service] = lambda: service
    app.dependency_overrides[get_public_news_equestrian_context] = lambda: tenant
    client = TestClient(app)
    if credentials:
        client.cookies.set("access_token", "unused-by-public-routes")
    try:
        listing = client.get("/api/news")
        by_id = client.get(f"/api/news/{item.id}")
        by_slug = client.get(f"/api/news/by-slug/{item.slug}")
    finally:
        app.dependency_overrides.pop(get_news_service)
        app.dependency_overrides.pop(get_public_news_equestrian_context)
    assert listing.status_code == by_id.status_code == by_slug.status_code == 200
    assert by_id.json() == by_slug.json()
    assert set(by_slug.json()) == {
        "id",
        "slug",
        "name",
        "snippet",
        "published_at",
        "photos",
        "content",
    }
    assert by_slug.json()["content"] == item.content
    assert listing.json()["items"][0] == {
        k: v for k, v in by_slug.json().items() if k != "content"
    }
    repository.get_public_by_slug.assert_awaited_once_with(
        item.slug, equestrian_id=tenant.id
    )
    repository.get_public_by_id.assert_awaited_once_with(
        item.id, equestrian_id=tenant.id
    )


@pytest.mark.asyncio
async def test_cms_news_dto_preserves_fields_and_adds_slug() -> None:
    tenant = EquestrianContext(id=uuid4(), source="test")
    item = News(
        name="Новость",
        slug="stable-slug",
        content="<p>Content</p>",
        published_at=datetime.now(timezone.utc),
        equestrian_id=tenant.id,
    )
    repository = AsyncMock()
    repository.get_news_photos.return_value = []
    service = NewsService(repository, AsyncMock(), Mock())
    dto = await service.build_out_dto(item, equestrian_context=tenant)
    assert dto.slug == item.slug
    assert dto.content == item.content
    assert set(dto.model_dump()) == {
        "id",
        "slug",
        "name",
        "snippet",
        "content",
        "published_at",
        "is_deleted",
        "deleted_at",
        "photos",
        "created_at",
        "updated_at",
    }
