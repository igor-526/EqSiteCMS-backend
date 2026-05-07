from __future__ import annotations

from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from core.entities.photos import Photo
from core.entities.prices import Price, PriceGroup, PriceGroupsRelation, PricePhotos
from core.exceptions.base import ClientError
from core.schemas.prices import (
    PriceCreateDto,
    PriceOutWithTablesDto,
    PricePhotosUpdateDto,
    PriceUpdateDto,
)
from core.services.prices import PriceService

pytestmark = pytest.mark.asyncio


class RepositoryError(Exception):
    pass


class FakePriceRepository:
    def __init__(self) -> None:
        self.by_id: dict[UUID, Price] = {}
        self.by_slug: dict[str, Price] = {}
        self.by_name: dict[str, Price] = {}
        self.group_relations: dict[UUID, list[PriceGroupsRelation]] = {}
        self.photo_relations: dict[UUID, list[PricePhotos]] = {}
        self.calls: list[tuple[str, Any]] = []
        self.filtered_result: tuple[list[Price], int] = ([], 0)
        self.fail_on: set[str] = set()

    def add(self, price: Price) -> Price:
        self.by_id[price.id] = price
        if price.slug is not None:
            self.by_slug[price.slug] = price
        self.by_name[price.name] = price
        return price

    def _fail_if_needed(self, method: str) -> None:
        if method in self.fail_on:
            raise RepositoryError(method)

    async def find_by_name(self, name: str) -> Price | None:
        self.calls.append(("find_by_name", name))
        self._fail_if_needed("find_by_name")
        return self.by_name.get(name)

    async def get_by_slug_or_id(self, slug_or_id: str | UUID) -> Price | None:
        self.calls.append(("get_by_slug_or_id", slug_or_id))
        self._fail_if_needed("get_by_slug_or_id")
        if isinstance(slug_or_id, UUID):
            return self.by_id.get(slug_or_id)
        return self.by_slug.get(slug_or_id)

    async def create(self, entity: Price) -> Price:
        self.calls.append(("create", entity))
        self._fail_if_needed("create")
        return self.add(entity)

    async def update(self, entity: Price) -> Price:
        self.calls.append(("update", entity))
        self._fail_if_needed("update")
        old = self.by_id.get(entity.id)
        if old is not None:
            self.by_name.pop(old.name, None)
            if old.slug is not None:
                self.by_slug.pop(old.slug, None)
        return self.add(entity)

    async def delete(self, id: UUID) -> None:
        self.calls.append(("delete", id))
        self._fail_if_needed("delete")
        price = self.by_id.pop(id, None)
        if price is not None:
            self.by_name.pop(price.name, None)
            if price.slug is not None:
                self.by_slug.pop(price.slug, None)

    async def get_filtered(
        self,
        *,
        name: str | list[str] | None = None,
        description: str | None = None,
        groups: str | list[str] | None = None,
        sort: list[str] | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[list[Price], int]:
        self.calls.append(
            (
                "get_filtered",
                {
                    "name": name,
                    "description": description,
                    "groups": groups,
                    "sort": sort,
                    "limit": limit,
                    "offset": offset,
                },
            )
        )
        self._fail_if_needed("get_filtered")
        return self.filtered_result

    async def get_price_groups(self, price_id: UUID) -> list[PriceGroupsRelation]:
        self.calls.append(("get_price_groups", price_id))
        self._fail_if_needed("get_price_groups")
        return self.group_relations.get(price_id, [])

    async def set_price_groups(self, price_id: UUID, group_ids: list[UUID]) -> None:
        self.calls.append(("set_price_groups", (price_id, group_ids)))
        self._fail_if_needed("set_price_groups")
        self.group_relations[price_id] = [
            PriceGroupsRelation(price_id=price_id, group_id=group_id)
            for group_id in group_ids
        ]

    async def get_price_photos(self, price_id: UUID) -> list[PricePhotos]:
        self.calls.append(("get_price_photos", price_id))
        self._fail_if_needed("get_price_photos")
        return self.photo_relations.get(price_id, [])

    async def set_price_photos(
        self,
        price_id: UUID,
        photo_ids: list[UUID] | None = None,
        main_photo_id: UUID | None = None,
    ) -> None:
        self.calls.append(("set_price_photos", (price_id, photo_ids, main_photo_id)))
        self._fail_if_needed("set_price_photos")
        if photo_ids is not None:
            self.photo_relations[price_id] = [
                PricePhotos(
                    price_id=price_id,
                    photo_id=photo_id,
                    is_main=photo_id == main_photo_id,
                )
                for photo_id in photo_ids
            ]
        elif main_photo_id is not None:
            self.photo_relations[price_id] = [
                relation.model_copy(
                    update={"is_main": relation.photo_id == main_photo_id}
                )
                for relation in self.photo_relations.get(price_id, [])
            ]


class FakePriceGroupRepository:
    def __init__(self) -> None:
        self.by_id: dict[UUID, PriceGroup] = {}
        self.calls: list[tuple[str, Any]] = []
        self.fail_on: set[str] = set()

    def add(self, group: PriceGroup) -> PriceGroup:
        self.by_id[group.id] = group
        return group

    def _fail_if_needed(self, method: str) -> None:
        if method in self.fail_on:
            raise RepositoryError(method)

    async def get_by_ids(self, ids: list[UUID]) -> dict[UUID, PriceGroup]:
        self.calls.append(("get_by_ids", ids))
        self._fail_if_needed("get_by_ids")
        return {id_: self.by_id[id_] for id_ in ids if id_ in self.by_id}


class FakePhotoRepository:
    def __init__(self) -> None:
        self.by_id: dict[UUID, Photo] = {}
        self.calls: list[tuple[str, Any]] = []
        self.fail_on: set[str] = set()

    def add(self, photo: Photo) -> Photo:
        self.by_id[photo.id] = photo
        return photo

    def _fail_if_needed(self, method: str) -> None:
        if method in self.fail_on:
            raise RepositoryError(method)

    async def get_by_id(self, id: UUID) -> Photo | None:
        self.calls.append(("get_by_id", id))
        self._fail_if_needed("get_by_id")
        return self.by_id.get(id)

    async def get_by_ids(self, ids: list[UUID]) -> dict[UUID, Photo]:
        self.calls.append(("get_by_ids", ids))
        self._fail_if_needed("get_by_ids")
        return {id_: self.by_id[id_] for id_ in ids if id_ in self.by_id}


class FakePhotoUrlBuilder:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def build(self, filename: str) -> str:
        self.calls.append(filename)
        return f"https://cdn.local/media/{filename}"


def make_price(**overrides: Any) -> Price:
    data = {
        "name": "Price",
        "slug": "price",
        "description": "Desc",
        "page_data": "<p>Page</p>",
        "price_tables": [],
    }
    data.update(overrides)
    return Price(**data)


def make_group(**overrides: Any) -> PriceGroup:
    data = {"name": "Group", "description": "Desc"}
    data.update(overrides)
    return PriceGroup(**data)


def make_photo(**overrides: Any) -> Photo:
    data = {"name": "Photo", "description": "Desc", "path": "photo.png"}
    data.update(overrides)
    return Photo(**data)


def make_service() -> tuple[
    PriceService,
    FakePriceRepository,
    FakePriceGroupRepository,
    FakePhotoRepository,
    FakePhotoUrlBuilder,
]:
    price_repo = FakePriceRepository()
    group_repo = FakePriceGroupRepository()
    photo_repo = FakePhotoRepository()
    url_builder = FakePhotoUrlBuilder()
    service = PriceService(
        price_repository=cast(Any, price_repo),
        price_group_repository=cast(Any, group_repo),
        photo_repository=cast(Any, photo_repo),
        photo_url_builder=url_builder,
    )
    return service, price_repo, group_repo, photo_repo, url_builder


async def test_parse_slug_or_id_uc12_returns_uuid_or_slug() -> None:
    service, *_ = make_service()
    id_ = uuid4()

    assert service._parse_slug_or_id(str(id_)) == id_
    assert service._parse_slug_or_id("abonement") == "abonement"


async def test_get_by_slug_or_id_uc12_uc13_passes_uuid_object_and_not_found() -> None:
    service, price_repo, *_ = make_service()
    price = price_repo.add(make_price())

    assert await service.get_by_slug_or_id(str(price.id)) == price
    assert isinstance(price_repo.calls[-1][1], UUID)

    with pytest.raises(ClientError):
        await service.get_by_slug_or_id("missing")


async def test_ensure_unique_name_uc14_uc15_rejects_duplicate_allows_self() -> None:
    service, price_repo, *_ = make_service()
    price = price_repo.add(make_price(name="Existing"))

    assert (
        await service._ensure_unique_name("Existing", exclude_id=price.id) == "Existing"
    )
    with pytest.raises(ClientError):
        await service._ensure_unique_name("Existing")


async def test_ensure_unique_slug_uc14_suffixes_duplicate_and_allows_self() -> None:
    service, price_repo, *_ = make_service()
    price = price_repo.add(make_price(slug="base"))
    price_repo.add(make_price(name="Other", slug="base-1"))

    assert await service._ensure_unique_slug("base", exclude_id=price.id) == "base"
    assert await service._ensure_unique_slug("base") == "base-2"


async def test_ensure_unique_slug_uc10_uc11_suffix_stays_within_max_length() -> None:
    service, price_repo, *_ = make_service()
    long_slug = "x" * 63
    price_repo.add(make_price(slug=long_slug))

    unique_slug = await service._ensure_unique_slug(long_slug)

    assert unique_slug == f"{'x' * 61}-1"
    assert len(unique_slug) == 63


async def test_create_uc01_uc02_uc22_validates_groups_before_create() -> None:
    service, price_repo, group_repo, *_ = make_service()
    group = group_repo.add(make_group())

    created = await service.create(
        PriceCreateDto(name="  Абонемент  ", groups=[group.id, group.id])
    )

    assert created.name == "Абонемент"
    assert created.slug == "abonement"
    assert created.page_data == "<div></div>"
    assert group_repo.calls == [("get_by_ids", [group.id])]
    assert [name for name, _ in price_repo.calls] == [
        "find_by_name",
        "get_by_slug_or_id",
        "create",
        "set_price_groups",
    ]
    assert price_repo.calls[-1][1] == (created.id, [group.id])


async def test_create_uc16_uc23_missing_group_prevents_persistence_side_effects() -> (
    None
):
    service, price_repo, *_ = make_service()
    missing_id = uuid4()

    with pytest.raises(ClientError):
        await service.create(PriceCreateDto(name="Price", groups=[missing_id]))

    assert price_repo.calls == []


async def test_create_uc05_uc06_uc11_rejects_bad_business_values() -> None:
    service, price_repo, *_ = make_service()

    with pytest.raises(ClientError):
        await service.create(PriceCreateDto(name=" "))
    with pytest.raises(ClientError):
        await service.create(PriceCreateDto(name="x" * 64))

    assert price_repo.calls == []


async def test_create_uc14_generates_unique_slug_from_explicit_slug() -> None:
    service, price_repo, *_ = make_service()
    price_repo.add(make_price(name="Existing", slug="custom"))

    created = await service.create(PriceCreateDto(name="New", slug="custom"))

    assert created.slug == "custom-1"


async def test_create_uc10_uc14_duplicate_explicit_slug_at_max_length_is_trimmed() -> (
    None
):
    service, price_repo, *_ = make_service()
    long_slug = "x" * 63
    price_repo.add(make_price(name="Existing", slug=long_slug))

    created = await service.create(PriceCreateDto(name="New", slug=long_slug))

    assert created.slug == f"{'x' * 61}-1"
    assert len(created.slug or "") == 63


async def test_create_uc10_uc14_duplicate_generated_slug_at_max_length_is_trimmed() -> (
    None
):
    service, price_repo, *_ = make_service()
    long_slug = "x" * 63
    price_repo.add(make_price(name="Existing", slug=long_slug))

    created = await service.create(PriceCreateDto(name=long_slug))

    assert created.slug == f"{'x' * 61}-1"
    assert len(created.slug or "") == 63


async def test_create_uc11_generated_transliterated_slug_over_limit_is_client_error() -> (
    None
):
    service, price_repo, *_ = make_service()

    with pytest.raises(ClientError):
        await service.create(PriceCreateDto(name="щ" * 22))

    assert [name for name, _ in price_repo.calls] == ["find_by_name"]


async def test_update_uc20_empty_update_is_client_error_without_write() -> None:
    service, price_repo, *_ = make_service()
    price = price_repo.add(make_price())

    with pytest.raises(ClientError):
        await service.update(price.slug or "", PriceUpdateDto())

    assert [name for name, _ in price_repo.calls] == ["get_by_slug_or_id"]


async def test_update_uc16_uc23_validates_groups_before_price_update() -> None:
    service, price_repo, *_ = make_service()
    price = price_repo.add(make_price())

    with pytest.raises(ClientError):
        await service.update(
            price.slug or "", PriceUpdateDto(name="New", groups=[uuid4()])
        )

    assert [name for name, _ in price_repo.calls] == ["get_by_slug_or_id"]


async def test_update_uc19_uc22_updates_entity_then_group_relations() -> None:
    service, price_repo, group_repo, *_ = make_service()
    price = price_repo.add(make_price(name="Old", slug="old"))
    group = group_repo.add(make_group())

    updated = await service.update(
        "old",
        PriceUpdateDto(name="New", description=" Desc ", groups=[group.id]),
    )

    assert updated.name == "New"
    assert updated.description == "Desc"
    assert updated.slug == "new"
    assert [name for name, _ in price_repo.calls] == [
        "get_by_slug_or_id",
        "find_by_name",
        "get_by_slug_or_id",
        "update",
        "get_price_groups",
        "set_price_groups",
    ]


async def test_update_uc10_uc14_duplicate_explicit_slug_at_max_length_is_trimmed() -> (
    None
):
    service, price_repo, *_ = make_service()
    current = price_repo.add(make_price(name="Current", slug="current"))
    long_slug = "x" * 63
    price_repo.add(make_price(name="Other", slug=long_slug))

    updated = await service.update(
        current.slug or "",
        PriceUpdateDto(slug=long_slug),
    )

    assert updated.slug == f"{'x' * 61}-1"
    assert len(updated.slug or "") == 63


async def test_update_uc10_uc14_duplicate_generated_slug_at_max_length_is_trimmed() -> (
    None
):
    service, price_repo, *_ = make_service()
    current = price_repo.add(make_price(name="Current", slug="current"))
    long_slug = "x" * 63
    price_repo.add(make_price(name="Other", slug=long_slug))

    updated = await service.update(
        current.slug or "",
        PriceUpdateDto(name=long_slug),
    )

    assert updated.slug == f"{'x' * 61}-1"
    assert len(updated.slug or "") == 63


async def test_update_uc11_generated_transliterated_slug_over_limit_is_client_error() -> (
    None
):
    service, price_repo, *_ = make_service()
    price = price_repo.add(make_price())

    with pytest.raises(ClientError):
        await service.update(price.slug or "", PriceUpdateDto(name="щ" * 22))

    assert [name for name, _ in price_repo.calls] == [
        "get_by_slug_or_id",
        "find_by_name",
    ]


async def test_update_uc19_groups_only_can_clear_relations_without_entity_update() -> (
    None
):
    service, price_repo, *_ = make_service()
    price = price_repo.add(make_price())

    updated = await service.update(price.slug or "", PriceUpdateDto(groups=[]))

    assert updated == price
    assert [name for name, _ in price_repo.calls] == [
        "get_by_slug_or_id",
        "get_price_groups",
        "set_price_groups",
    ]
    assert price_repo.calls[-1][1] == (price.id, [])


async def test_delete_uc01_uc13_deletes_existing_and_rejects_missing() -> None:
    service, price_repo, *_ = make_service()
    price = price_repo.add(make_price())

    await service.delete(price.slug or "")
    assert price.id not in price_repo.by_id

    with pytest.raises(ClientError):
        await service.delete(price.slug or "")


async def test_get_filtered_uc26_uc27_passes_filters_through() -> None:
    service, price_repo, *_ = make_service()
    prices = [make_price(name="A"), make_price(name="B")]
    price_repo.filtered_result = (prices, 2)

    entities, total = await service.get_filtered(
        name=["A", "B"],
        description="desc",
        groups=["Group"],
        sort=["name", "-name"],
        limit=10,
        offset=20,
    )

    assert entities == prices
    assert total == 2
    assert price_repo.calls[-1][0] == "get_filtered"


async def test_update_price_photos_uc16_validates_photos_and_main_before_side_effect() -> (
    None
):
    service, price_repo, _, photo_repo, _ = make_service()
    price = price_repo.add(make_price())
    photo = photo_repo.add(make_photo())

    await service.update_price_photos(
        price.slug or "",
        PricePhotosUpdateDto(photo_ids=[photo.id, photo.id], main=photo.id),
    )

    assert photo_repo.calls == [("get_by_ids", [photo.id])]
    assert price_repo.calls[-1] == (
        "set_price_photos",
        (price.id, [photo.id], photo.id),
    )


async def test_update_price_photos_uc16_main_must_belong_to_new_photo_list() -> None:
    service, price_repo, _, photo_repo, _ = make_service()
    price = price_repo.add(make_price())
    photo = photo_repo.add(make_photo())
    main = photo_repo.add(make_photo(name="Main", path="main.png"))

    with pytest.raises(ClientError):
        await service.update_price_photos(
            price.slug or "",
            PricePhotosUpdateDto(photo_ids=[photo.id], main=main.id),
        )

    assert [name for name, _ in price_repo.calls] == ["get_by_slug_or_id"]


async def test_update_price_photos_uc16_main_only_must_exist_and_be_related() -> None:
    service, price_repo, _, photo_repo, _ = make_service()
    price = price_repo.add(make_price())
    photo = photo_repo.add(make_photo())
    price_repo.photo_relations[price.id] = [
        PricePhotos(price_id=price.id, photo_id=photo.id, is_main=False)
    ]

    await service.update_price_photos(
        price.slug or "",
        PricePhotosUpdateDto(main=photo.id),
    )

    assert [name for name, _ in photo_repo.calls] == ["get_by_id"]
    assert price_repo.calls[-1] == (
        "set_price_photos",
        (price.id, None, photo.id),
    )


async def test_update_price_photos_uc16_main_only_rejects_unrelated_photo() -> None:
    service, price_repo, _, photo_repo, _ = make_service()
    price = price_repo.add(make_price())
    photo = photo_repo.add(make_photo())

    with pytest.raises(ClientError):
        await service.update_price_photos(
            price.slug or "",
            PricePhotosUpdateDto(main=photo.id),
        )

    assert all(name != "set_price_photos" for name, _ in price_repo.calls)


async def test_update_price_photos_uc20_empty_update_is_client_error() -> None:
    service, price_repo, *_ = make_service()
    price = price_repo.add(make_price())

    with pytest.raises(ClientError):
        await service.update_price_photos(price.slug or "", PricePhotosUpdateDto())

    assert [name for name, _ in price_repo.calls] == ["get_by_slug_or_id"]


async def test_build_out_dto_uc25_uc28_sorts_main_first_stably_and_builds_urls() -> (
    None
):
    service, price_repo, group_repo, photo_repo, url_builder = make_service()
    price = price_repo.add(make_price(page_data=None, price_tables=[]))
    group_a = group_repo.add(make_group(name="A"))
    group_b = group_repo.add(make_group(name="B"))
    photo_a = photo_repo.add(make_photo(name="A", path="a.png"))
    photo_b = photo_repo.add(make_photo(name="B", path="b.png"))
    photo_c = photo_repo.add(make_photo(name="C", path="c.png"))
    price_repo.group_relations[price.id] = [
        PriceGroupsRelation(price_id=price.id, group_id=group_b.id),
        PriceGroupsRelation(price_id=price.id, group_id=group_a.id),
    ]
    price_repo.photo_relations[price.id] = [
        PricePhotos(price_id=price.id, photo_id=photo_a.id, is_main=False),
        PricePhotos(price_id=price.id, photo_id=photo_b.id, is_main=True),
        PricePhotos(price_id=price.id, photo_id=photo_c.id, is_main=False),
    ]

    dto = await service.build_out_dto(price, include_tables=True)
    assert isinstance(dto, PriceOutWithTablesDto)

    assert dto.page_data == "<div></div>"
    assert [group.name for group in dto.groups] == ["B", "A"]
    assert [photo.id for photo in dto.photos] == [photo_b.id, photo_a.id, photo_c.id]
    assert [photo.is_main for photo in dto.photos] == [True, False, False]
    assert url_builder.calls == ["b.png", "a.png", "c.png"]


async def test_get_filtered_out_uc28_enriches_items_at_service_boundary() -> None:
    service, price_repo, *_ = make_service()
    price = price_repo.add(make_price())
    price_repo.filtered_result = ([price], 1)

    items, total = await service.get_filtered_out(name="Price")

    assert total == 1
    assert items[0].id == price.id
    assert [name for name, _ in price_repo.calls] == [
        "get_filtered",
        "get_price_groups",
        "get_price_photos",
    ]


async def test_create_uc21_repository_failure_bubbles_for_session_rollback() -> None:
    service, price_repo, *_ = make_service()
    price_repo.fail_on.add("create")

    with pytest.raises(RepositoryError):
        await service.create(PriceCreateDto(name="Price"))


async def test_price_service_uc30_has_no_fastapi_or_settings_dependency() -> None:
    import inspect

    import core.services.prices as prices_module

    module_source = inspect.getsource(prices_module)
    assert "fastapi" not in module_source
    assert "from settings import settings" not in module_source
