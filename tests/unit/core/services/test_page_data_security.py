"""Unit tests for JS-injection validation in page_data fields.

Covers:
- validate_no_js_in_html utility directly
- Integration with BreedService, CoatColorService, HorseServiceService, PriceService
"""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

import pytest
from tenant_context import TEST_EQUESTRIAN_CONTEXT

from core.entities.breeds import Breed
from core.entities.coat_color import CoatColor
from core.entities.horse_service import HorseServiceEntity
from core.entities.price import PriceFormatter
from core.entities.prices import Price, PriceGroup, PriceGroupsRelation, PricePhotos
from core.exceptions.base import ClientError
from core.schemas.breeds import BreedCreateDto, BreedUpdateDto
from core.schemas.coat_color import CoatColorCreateDto, CoatColorUpdateDto
from core.schemas.horse_service import HorseServiceUpdateDto
from core.schemas.prices import PriceCreateDto, PriceUpdateDto
from core.services.breeds import BreedService
from core.services.coat_color import CoatColorService
from core.services.horse_service import HorseServiceService
from core.services.prices import PriceService
from core.utils.html_security import validate_no_js_in_html

pytestmark = pytest.mark.asyncio

# ---------------------------------------------------------------------------
# Utility: validate_no_js_in_html — direct tests
# ---------------------------------------------------------------------------


async def test_util_clean_html_passes() -> None:
    """Plain HTML without any JS constructs should not raise."""
    validate_no_js_in_html("field", "<h1>Hello</h1><p>World</p>")


async def test_util_script_tag_raises() -> None:
    """<script> tag must be rejected."""
    with pytest.raises(ClientError):
        validate_no_js_in_html("field", "<script>alert(1)</script>")


async def test_util_script_tag_uppercase_raises() -> None:
    """<SCRIPT SRC=…> (uppercase) must be rejected (case-insensitive check)."""
    with pytest.raises(ClientError):
        validate_no_js_in_html("field", "<SCRIPT SRC='x'></SCRIPT>")


async def test_util_javascript_uri_inline_raises() -> None:
    """javascript: URI anywhere in the string must be rejected."""
    with pytest.raises(ClientError):
        validate_no_js_in_html("field", "javascript:void(0)")


async def test_util_javascript_uri_in_href_raises() -> None:
    """javascript: in an <a href> attribute must be rejected."""
    with pytest.raises(ClientError):
        validate_no_js_in_html("field", '<a href="javascript:alert(1)">click</a>')


async def test_util_onclick_raises() -> None:
    """onclick= inline handler must be rejected."""
    with pytest.raises(ClientError):
        validate_no_js_in_html("field", '<img onclick="evil()">')


async def test_util_onmouseover_raises() -> None:
    """onmouseover= inline handler must be rejected."""
    with pytest.raises(ClientError):
        validate_no_js_in_html("field", '<div onmouseover="evil()">text</div>')


async def test_util_onchange_raises() -> None:
    """onchange= inline handler must be rejected."""
    with pytest.raises(ClientError):
        validate_no_js_in_html("field", '<input onchange="x">')


async def test_util_safe_href_passes() -> None:
    """Normal https link should not be rejected."""
    validate_no_js_in_html("field", '<a href="https://example.com">link</a>')


async def test_util_css_style_attribute_passes() -> None:
    """CSS in a style attribute is allowed."""
    validate_no_js_in_html("field", '<p style="color: red">text</p>')


async def test_util_table_passes() -> None:
    """Plain table HTML should not be rejected."""
    validate_no_js_in_html("field", "<table><tr><td>data</td></tr></table>")


async def test_util_word_on_in_content_passes() -> None:
    """The word 'on' inside text content is not an event handler attribute."""
    validate_no_js_in_html("field", 'content="onboarding"')


async def test_util_script_tag_only_raises() -> None:
    """<SCRIPT> tag alone (no closing tag) must be rejected."""
    with pytest.raises(ClientError):
        validate_no_js_in_html("field", "<SCRIPT>")


async def test_util_onerror_attribute_raises() -> None:
    """onerror= attribute must be rejected."""
    with pytest.raises(ClientError):
        validate_no_js_in_html("field", '<img src="x" onerror="alert(1)">')


async def test_util_large_clean_html_passes() -> None:
    """Large HTML (1000+ characters) without JS should not raise."""
    big_html = "<p>" + ("A" * 1000) + "</p>"
    validate_no_js_in_html("field", big_html)


async def test_util_javascript_uppercase_uri_raises() -> None:
    """JAVASCRIPT: (uppercase) URI must be rejected (case-insensitive)."""
    with pytest.raises(ClientError):
        validate_no_js_in_html("field", '<a href="JAVASCRIPT:alert()">x</a>')


