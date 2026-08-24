from __future__ import annotations

import hashlib
import unicodedata
from importlib import import_module
from typing import Any
from uuid import uuid4

import pytest
from tenant_context import TEST_EQUESTRIAN_CONTEXT

from core.exceptions.base import ClientError, ConflictError
from core.photo_names import (
    MAX_PHOTO_NAME_LENGTH,
    add_name_discriminator,
    build_bounded_photo_name,
    normalize_photo_name,
)
from core.schemas.photos import PhotoCreateDto, PhotoUpdateDto

photo_test_helpers = import_module("tests.unit.core.services.test_photo_service")
make_photo = photo_test_helpers.make_photo
make_service = photo_test_helpers.make_service
make_upload = photo_test_helpers.make_upload


def create_identity(content: bytes = b"data") -> bytes:
    return b"C" + hashlib.sha256(content).digest()


def test_exactly_63_ascii_is_unchanged() -> None:
    value = "a" * 63
    assert build_bounded_photo_name(value, identity=create_identity()) == value


def test_64_ascii_gets_digest_and_is_bounded() -> None:
    result = build_bounded_photo_name("a" * 64, identity=create_identity())
    assert len(result) == 63
    assert result[-13] == "-"
    assert len(result.rsplit("-", maxsplit=1)[1]) == 12


def test_63_unicode_codepoints_are_not_counted_as_bytes() -> None:
    value = "馬" * 63
    assert build_bounded_photo_name(value, identity=create_identity()) == value


def test_64_unicode_codepoints_are_sliced_safely() -> None:
    result = build_bounded_photo_name("🐴" * 64, identity=create_identity())
    assert len(result) == 63
    assert result.startswith("🐴")


def test_normalization_uses_nfc() -> None:
    composed = normalize_photo_name("café.jpg")
    decomposed = normalize_photo_name("cafe\u0301.jpg")
    assert composed == decomposed
    assert unicodedata.is_normalized("NFC", decomposed.full_name)


@pytest.mark.parametrize(
    ("source", "expected"),
    [("folder/photo.jpg", "photo.jpg"), (r"folder\photo.jpg", "photo.jpg")],
)
def test_normalization_removes_path_components(source: str, expected: str) -> None:
    assert normalize_photo_name(source).full_name == expected


def test_normalization_removes_controls_and_falls_back() -> None:
    assert normalize_photo_name("\x00\n\t").full_name == "photo"


def test_safe_extension_is_limited_to_ten_codepoints() -> None:
    normalized = normalize_photo_name("photo.abcdefghijklmnop")
    assert normalized.extension == ".abcdefghi"
    assert len(normalized.extension) == 10


def test_discriminator_is_inserted_before_extension() -> None:
    value = "a" * 59 + ".jpg"
    assert add_name_discriminator(value, 100).endswith("-100.jpg")
    assert len(add_name_discriminator(value, 100)) <= MAX_PHOTO_NAME_LENGTH


def test_discriminator_preserves_long_name_digest() -> None:
    base = build_bounded_photo_name("x" * 100 + ".jpg", identity=create_identity())
    digest = base.rsplit("-", maxsplit=1)[1][:-4]
    duplicate = add_name_discriminator(base, 2)
    assert duplicate.endswith(f"-{digest}-2.jpg")
    assert len(duplicate) == 63


def test_long_name_digest_changes_with_content() -> None:
    value = "same" * 30 + ".jpg"
    first = build_bounded_photo_name(value, identity=create_identity(b"first"))
    second = build_bounded_photo_name(value, identity=create_identity(b"second"))
    assert first != second


def test_long_name_digest_is_deterministic() -> None:
    value = "same" * 30 + ".jpg"
    assert build_bounded_photo_name(
        value, identity=create_identity()
    ) == build_bounded_photo_name(value, identity=create_identity())


@pytest.mark.asyncio
async def test_create_long_filename_fallback_is_bounded() -> None:
    service, _, _, _ = make_service()
    created = await service.create(
        PhotoCreateDto(),
        make_upload(filename=f"{'x' * 100}.jpg"),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )
    assert len(created.name) <= 63
    assert created.name.endswith(".jpg")


@pytest.mark.parametrize("name", [None, "", "   "])
@pytest.mark.asyncio
async def test_create_empty_name_uses_filename_stem(name: str | None) -> None:
    service, _, _, _ = make_service()
    created = await service.create(
        PhotoCreateDto(name=name),
        make_upload(filename="fallback.jpg"),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )
    assert created.name == "fallback"


