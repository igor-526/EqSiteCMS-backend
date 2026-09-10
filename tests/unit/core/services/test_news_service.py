from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from tenant_context import TEST_EQUESTRIAN_CONTEXT

from core.entities.news import News, NewsPhoto, NewsStatus
from core.entities.photos import Photo
from core.exceptions.auth import ForbiddenError
from core.exceptions.base import ClientError
from core.schemas.news import NewsCreateDto, NewsPhotosUpdateDto, NewsUpdateDto
from core.schemas.users import UserOutDto
from core.services.news import NewsService

pytestmark = pytest.mark.asyncio

_NOW = datetime(2026, 5, 11, 12, 0, 0, tzinfo=timezone.utc)
_FUTURE = datetime(2030, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
_PAST = datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeNewsRepository:
    def __init__(self) -> None:
        self.by_id: dict[UUID, News] = {}
        self.photo_relations: dict[UUID, list[NewsPhoto]] = {}
        self.calls: list[tuple[str, Any]] = []
        self.cms_filtered_result: tuple[list[News], int] = ([], 0)
        self.public_filtered_result: tuple[list[News], int] = ([], 0)

    def add(self, news_item: News) -> News:
        self.by_id[news_item.id] = news_item
        return news_item

    async def get_by_id(self, id: UUID) -> News | None:
        self.calls.append(("get_by_id", id))
        return self.by_id.get(id)

    async def create(self, entity: News) -> News:
        self.calls.append(("create", entity))
        return self.add(entity)

    async def update(self, entity: News) -> News:
        self.calls.append(("update", entity))
        return self.add(entity)

    async def get_cms_filtered(
        self, *, equestrian_id: UUID, **kwargs: Any
    ) -> tuple[list[News], int]:
        self.calls.append(("get_cms_filtered", kwargs))
        return self.cms_filtered_result

    async def get_public_filtered(
        self, *, equestrian_id: UUID, **kwargs: Any
    ) -> tuple[list[News], int]:
        self.calls.append(("get_public_filtered", kwargs))
        return self.public_filtered_result

    async def get_public_by_id(self, id: UUID) -> News | None:
        self.calls.append(("get_public_by_id", id))
        news_item = self.by_id.get(id)
        if news_item is None or news_item.is_deleted or news_item.published_at > _NOW:
            return None
        return news_item

    async def get_news_photos(self, news_id: UUID) -> list[NewsPhoto]:
        self.calls.append(("get_news_photos", news_id))
        return self.photo_relations.get(news_id, [])

    async def set_news_photos(
        self,
        news_id: UUID,
        photo_ids: list[UUID] | None = None,
        main_photo_id: UUID | None = None,
    ) -> None:
        self.calls.append(("set_news_photos", (news_id, photo_ids, main_photo_id)))
        if photo_ids is not None:
            self.photo_relations[news_id] = [
                NewsPhoto(
                    news_id=news_id,
                    photo_id=pid,
                    is_main=pid == main_photo_id,
                )
                for pid in photo_ids
            ]
        elif main_photo_id is not None:
            self.photo_relations[news_id] = [
                r.model_copy(update={"is_main": r.photo_id == main_photo_id})
                for r in self.photo_relations.get(news_id, [])
            ]

    async def delete(self, id: UUID) -> None:
        self.calls.append(("delete", id))
        self.by_id.pop(id, None)


class FakePhotoRepository:
    def __init__(self) -> None:
        self.by_id: dict[UUID, Photo] = {}

    def add(self, photo: Photo) -> Photo:
        self.by_id[photo.id] = photo
        return photo

    async def get_by_id(self, id: UUID) -> Photo | None:
        return self.by_id.get(id)

    async def get_by_ids(self, ids: list[UUID]) -> dict[UUID, Photo]:
        return {id_: self.by_id[id_] for id_ in ids if id_ in self.by_id}


class FakePhotoUrlBuilder:
    def build(self, filename: str) -> str:
        return f"https://cdn.test/{filename}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

type NewsServiceBundle = tuple[
    NewsService, FakeNewsRepository, FakePhotoRepository, FakePhotoUrlBuilder
]


def make_service() -> NewsServiceBundle:
    news_repo = FakeNewsRepository()
    photo_repo = FakePhotoRepository()
    url_builder = FakePhotoUrlBuilder()
    service = NewsService(
        news_repository=cast(Any, news_repo),
        photo_repository=cast(Any, photo_repo),
        photo_url_builder=url_builder,
    )
    return service, news_repo, photo_repo, url_builder


def make_news(**overrides: Any) -> News:
    data: dict[str, Any] = {
        "name": "Тестовая новость",
        "snippet": "Краткое описание",
        "content": "<p>Полный текст</p>",
        "published_at": _PAST,
    }
    data.update(overrides)
    return News(**data)


def make_photo(**overrides: Any) -> Photo:
    data = {"name": "Photo", "description": None, "path": "photo.png"}
    data.update(overrides)
    return Photo(**data)


def make_admin_user() -> UserOutDto:
    from core.entities.user import UserScope

    scope = UserScope(scope_name="ADMIN", scope_description="Administrator")
    return UserOutDto.model_validate(
        {
            "id": str(uuid4()),
            "username": "admin",
            "created_at": _NOW.isoformat(),
            "scopes": [
                {
                    "id": str(scope.id),
                    "scope_name": "ADMIN",
                    "scope_description": "Administrator",
                }
            ],
        }
    )


def make_no_scope_user() -> UserOutDto:
    return UserOutDto.model_validate(
        {
            "id": str(uuid4()),
            "username": "guest",
            "created_at": _NOW.isoformat(),
            "scopes": [],
        }
    )


# ---------------------------------------------------------------------------
# Group 1: snippet autogeneration
# ---------------------------------------------------------------------------


async def test_ut01_create_snippet_none_html_content_autogenerated() -> None:
    service, repo, *_ = make_service()
    user = make_admin_user()
    dto = NewsCreateDto(
        name="Новость",
        snippet=None,
        content="<p>Привет мир</p>",
        published_at=_FUTURE,
    )
    news_item = await service.create(
        dto, user=user, equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )
    assert news_item.snippet == "Привет мир"


async def test_ut02_create_snippet_explicit_used_as_is() -> None:
    service, *_ = make_service()
    user = make_admin_user()
    dto = NewsCreateDto(
        name="Новость",
        snippet="Явный сниппет",
        content="<p>Контент</p>",
        published_at=_FUTURE,
    )
    news_item = await service.create(
        dto, user=user, equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )
    assert news_item.snippet == "Явный сниппет"


async def test_ut03_create_snippet_none_empty_content_stays_none() -> None:
    service, *_ = make_service()
    user = make_admin_user()
    dto = NewsCreateDto(name="Новость", snippet=None, content="", published_at=_FUTURE)
    news_item = await service.create(
        dto, user=user, equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )
    assert news_item.snippet is None


async def test_ut04_create_content_html_tags_stripped_from_snippet() -> None:
    service, *_ = make_service()
    user = make_admin_user()
    dto = NewsCreateDto(
        name="Новость",
        snippet=None,
        content="<h1>Заголовок</h1><p>Абзац</p>",
        published_at=_FUTURE,
    )
    news_item = await service.create(
        dto, user=user, equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )
    assert "<" not in (news_item.snippet or "")
    assert "Заголовок" in (news_item.snippet or "")


async def test_ut05_create_snippet_truncated_to_255() -> None:
    service, *_ = make_service()
    user = make_admin_user()
    long_text = "А" * 300
    dto = NewsCreateDto(
        name="Новость",
        snippet=None,
        content=long_text,
        published_at=_FUTURE,
    )
    news_item = await service.create(
        dto, user=user, equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )
    assert len(news_item.snippet or "") <= 255


async def test_ut06_update_snippet_none_regenerated_from_new_content() -> None:
    service, repo, *_ = make_service()
    user = make_admin_user()
    existing = make_news(snippet="Старый сниппет", content="<p>Старый текст</p>")
    repo.add(existing)

    dto = NewsUpdateDto(content="<p>Новый текст</p>", snippet=None)
    updated = await service.update(
        existing.id, dto, user=user, equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )
    assert updated.snippet == "Новый текст"


async def test_ut07_update_snippet_explicit_used_as_is() -> None:
    service, repo, *_ = make_service()
    user = make_admin_user()
    existing = make_news(snippet="Старый сниппет")
    repo.add(existing)

    dto = NewsUpdateDto(snippet="Новый явный сниппет")
    updated = await service.update(
        existing.id, dto, user=user, equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )
    assert updated.snippet == "Новый явный сниппет"


async def test_ut08_strip_html_normalizes_whitespace() -> None:
    service, *_ = make_service()
    result = service._strip_html_to_text("<p>  Текст  \n\n  с пробелами  </p>")
    assert "  " not in result
    assert "Текст" in result
    assert "с пробелами" in result


# ---------------------------------------------------------------------------
# Group 2: field validation
# ---------------------------------------------------------------------------


async def test_ut09_create_empty_name_raises_client_error() -> None:
    service, *_ = make_service()
    user = make_admin_user()
    with pytest.raises(ClientError):
        await service.create(
            NewsCreateDto(name="", content="<p>x</p>", published_at=_FUTURE),
            user=user,
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )


async def test_ut10_create_name_too_long_raises_client_error() -> None:
    service, *_ = make_service()
    user = make_admin_user()
    with pytest.raises(ClientError):
        await service.create(
            NewsCreateDto(name="Н" * 64, content="<p>x</p>", published_at=_FUTURE),
            user=user,
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )


async def test_ut11_create_snippet_too_long_raises_client_error() -> None:
    service, *_ = make_service()
    user = make_admin_user()
    with pytest.raises(ClientError):
        await service.create(
            NewsCreateDto(
                name="Новость",
                snippet="С" * 256,
                content="<p>x</p>",
                published_at=_FUTURE,
            ),
            user=user,
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )


async def test_ut12_create_empty_string_snippet_raises_client_error() -> None:
    service, *_ = make_service()
    user = make_admin_user()
    with pytest.raises(ClientError):
        await service.create(
            NewsCreateDto(
                name="Новость", snippet="", content="<p>x</p>", published_at=_FUTURE
            ),
            user=user,
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )


async def test_ut13_create_content_with_script_raises_client_error() -> None:
    service, *_ = make_service()
    user = make_admin_user()
    with pytest.raises(ClientError):
        await service.create(
            NewsCreateDto(
                name="Новость",
                content="<script>alert(1)</script>",
                published_at=_FUTURE,
            ),
            user=user,
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )


async def test_ut14_create_content_with_javascript_uri_raises_client_error() -> None:
    service, *_ = make_service()
    user = make_admin_user()
    with pytest.raises(ClientError):
        await service.create(
            NewsCreateDto(
                name="Новость",
                content='<a href="javascript:void(0)">link</a>',
                published_at=_FUTURE,
            ),
            user=user,
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )


async def test_ut15_create_content_with_onerror_raises_client_error() -> None:
    service, *_ = make_service()
    user = make_admin_user()
    with pytest.raises(ClientError):
        await service.create(
            NewsCreateDto(
                name="Новость",
                content='<img onerror="evil()" src="x">',
                published_at=_FUTURE,
            ),
            user=user,
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )


async def test_ut16_create_valid_html_success() -> None:
    service, *_ = make_service()
    user = make_admin_user()
    news_item = await service.create(
        NewsCreateDto(
            name="Новость",
            content="<h2>Заголовок</h2><p>Текст</p>",
            published_at=_FUTURE,
        ),
        user=user,
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )
    assert news_item.name == "Новость"


# ---------------------------------------------------------------------------
# Group 3: soft delete
# ---------------------------------------------------------------------------


async def test_ut17_soft_delete_sets_is_deleted_and_deleted_at() -> None:
    service, repo, *_ = make_service()
    user = make_admin_user()
    existing = make_news()
    repo.add(existing)

    await service.soft_delete(
        existing.id, user=user, equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )

    saved = repo.by_id[existing.id]
    assert saved.is_deleted is True
    assert saved.deleted_at is not None


async def test_ut18_soft_delete_nonexistent_raises_client_error() -> None:
    service, *_ = make_service()
    user = make_admin_user()
    with pytest.raises(ClientError):
        await service.soft_delete(
            uuid4(), user=user, equestrian_context=TEST_EQUESTRIAN_CONTEXT
        )


async def test_ut19_get_cms_list_returns_deleted_records() -> None:
    service, repo, *_ = make_service()
    user = make_admin_user()
    deleted = make_news(is_deleted=True)
    repo.cms_filtered_result = ([deleted], 1)

    items, total = await service.get_cms_list(
        user=user, equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )
    assert total == 1
    assert items[0].is_deleted is True


async def test_ut20_get_cms_list_status_filter_passed_to_repo() -> None:
    service, repo, *_ = make_service()
    user = make_admin_user()
    repo.cms_filtered_result = ([], 0)

    await service.get_cms_list(
        user=user,
        status=[NewsStatus.PUBLISHED, NewsStatus.SCHEDULED],
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    last_call = repo.calls[-1]
    assert last_call[0] == "get_cms_filtered"
    assert last_call[1]["status"] == [NewsStatus.PUBLISHED, NewsStatus.SCHEDULED]


async def test_ut21_get_public_list_never_returns_deleted() -> None:
    service, repo, *_ = make_service()
    published = make_news(is_deleted=False, published_at=_PAST)
    repo.public_filtered_result = ([published], 1)

    items, total = await service.get_public_list(
        equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )
    assert total == 1
    assert items[0].is_deleted is False


# ---------------------------------------------------------------------------
# Group 4: publication and basic filtering
# ---------------------------------------------------------------------------


async def test_ut22_get_public_list_future_not_returned() -> None:
    service, repo, *_ = make_service()
    repo.public_filtered_result = ([], 0)

    items, total = await service.get_public_list(
        equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )
    assert total == 0
    assert items == []


async def test_ut23_get_public_list_past_published_returned() -> None:
    service, repo, *_ = make_service()
    past_news = make_news(published_at=_PAST)
    repo.public_filtered_result = ([past_news], 1)

    items, total = await service.get_public_list(
        equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )
    assert total == 1


async def test_ut24_get_cms_list_returns_future_published() -> None:
    service, repo, *_ = make_service()
    user = make_admin_user()
    future_news = make_news(published_at=_FUTURE)
    repo.cms_filtered_result = ([future_news], 1)

    items, total = await service.get_cms_list(
        user=user, equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )
    assert total == 1
    assert items[0].published_at == _FUTURE


async def test_ut25_get_cms_list_sort_passed_to_repo() -> None:
    service, repo, *_ = make_service()
    user = make_admin_user()
    repo.cms_filtered_result = ([], 0)

    await service.get_cms_list(
        user=user, sort="-published_at", equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )

    last_call = repo.calls[-1]
    assert last_call[1]["sort"] == "-published_at"


async def test_ut26_get_cms_list_pagination_passed_to_repo() -> None:
    service, repo, *_ = make_service()
    user = make_admin_user()
    repo.cms_filtered_result = ([], 0)

    await service.get_cms_list(
        user=user, limit=10, offset=20, equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )

    last_call = repo.calls[-1]
    assert last_call[1]["limit"] == 10
    assert last_call[1]["offset"] == 20


# ---------------------------------------------------------------------------
# Group 5: text search
# ---------------------------------------------------------------------------


async def test_ut27_get_cms_list_name_filter_passed_to_repo() -> None:
    service, repo, *_ = make_service()
    user = make_admin_user()
    repo.cms_filtered_result = ([], 0)

    await service.get_cms_list(
        user=user, name="конюшня", equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )

    last_call = repo.calls[-1]
    assert last_call[1]["name"] == "конюшня"


async def test_ut28_get_cms_list_name_case_insensitive_passed_unchanged() -> None:
    service, repo, *_ = make_service()
    user = make_admin_user()
    repo.cms_filtered_result = ([], 0)

    await service.get_cms_list(
        user=user, name="КОНЮШНЯ", equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )

    last_call = repo.calls[-1]
    assert last_call[1]["name"] == "КОНЮШНЯ"


async def test_ut29_get_cms_list_no_name_match_empty_result() -> None:
    service, repo, *_ = make_service()
    user = make_admin_user()
    repo.cms_filtered_result = ([], 0)

    items, total = await service.get_cms_list(
        user=user, name="несуществующее", equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )
    assert items == []
    assert total == 0


async def test_ut30_get_cms_list_snippet_filter_passed_to_repo() -> None:
    service, repo, *_ = make_service()
    user = make_admin_user()
    repo.cms_filtered_result = ([], 0)

    await service.get_cms_list(
        user=user, snippet="анонс", equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )

    last_call = repo.calls[-1]
    assert last_call[1]["snippet"] == "анонс"


async def test_ut31_get_cms_list_content_filter_passed_to_repo() -> None:
    service, repo, *_ = make_service()
    user = make_admin_user()
    repo.cms_filtered_result = ([], 0)

    await service.get_cms_list(
        user=user, content="подробности", equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )

    last_call = repo.calls[-1]
    assert last_call[1]["content"] == "подробности"


async def test_ut32_get_cms_list_none_name_no_filter() -> None:
    service, repo, *_ = make_service()
    user = make_admin_user()
    repo.cms_filtered_result = ([], 0)

    await service.get_cms_list(
        user=user, name=None, equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )

    last_call = repo.calls[-1]
    assert last_call[1]["name"] is None


async def test_ut33_get_cms_list_special_chars_in_name_passed_to_repo() -> None:
    service, repo, *_ = make_service()
    user = make_admin_user()
    repo.cms_filtered_result = ([], 0)

    await service.get_cms_list(
        user=user, name="test.com", equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )

    last_call = repo.calls[-1]
    assert last_call[1]["name"] == "test.com"


async def test_ut34_get_cms_list_name_and_status_combined() -> None:
    service, repo, *_ = make_service()
    user = make_admin_user()
    repo.cms_filtered_result = ([], 0)

    await service.get_cms_list(
        user=user,
        name="new",
        status=[NewsStatus.PUBLISHED],
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    last_call = repo.calls[-1]
    assert last_call[1]["name"] == "new"
    assert last_call[1]["status"] == [NewsStatus.PUBLISHED]


# ---------------------------------------------------------------------------
# Group 6: date and status filtering
# ---------------------------------------------------------------------------


async def test_ut35_get_cms_list_published_at_from_passed_to_repo() -> None:
    service, repo, *_ = make_service()
    user = make_admin_user()
    repo.cms_filtered_result = ([], 0)

    await service.get_cms_list(
        user=user, published_at_from=_PAST, equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )

    last_call = repo.calls[-1]
    assert last_call[1]["published_at_from"] == _PAST


async def test_ut36_get_cms_list_published_at_to_passed_to_repo() -> None:
    service, repo, *_ = make_service()
    user = make_admin_user()
    repo.cms_filtered_result = ([], 0)

    await service.get_cms_list(
        user=user, published_at_to=_FUTURE, equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )

    last_call = repo.calls[-1]
    assert last_call[1]["published_at_to"] == _FUTURE


async def test_ut37_get_cms_list_date_range_both_passed_to_repo() -> None:
    service, repo, *_ = make_service()
    user = make_admin_user()
    repo.cms_filtered_result = ([], 0)

    await service.get_cms_list(
        user=user,
        published_at_from=_PAST,
        published_at_to=_FUTURE,
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    last_call = repo.calls[-1]
    assert last_call[1]["published_at_from"] == _PAST
    assert last_call[1]["published_at_to"] == _FUTURE


async def test_ut38_get_cms_list_status_published_only() -> None:
    service, repo, *_ = make_service()
    user = make_admin_user()
    published = make_news(published_at=_PAST)
    repo.cms_filtered_result = ([published], 1)

    items, total = await service.get_cms_list(
        user=user,
        status=[NewsStatus.PUBLISHED],
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )
    assert total == 1


async def test_ut39_get_cms_list_status_scheduled_only() -> None:
    service, repo, *_ = make_service()
    user = make_admin_user()
    scheduled = make_news(published_at=_FUTURE)
    repo.cms_filtered_result = ([scheduled], 1)

    items, total = await service.get_cms_list(
        user=user,
        status=[NewsStatus.SCHEDULED],
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )
    assert total == 1


async def test_ut40_get_cms_list_status_deleted_only() -> None:
    service, repo, *_ = make_service()
    user = make_admin_user()
    deleted = make_news(is_deleted=True)
    repo.cms_filtered_result = ([deleted], 1)

    items, total = await service.get_cms_list(
        user=user,
        status=[NewsStatus.DELETED],
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )
    assert total == 1


async def test_ut41_get_cms_list_status_multi_or_passed_to_repo() -> None:
    service, repo, *_ = make_service()
    user = make_admin_user()
    repo.cms_filtered_result = ([], 0)

    await service.get_cms_list(
        user=user,
        status=[NewsStatus.PUBLISHED, NewsStatus.SCHEDULED],
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    last_call = repo.calls[-1]
    assert NewsStatus.PUBLISHED in last_call[1]["status"]
    assert NewsStatus.SCHEDULED in last_call[1]["status"]


async def test_ut42_get_cms_list_sort_status_passed() -> None:
    service, repo, *_ = make_service()
    user = make_admin_user()
    repo.cms_filtered_result = ([], 0)

    await service.get_cms_list(
        user=user, sort="status", equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )

    last_call = repo.calls[-1]
    assert last_call[1]["sort"] == "status"


# ---------------------------------------------------------------------------
# Group 7: access control and CRUD
# ---------------------------------------------------------------------------


async def test_ut43_create_admin_success() -> None:
    service, *_ = make_service()
    user = make_admin_user()
    news_item = await service.create(
        NewsCreateDto(name="Новость", content="<p>Текст</p>", published_at=_FUTURE),
        user=user,
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )
    assert news_item.name == "Новость"


async def test_ut44_create_no_scope_raises_forbidden() -> None:
    service, *_ = make_service()
    user = make_no_scope_user()
    with pytest.raises(ForbiddenError):
        await service.create(
            NewsCreateDto(name="Новость", content="", published_at=_FUTURE),
            user=user,
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )


async def test_ut45_create_none_user_raises_forbidden() -> None:
    service, *_ = make_service()
    user = make_no_scope_user()
    user.scopes = []
    with pytest.raises(ForbiddenError):
        await service.create(
            NewsCreateDto(name="Новость", content="", published_at=_FUTURE),
            user=user,
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )


async def test_ut46_update_nonexistent_raises_client_error() -> None:
    service, *_ = make_service()
    user = make_admin_user()
    with pytest.raises(ClientError):
        await service.update(
            uuid4(),
            NewsUpdateDto(name="X"),
            user=user,
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )


async def test_ut47_update_partial_untouched_fields_unchanged() -> None:
    service, repo, *_ = make_service()
    user = make_admin_user()
    existing = make_news(name="Старое", snippet="Сниппет", content="<p>Контент</p>")
    repo.add(existing)

    updated = await service.update(
        existing.id,
        NewsUpdateDto(name="Новое"),
        user=user,
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )
    assert updated.snippet == "Сниппет"
    assert updated.content == "<p>Контент</p>"


async def test_ut48_update_photos_main_not_in_photo_ids_raises_client_error() -> None:
    service, repo, photo_repo, *_ = make_service()
    existing = make_news()
    repo.add(existing)
    photo1 = make_photo()
    photo_repo.add(photo1)
    alien_id = uuid4()

    with pytest.raises(ClientError):
        await service.update_photos(
            existing.id,
            NewsPhotosUpdateDto(photo_ids=[photo1.id], main=alien_id),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )


async def test_ut49_update_photos_photo_not_in_equestrian_raises_client_error() -> None:
    service, repo, photo_repo, *_ = make_service()
    existing = make_news()
    repo.add(existing)
    alien_photo_id = uuid4()

    with pytest.raises(ClientError):
        await service.update_photos(
            existing.id,
            NewsPhotosUpdateDto(photo_ids=[alien_photo_id]),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )


async def test_ut50_get_public_list_response_has_no_content_is_deleted() -> None:
    service, repo, *_ = make_service()
    published = make_news(published_at=_PAST)
    repo.public_filtered_result = ([published], 1)

    items, _ = await service.get_public_list(equestrian_context=TEST_EQUESTRIAN_CONTEXT)
    public_dto = await service.build_public_out_dto(
        items[0], equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )

    assert not hasattr(public_dto, "content")
    assert not hasattr(public_dto, "is_deleted")
    assert not hasattr(public_dto, "deleted_at")


@pytest.mark.parametrize(
    "name",
    [
        "Ёж, щука и Юлия!",
        "  Конный -- КЛУБ  ",
        "中文 🎠",
        "___",
        "",
        "A" * 200,
        "a" * 126 + " - b",
    ],
)
async def test_news_slug_matches_frozen_backfill(name: str) -> None:
    from importlib import import_module
    from core.utils.news_slug import generate_news_slug

    migration = import_module("migration.versions.7d28fbc9a631_add_news_slug")
    identity = UUID("12345678-9abc-def0-1234-56789abcdef0")
    slug = generate_news_slug(name, identity)
    assert slug == migration._generate_slug(name, identity)
    assert len(slug) <= 160


async def test_ut_be04_old_payload_generates_distinct_persisted_slugs() -> None:
    service, repo, *_ = make_service()
    dto = NewsCreateDto(name="Конный клуб", content="<p>x</p>", published_at=_PAST)
    first = await service.create(
        dto, user=make_admin_user(), equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )
    second = await service.create(
        dto, user=make_admin_user(), equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )
    assert first.slug == f"konnyy-klub-{first.id.hex}"
    assert second.slug == f"konnyy-klub-{second.id.hex}"
    assert first.slug != second.slug
    assert repo.by_id[first.id].slug == first.slug


async def test_ut_be05_rename_content_and_delete_preserve_slug() -> None:
    service, repo, *_ = make_service()
    user = make_admin_user()
    item = await service.create(
        NewsCreateDto(name="Название", content="<p>x</p>", published_at=_PAST),
        user=user,
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )
    slug = item.slug
    for dto in [NewsUpdateDto(name="Новое имя"), NewsUpdateDto(content="<p>New</p>")]:
        updated = await service.update(
            item.id, dto, user=user, equestrian_context=TEST_EQUESTRIAN_CONTEXT
        )
        assert updated.slug == slug
    await service.soft_delete(
        item.id, user=user, equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )
    assert repo.by_id[item.id].slug == slug


async def test_ut_be06_slug_service_passes_tenant_and_maps_missing_only() -> None:
    from unittest.mock import AsyncMock
    from core.exceptions.base import NotFoundError

    service, repo, *_ = make_service()
    item = make_news(slug="public-slug")
    lookup = AsyncMock(return_value=item)
    repo.get_public_by_slug = lookup  # type: ignore[attr-defined]
    assert (
        await service.get_public_detail_by_slug(
            item.slug, equestrian_context=TEST_EQUESTRIAN_CONTEXT
        )
        is item
    )
    lookup.assert_awaited_once_with(item.slug, equestrian_id=TEST_EQUESTRIAN_CONTEXT.id)
    lookup.return_value = None
    with pytest.raises(NotFoundError):
        await service.get_public_detail_by_slug(
            "missing", equestrian_context=TEST_EQUESTRIAN_CONTEXT
        )


@pytest.mark.parametrize("method", ["slug", "id", "list"])
async def test_ut_be07_database_errors_propagate(method: str) -> None:
    from unittest.mock import AsyncMock

    service, repo, *_ = make_service()
    error = RuntimeError("database unavailable")
    operation: Any
    if method == "slug":
        repo.get_public_by_slug = AsyncMock(side_effect=error)  # type: ignore[attr-defined]
        operation = service.get_public_detail_by_slug(
            "slug", equestrian_context=TEST_EQUESTRIAN_CONTEXT
        )
    elif method == "id":
        repo.get_public_by_id = AsyncMock(side_effect=error)  # type: ignore[method-assign]
        operation = service.get_public_detail(
            uuid4(), equestrian_context=TEST_EQUESTRIAN_CONTEXT
        )
    else:
        repo.get_public_filtered = AsyncMock(side_effect=error)  # type: ignore[method-assign]
        operation = service.get_public_list(equestrian_context=TEST_EQUESTRIAN_CONTEXT)
    with pytest.raises(RuntimeError, match="database unavailable"):
        await operation


@pytest.mark.parametrize("method", ["slug", "id", "list"])
async def test_ut_be06_07_repository_public_query_contract(method: str) -> None:
    from unittest.mock import AsyncMock, MagicMock
    from sqlalchemy.dialects import postgresql
    from repositories.news_repository import NewsRepository

    result = MagicMock()
    result.mappings.return_value.first.return_value = None
    result.mappings.return_value.all.return_value = []
    result.scalar.return_value = 0
    session = AsyncMock()
    session.execute.return_value = result
    repository = NewsRepository(session=session)
    tenant = TEST_EQUESTRIAN_CONTEXT.id
    identity = uuid4()
    if method == "slug":
        assert (
            await repository.get_public_by_slug("exact-slug", equestrian_id=tenant)
            is None
        )
    elif method == "id":
        assert await repository.get_public_by_id(identity, equestrian_id=tenant) is None
    else:
        assert await repository.get_public_filtered(
            equestrian_id=tenant, limit=12, offset=12
        ) == ([], 0)

    # Check the actual PostgreSQL predicates, including inclusive publication time.
    for call in session.execute.await_args_list:
        query = call.args[0].compile(dialect=postgresql.dialect())
        sql = str(query)
        assert "news.equestrian_id =" in sql
        assert tenant in query.params.values()
        assert "news.is_deleted = false" in sql
        assert "news.published_at <= now()" in sql
        if method == "slug":
            assert "news.slug =" in sql
            assert "exact-slug" in query.params.values()
        elif method == "id":
            assert "news.id =" in sql
            assert identity in query.params.values()
    if method == "list":
        query = (
            session.execute.await_args_list[0]
            .args[0]
            .compile(dialect=postgresql.dialect())
        )
        assert "ORDER BY news.published_at DESC, news.id DESC" in str(query)
        assert list(query.params.values()).count(12) == 2