async def test_util_multiple_violations_raises_once() -> None:
    """HTML with multiple violations should still raise (not crash or raise twice)."""
    evil = '<script>x</script><img onclick="y" onerror="z">'
    with pytest.raises(ClientError):
        validate_no_js_in_html("field", evil)


# ---------------------------------------------------------------------------
# Fake repositories
# ---------------------------------------------------------------------------


class FakeBreedRepository:
    def __init__(self) -> None:
        self.by_id: dict[UUID, Breed] = {}
        self.by_slug: dict[str, Breed] = {}
        self.by_name: dict[str, Breed] = {}
        self.calls: list[tuple[str, Any]] = []

    def add(self, breed: Breed) -> Breed:
        self.by_id[breed.id] = breed
        self.by_slug[breed.slug or ""] = breed
        self.by_name[breed.name] = breed
        return breed

    async def get_by_slug_or_id(self, slug_or_id: str | UUID) -> Breed | None:
        self.calls.append(("get_by_slug_or_id", slug_or_id))
        if isinstance(slug_or_id, UUID):
            return self.by_id.get(slug_or_id)
        return self.by_slug.get(slug_or_id)

    async def find_by_slug(self, slug: str) -> Breed | None:
        self.calls.append(("find_by_slug", slug))
        return self.by_slug.get(slug)

    async def find_by_name(self, name: str) -> Breed | None:
        self.calls.append(("find_by_name", name))
        return self.by_name.get(name)

    async def create(self, entity: Breed) -> Breed:
        self.calls.append(("create", entity))
        self.add(entity)
        return entity

    async def update(self, entity: Breed) -> Breed:
        self.calls.append(("update", entity))
        self.add(entity)
        return entity

    async def delete(self, id: UUID) -> None:
        self.calls.append(("delete", id))
        breed = self.by_id.pop(id, None)
        if breed is not None:
            self.by_slug.pop(breed.slug or "", None)
            self.by_name.pop(breed.name, None)

    async def get_filtered(self, **kwargs: Any) -> tuple[list[Breed], int]:
        self.calls.append(("get_filtered", kwargs))
        return [], 0


class FakeCoatColorRepository:
    def __init__(self) -> None:
        self.by_id: dict[UUID, CoatColor] = {}
        self.by_slug: dict[str, CoatColor] = {}
        self.by_name: dict[str, CoatColor] = {}
        self.calls: list[tuple[str, Any]] = []

    def add(self, entity: CoatColor) -> CoatColor:
        self.by_id[entity.id] = entity
        self.by_slug[entity.slug or ""] = entity
        self.by_name[entity.name] = entity
        return entity

    async def get_by_slug_or_id(self, slug_or_id: str | UUID) -> CoatColor | None:
        self.calls.append(("get_by_slug_or_id", slug_or_id))
        if isinstance(slug_or_id, UUID):
            return self.by_id.get(slug_or_id)
        return self.by_slug.get(slug_or_id)

    async def find_by_slug(self, slug: str) -> CoatColor | None:
        self.calls.append(("find_by_slug", slug))
        return self.by_slug.get(slug)

    async def find_by_name(self, name: str) -> CoatColor | None:
        self.calls.append(("find_by_name", name))
        return self.by_name.get(name)

    async def create(self, entity: CoatColor) -> CoatColor:
        self.calls.append(("create", entity))
        self.add(entity)
        return entity

    async def update(self, entity: CoatColor) -> CoatColor:
        self.calls.append(("update", entity))
        self.add(entity)
        return entity

    async def delete(self, id: UUID) -> None:
        self.calls.append(("delete", id))
        entity = self.by_id.pop(id, None)
        if entity is not None:
            self.by_slug.pop(entity.slug or "", None)
            self.by_name.pop(entity.name, None)

    async def get_filtered(self, **kwargs: Any) -> tuple[list[CoatColor], int]:
        self.calls.append(("get_filtered", kwargs))
        return [], 0