@pytest.mark.asyncio
async def test_duplicate_short_name_uses_two_suffix() -> None:
    service, repo, _, _ = make_service()
    repo.add(make_photo(name="photo.jpg"))
    created = await service.create(
        PhotoCreateDto(name="photo.jpg"),
        make_upload(),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )
    assert created.name == "photo-2.jpg"


@pytest.mark.asyncio
async def test_multiple_collisions_rebudget_multi_digit_suffix() -> None:
    service, repo, _, _ = make_service()
    base = "a" * 59 + ".jpg"
    for attempt in range(1, 12):
        repo.add(make_photo(name=add_name_discriminator(base, attempt)))
    created = await service.create(
        PhotoCreateDto(name=base),
        make_upload(),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )
    assert created.name.endswith("-12.jpg")
    assert len(created.name) == 63


@pytest.mark.asyncio
async def test_update_long_name_uses_photo_uuid_identity() -> None:
    service, repo, _, _ = make_service()
    photo = repo.add(make_photo(name="old"))
    value = "rename" * 20 + ".png"
    updated = await service.update(
        photo.id,
        PhotoUpdateDto(name=value),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )
    expected = build_bounded_photo_name(value, identity=b"U" + photo.id.bytes)
    assert updated.name == expected


@pytest.mark.asyncio
async def test_update_long_name_with_new_file_still_uses_uuid_identity() -> None:
    service, repo, storage, _ = make_service()
    photo = repo.add(make_photo(name="old", path="old.jpg"))
    storage.saved["old.jpg"] = b"old"
    value = "rename" * 20 + ".png"
    updated = await service.update(
        photo.id,
        PhotoUpdateDto(name=value),
        upload=make_upload(content=b"different-content"),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )
    assert updated.name == build_bounded_photo_name(
        value, identity=b"U" + photo.id.bytes
    )


@pytest.mark.asyncio
async def test_duplicate_lookup_receives_tenant_scope() -> None:
    service, repo, _, _ = make_service()
    observed_tenant = None

    async def observe(_: str, *, equestrian_id: Any) -> None:
        nonlocal observed_tenant
        observed_tenant = equestrian_id
        return None

    repo.find_by_name = observe  # type: ignore[method-assign]
    await service._generate_unique_name(
        "available", equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )
    assert observed_tenant == TEST_EQUESTRIAN_CONTEXT.id


@pytest.mark.asyncio
async def test_same_long_rename_is_stable_and_excludes_self() -> None:
    service, repo, _, _ = make_service()
    photo = repo.add(make_photo(name="old"))
    value = "rename" * 20
    first = await service.update(
        photo.id, PhotoUpdateDto(name=value), equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )
    second = await service.update(
        photo.id, PhotoUpdateDto(name=value), equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )
    assert first.name == second.name
    assert not second.name.endswith("-2")


@pytest.mark.asyncio
async def test_same_long_rename_differs_for_two_photo_ids() -> None:
    value = "rename" * 20
    first = build_bounded_photo_name(value, identity=b"U" + uuid4().bytes)
    second = build_bounded_photo_name(value, identity=b"U" + uuid4().bytes)
    assert first != second


@pytest.mark.asyncio
async def test_update_name_none_does_not_rename() -> None:
    service, repo, _, _ = make_service()
    photo = repo.add(make_photo(name="unchanged"))
    updated = await service.update(
        photo.id,
        PhotoUpdateDto(description="new"),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )
    assert updated.name == "unchanged"


@pytest.mark.asyncio
async def test_update_not_found_has_no_storage_mutation() -> None:
    service, _, storage, _ = make_service()
    with pytest.raises(ClientError):
        await service.update(
            uuid4(),
            PhotoUpdateDto(name="new"),
            upload=make_upload(),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )
    assert storage.calls == []


@pytest.mark.asyncio
async def test_atomic_create_retry_uses_next_candidate() -> None:
    service, repo, _, _ = make_service()
    original = repo.try_create
    attempts = 0

    async def collide_once(entity: Any) -> Any:
        nonlocal attempts
        attempts += 1
        return None if attempts == 1 else await original(entity)

    repo.try_create = collide_once  # type: ignore[method-assign]
    created = await service.create(
        PhotoCreateDto(name="race.jpg"),
        make_upload(),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )
    assert created.name == "race-2.jpg"


@pytest.mark.asyncio
async def test_atomic_create_retry_exhaustion_is_conflict() -> None:
    service, repo, storage, _ = make_service()

    async def always_collide(_: Any) -> None:
        return None

    repo.try_create = always_collide  # type: ignore[method-assign]
    with pytest.raises(ConflictError):
        await service.create(
            PhotoCreateDto(name="race.jpg"),
            make_upload(),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )
    assert storage.saved == {}