class FakeHorseServiceRepository:
    def __init__(self) -> None:
        self.by_id: dict[UUID, HorseServiceEntity] = {}
        self.by_slug: dict[str, HorseServiceEntity] = {}
        self.by_name: dict[str, HorseServiceEntity] = {}
        self.calls: list[tuple[str, Any]] = []

    def add(self, entity: HorseServiceEntity) -> HorseServiceEntity:
        self.by_id[entity.id] = entity
        assert entity.slug is not None
        self.by_slug[entity.slug] = entity
        self.by_name[entity.name] = entity
        return entity

    async def get_by_slug_or_id(
        self, slug_or_id: str | UUID
    ) -> HorseServiceEntity | None:
        self.calls.append(("get_by_slug_or_id", slug_or_id))
        if isinstance(slug_or_id, UUID):
            return self.by_id.get(slug_or_id)
        return self.by_slug.get(slug_or_id)

    async def find_by_slug(self, slug: str) -> HorseServiceEntity | None:
        self.calls.append(("find_by_slug", slug))
        return self.by_slug.get(slug)

    async def find_by_name(self, name: str) -> HorseServiceEntity | None:
        self.calls.append(("find_by_name", name))
        return self.by_name.get(name)

    async def create(self, entity: HorseServiceEntity) -> HorseServiceEntity:
        self.calls.append(("create", entity))
        self.add(entity)
        return entity

    async def update(self, entity: HorseServiceEntity) -> HorseServiceEntity:
        self.calls.append(("update", entity))
        self.add(entity)
        return entity

    async def delete(self, id: UUID) -> None:
        self.calls.append(("delete", id))
        entity = self.by_id.pop(id, None)
        if entity is not None:
            assert entity.slug is not None
            self.by_slug.pop(entity.slug, None)
            self.by_name.pop(entity.name, None)

    async def get_filtered(self, **kwargs: Any) -> tuple[list[HorseServiceEntity], int]:
        self.calls.append(("get_filtered", kwargs))
        return [], 0


class FakePriceRepository:
    def __init__(self) -> None:
        self.by_id: dict[UUID, Price] = {}
        self.by_slug: dict[str, Price] = {}
        self.by_name: dict[str, Price] = {}
        self.calls: list[tuple[str, Any]] = []

    def add(self, price: Price) -> Price:
        self.by_id[price.id] = price
        if price.slug is not None:
            self.by_slug[price.slug] = price
        self.by_name[price.name] = price
        return price

    async def find_by_name(self, name: str) -> Price | None:
        self.calls.append(("find_by_name", name))
        return self.by_name.get(name)

    async def get_by_slug_or_id(self, slug_or_id: str | UUID) -> Price | None:
        self.calls.append(("get_by_slug_or_id", slug_or_id))
        if isinstance(slug_or_id, UUID):
            return self.by_id.get(slug_or_id)
        return self.by_slug.get(slug_or_id)

    async def create(self, entity: Price) -> Price:
        self.calls.append(("create", entity))
        return self.add(entity)

    async def update(self, entity: Price) -> Price:
        self.calls.append(("update", entity))
        old = self.by_id.get(entity.id)
        if old is not None:
            self.by_name.pop(old.name, None)
            if old.slug is not None:
                self.by_slug.pop(old.slug, None)
        return self.add(entity)

    async def delete(self, id: UUID) -> None:
        self.calls.append(("delete", id))
        price = self.by_id.pop(id, None)
        if price is not None:
            self.by_name.pop(price.name, None)
            if price.slug is not None:
                self.by_slug.pop(price.slug, None)

    async def get_filtered(self, **kwargs: Any) -> tuple[list[Price], int]:
        self.calls.append(("get_filtered", kwargs))
        return [], 0

    async def get_price_groups(self, price_id: UUID) -> list[PriceGroupsRelation]:
        self.calls.append(("get_price_groups", price_id))
        return []

    async def set_price_groups(self, price_id: UUID, group_ids: list[UUID]) -> None:
        self.calls.append(("set_price_groups", (price_id, group_ids)))

    async def get_price_photos(self, price_id: UUID) -> list[PricePhotos]:
        self.calls.append(("get_price_photos", price_id))
        return []

    async def set_price_photos(
        self,
        price_id: UUID,
        photo_ids: list[UUID] | None = None,
        main_photo_id: UUID | None = None,
    ) -> None:
        self.calls.append(("set_price_photos", (price_id, photo_ids, main_photo_id)))

    async def get_group_relations_ordered(
        self, group_id: UUID
    ) -> list[PriceGroupsRelation]:
        self.calls.append(("get_group_relations_ordered", group_id))
        return []

    async def set_display_orders(self, group_id: UUID, orders: dict[UUID, int]) -> None:
        self.calls.append(("set_display_orders", (group_id, orders)))


class FakePriceGroupRepository:
    def __init__(self) -> None:
        self.by_id: dict[UUID, PriceGroup] = {}
        self.calls: list[tuple[str, Any]] = []

    def add(self, group: PriceGroup) -> PriceGroup:
        self.by_id[group.id] = group
        return group

    async def get_by_ids(self, ids: list[UUID]) -> dict[UUID, PriceGroup]:
        self.calls.append(("get_by_ids", ids))
        return {id_: self.by_id[id_] for id_ in ids if id_ in self.by_id}

    async def find_by_name(self, name: str) -> PriceGroup | None:
        self.calls.append(("find_by_name", name))
        return None


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def make_breed(**overrides: Any) -> Breed:
    data: dict[str, Any] = {
        "name": "Arabian",
        "slug": "arabian",
        "short_name": "Arabian",
        "page_data": "<div>Arabian</div>",
    }
    data.update(overrides)
    return Breed(**data)


def make_coat_color(**overrides: Any) -> CoatColor:
    data: dict[str, Any] = {
        "name": "Bay",
        "slug": "bay",
        "short_name": "Bay",
        "page_data": "<div>Bay</div>",
    }
    data.update(overrides)
    return CoatColor(**data)


def make_horse_service_entity(**overrides: Any) -> HorseServiceEntity:
    data: dict[str, Any] = {
        "name": "Trimming",
        "slug": "trimming",
        "price": 500,
        "price_formatter": PriceFormatter.equal,
        "page_data": "<div>Trim</div>",
    }
    data.update(overrides)
    return HorseServiceEntity(**data)


def make_price(**overrides: Any) -> Price:
    data: dict[str, Any] = {
        "name": "Subscription",
        "slug": "subscription",
        "page_data": "<p>Info</p>",
        "price_tables": [],
    }
    data.update(overrides)
    return Price(**data)


def make_breed_service() -> tuple[BreedService, FakeBreedRepository]:
    repo = FakeBreedRepository()
    return BreedService(breed_repository=cast(Any, repo)), repo


def make_coat_color_service() -> tuple[CoatColorService, FakeCoatColorRepository]:
    repo = FakeCoatColorRepository()
    return CoatColorService(coat_color_repository=cast(Any, repo)), repo


type HorseServiceBundle = tuple[HorseServiceService, FakeHorseServiceRepository]


def make_horse_service_service() -> HorseServiceBundle:
    repo = FakeHorseServiceRepository()
    return HorseServiceService(horse_service_repository=cast(Any, repo)), repo


def make_price_service() -> tuple[PriceService, FakePriceRepository]:
    price_repo = FakePriceRepository()
    group_repo = FakePriceGroupRepository()

    class _FakePhotoRepo:
        async def get_by_ids(self, ids: list[UUID]) -> dict[UUID, Any]:
            return {}

        async def get_by_id(self, id: UUID) -> Any:
            return None

    class _FakeUrlBuilder:
        def build(self, path: str) -> str:
            return f"https://cdn.local/{path}"

    service = PriceService(
        price_repository=cast(Any, price_repo),
        price_group_repository=cast(Any, group_repo),
        photo_repository=cast(Any, _FakePhotoRepo()),
        photo_url_builder=_FakeUrlBuilder(),
    )
    return service, price_repo


# ---------------------------------------------------------------------------
# BreedService integration tests
# ---------------------------------------------------------------------------


async def test_breed_update_with_clean_page_data_succeeds() -> None:
    """update with safe page_data should call repository.update."""
    service, repo = make_breed_service()
    repo.add(make_breed())

    updated = await service.update(
        "arabian",
        BreedUpdateDto(page_data="<h1>Info</h1>"),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert updated.page_data == "<h1>Info</h1>"
    assert any(name == "update" for name, _ in repo.calls)


async def test_breed_update_with_script_tag_raises_client_error() -> None:
    """update with <script> in page_data must raise ClientError; repo.update NOT called."""
    service, repo = make_breed_service()
    repo.add(make_breed())

    with pytest.raises(ClientError):
        await service.update(
            "arabian",
            BreedUpdateDto(page_data="<script>x</script>"),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )

    assert not any(name == "update" for name, _ in repo.calls)


async def test_breed_update_with_onerror_raises_client_error() -> None:
    """onerror= inline handler must be rejected on update."""
    service, repo = make_breed_service()
    repo.add(make_breed())

    with pytest.raises(ClientError):
        await service.update(
            "arabian",
            BreedUpdateDto(page_data="<img onerror='x'>"),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )

    assert not any(name == "update" for name, _ in repo.calls)


async def test_breed_update_with_javascript_uri_raises_client_error() -> None:
    """javascript: URI must be rejected on update."""
    service, repo = make_breed_service()
    repo.add(make_breed())

    with pytest.raises(ClientError):
        await service.update(
            "arabian",
            BreedUpdateDto(page_data='<a href="javascript:x">'),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )

    assert not any(name == "update" for name, _ in repo.calls)


async def test_breed_update_without_page_data_no_js_validation() -> None:
    """update without page_data key must not trigger JS validation."""
    service, repo = make_breed_service()
    repo.add(make_breed(description="old"))

    updated = await service.update(
        "arabian",
        BreedUpdateDto(description="new"),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert updated.description == "new"
    assert any(name == "update" for name, _ in repo.calls)


async def test_breed_create_with_script_raises_client_error() -> None:
    """create with <script> in page_data must raise ClientError; repo.create NOT called."""
    service, repo = make_breed_service()

    with pytest.raises(ClientError):
        await service.create(
            BreedCreateDto(name="Test", page_data="<script>x</script>"),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )

    assert not any(name == "create" for name, _ in repo.calls)


async def test_breed_create_without_page_data_uses_default() -> None:
    """create without page_data must store DEFAULT_PAGE_DATA without raising."""
    service, repo = make_breed_service()

    breed = await service.create(
        BreedCreateDto(name="Mustang"), equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )

    assert breed.page_data == "<div></div>"
    assert any(name == "create" for name, _ in repo.calls)


# ---------------------------------------------------------------------------
# CoatColorService integration tests
# ---------------------------------------------------------------------------


async def test_coat_color_update_with_onclick_raises_client_error() -> None:
    """onclick= in page_data must raise ClientError on update."""
    service, repo = make_coat_color_service()
    repo.add(make_coat_color())

    with pytest.raises(ClientError):
        await service.update(
            "bay",
            CoatColorUpdateDto(page_data="<div onclick='x'>"),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )

    assert not any(name == "update" for name, _ in repo.calls)


async def test_coat_color_update_with_clean_html_succeeds() -> None:
    """Safe HTML must pass through on update."""
    service, repo = make_coat_color_service()
    repo.add(make_coat_color())

    updated = await service.update(
        "bay",
        CoatColorUpdateDto(page_data="<ul><li>ok</li></ul>"),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert updated.page_data == "<ul><li>ok</li></ul>"
    assert any(name == "update" for name, _ in repo.calls)


async def test_coat_color_create_with_script_raises_client_error() -> None:
    """create with <SCRIPT> must raise ClientError."""
    service, repo = make_coat_color_service()

    with pytest.raises(ClientError):
        await service.create(
            CoatColorCreateDto(name="Roan", page_data="<SCRIPT>"),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )

    assert not any(name == "create" for name, _ in repo.calls)


# ---------------------------------------------------------------------------
# HorseServiceService integration tests
# ---------------------------------------------------------------------------


async def test_horse_service_update_with_onfocus_raises_client_error() -> None:
    """onfocus= handler must be rejected on update."""
    service, repo = make_horse_service_service()
    repo.add(make_horse_service_entity())

    with pytest.raises(ClientError):
        await service.update(
            "trimming",
            HorseServiceUpdateDto(page_data="<div onfocus='x'>"),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )

    assert not any(name == "update" for name, _ in repo.calls)


async def test_horse_service_update_with_clean_html_succeeds() -> None:
    """Clean table HTML must pass through on update."""
    service, repo = make_horse_service_service()
    repo.add(make_horse_service_entity())

    updated = await service.update(
        "trimming",
        HorseServiceUpdateDto(page_data="<table><tr><td>ok</td></tr></table>"),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert updated.page_data == "<table><tr><td>ok</td></tr></table>"
    assert any(name == "update" for name, _ in repo.calls)


# ---------------------------------------------------------------------------
# PriceService integration tests
# ---------------------------------------------------------------------------


async def test_price_update_with_onload_raises_client_error() -> None:
    """onload= handler must be rejected on update."""
    service, repo = make_price_service()
    repo.add(make_price())

    with pytest.raises(ClientError):
        await service.update(
            "subscription",
            PriceUpdateDto(page_data="<div onload='x'>"),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )

    assert not any(name == "update" for name, _ in repo.calls)


async def test_price_update_with_clean_html_succeeds() -> None:
    """Clean HTML must pass on price update."""
    service, repo = make_price_service()
    repo.add(make_price())

    updated = await service.update(
        "subscription",
        PriceUpdateDto(page_data="<h2>Услуга</h2><p>Описание</p>"),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert updated.page_data == "<h2>Услуга</h2><p>Описание</p>"
    assert any(name == "update" for name, _ in repo.calls)


async def test_price_create_with_script_src_raises_client_error() -> None:
    """create with <script src='x'> must raise ClientError; repo.create NOT called."""
    service, repo = make_price_service()

    with pytest.raises(ClientError):
        await service.create(
            PriceCreateDto(name="BadPrice", page_data="<script src='x'>"),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )

    assert not any(name == "create" for name, _ in repo.calls)
