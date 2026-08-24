from __future__ import annotations

from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from tenant_context import TEST_EQUESTRIAN_CONTEXT

from core.entities.photos import Photo
from core.exceptions.base import ClientError
from core.schemas.photos import PhotoCreateDto, PhotoUpdateDto, PhotoUploadDto
from core.services.photos import PhotoService

pytestmark = pytest.mark.asyncio


class RepositoryError(Exception):
    pass


class StorageError(Exception):
    pass


class FakePhotoRepository:
    def __init__(self, operation_log: list[str] | None = None) -> None:
        self.by_id: dict[UUID, Photo] = {}
        self.by_name: dict[str, Photo] = {}
        self.calls: list[tuple[str, Any]] = []
        self.operation_log = operation_log if operation_log is not None else []
        self.filtered_result: tuple[list[Photo], int] = ([], 0)
        self.fail_on: set[str] = set()

    def add(self, photo: Photo) -> Photo:
        self.by_id[photo.id] = photo
        self.by_name[photo.name] = photo
        return photo

    def _fail_if_needed(self, method: str) -> None:
        if method in self.fail_on:
            raise RepositoryError(method)

    async def find_by_name(self, name: str) -> Photo | None:
        self.calls.append(("find_by_name", name))
        self.operation_log.append("repo.find_by_name")
        self._fail_if_needed("find_by_name")
        return self.by_name.get(name)

    async def create(self, entity: Photo) -> Photo:
        self.calls.append(("create", entity))
        self.operation_log.append("repo.create")
        self._fail_if_needed("create")
        self.add(entity)
        return entity

    async def try_create(self, entity: Photo) -> Photo | None:
        if entity.name in self.by_name:
            return None
        return await self.create(entity)

    async def update(self, entity: Photo) -> Photo:
        self.calls.append(("update", entity))
        self.operation_log.append("repo.update")
        self._fail_if_needed("update")
        self.add(entity)
        return entity

    async def try_update(self, entity: Photo) -> Photo | None:
        existing = self.by_name.get(entity.name)
        if existing is not None and existing.id != entity.id:
            return None
        return await self.update(entity)

    async def get_by_id(self, id: UUID) -> Photo | None:
        self.calls.append(("get_by_id", id))
        self.operation_log.append("repo.get_by_id")
        self._fail_if_needed("get_by_id")
        return self.by_id.get(id)

    async def delete(self, id: UUID) -> None:
        self.calls.append(("delete", id))
        self.operation_log.append("repo.delete")
        self._fail_if_needed("delete")
        photo = self.by_id.pop(id, None)
        if photo is not None:
            self.by_name.pop(photo.name, None)

    async def get_filtered(
        self,
        *,
        name: str | None = None,
        description: str | None = None,
        price_ids: list[UUID] | None = None,
        horse_ids: list[UUID] | None = None,
        sort: list[str] | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[list[Photo], int]:
        self.calls.append(
            (
                "get_filtered",
                {
                    "name": name,
                    "description": description,
                    "price_ids": price_ids,
                    "horse_ids": horse_ids,
                    "sort": sort,
                    "limit": limit,
                    "offset": offset,
                },
            )
        )
        self.operation_log.append("repo.get_filtered")
        self._fail_if_needed("get_filtered")
        return self.filtered_result

    async def batch_delete(self, ids: list[UUID]) -> None:
        self.calls.append(("batch_delete", ids))
        self.operation_log.append("repo.batch_delete")
        self._fail_if_needed("batch_delete")
        for id_ in ids:
            await self.delete(id_)


class FakeMediaStorage:
    def __init__(self, operation_log: list[str] | None = None) -> None:
        self.saved: dict[str, bytes] = {}
        self.deleted: list[str] = []
        self.calls: list[tuple[str, str]] = []
        self.operation_log = operation_log if operation_log is not None else []
        self.fail_on_save = False
        self.fail_on_load_for: set[str] = set()
        self.fail_on_delete_for: set[str] = set()

    async def save(self, file_content: bytes, filename: str) -> str:
        self.calls.append(("save", filename))
        self.operation_log.append(f"storage.save:{filename}")
        if self.fail_on_save:
            raise StorageError("save")
        self.saved[filename] = file_content
        return filename

    async def load(self, filename: str) -> bytes:
        self.calls.append(("load", filename))
        self.operation_log.append(f"storage.load:{filename}")
        if filename in self.fail_on_load_for:
            raise StorageError("load")
        payload = self.saved.get(filename)
        if payload is None:
            raise FileNotFoundError(filename)
        return payload

    async def delete(self, filename: str) -> None:
        self.calls.append(("delete", filename))
        self.operation_log.append(f"storage.delete:{filename}")
        if filename in self.fail_on_delete_for:
            raise StorageError("delete")
        self.deleted.append(filename)
        self.saved.pop(filename, None)


class FakePhotoUrlBuilder:
    def __init__(self, prefix: str = "https://cdn.local/media") -> None:
        self.prefix = prefix

    def build(self, filename: str) -> str:
        return f"{self.prefix}/{filename}"


class FakeMediaTypeValidator:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int, str | None]] = []
        self.fail_for: set[str] = set()

    def validate(
        self, filename: str, content: bytes, content_type: str | None = None
    ) -> None:
        self.calls.append((filename, len(content), content_type))
        if filename in self.fail_for:
            raise ClientError("invalid media type")


def make_photo(**overrides: Any) -> Photo:
    data = {
        "name": "photo",
        "description": "desc",
        "path": "photo.png",
    }
    data.update(overrides)
    return Photo(**data)


def make_upload(
    filename: str = "photo.png",
    content: bytes = b"data",
    content_type: str | None = "image/png",
) -> PhotoUploadDto:
    return PhotoUploadDto(
        filename=filename,
        content=content,
        content_type=content_type,
    )


def make_service(
    operation_log: list[str] | None = None,
) -> tuple[PhotoService, FakePhotoRepository, FakeMediaStorage, FakeMediaTypeValidator]:
    repo = FakePhotoRepository(operation_log)
    storage = FakeMediaStorage(operation_log)
    media_type_validator = FakeMediaTypeValidator()
    service = PhotoService(
        photo_repository=cast(Any, repo),
        media_storage=storage,
        photo_url_builder=FakePhotoUrlBuilder(),
        media_type_validator=media_type_validator,
    )
    return service, repo, storage, media_type_validator


async def test_generate_unique_name_uc01_uc14_uc15_returns_available_suffix() -> None:
    service, repo, _, _ = make_service()
    existing = repo.add(make_photo(name="Hero"))

    assert (
        await service._generate_unique_name(
            "New", equestrian_context=TEST_EQUESTRIAN_CONTEXT
        )
        == "New"
    )
    assert (
        await service._generate_unique_name(
            "Hero", equestrian_context=TEST_EQUESTRIAN_CONTEXT
        )
        == "Hero-2"
    )
    assert (
        await service._generate_unique_name(
            "Hero", exclude_id=existing.id, equestrian_context=TEST_EQUESTRIAN_CONTEXT
        )
        == "Hero"
    )


async def test_file_name_helpers_uc01_uc07_uc12_handle_extensions_and_unicode() -> None:
    service, _, _, _ = make_service()

    generated = service._generate_filename("Фото.HEIC")
    generated_stem, generated_extension = generated.rsplit(".", maxsplit=1)

    UUID(generated_stem)
    assert service._get_file_extension("archive.tar.gz") == ".gz"
    assert generated_extension == "HEIC"
    assert service._get_name_from_filename("  Лошадь 01.png") == "  Лошадь 01"


async def test_validate_file_type_uc22_uc29_passes_content_type_to_validator() -> None:
    service, _, _, media_type_validator = make_service()

    service._validate_file_type("image.png", b"content", "image/png")

    assert media_type_validator.calls == [("image.png", 7, "image/png")]


async def test_create_uc01_uc22_saves_then_creates_entity() -> None:
    operation_log: list[str] = []
    service, repo, storage, _ = make_service(operation_log)

    created = await service.create(
        PhotoCreateDto(name="Hero", description="Main"),
        make_upload(filename="hero.png"),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert created.name == "Hero"
    assert created.description == "Main"
    assert [name for name, _ in storage.calls] == ["save"]
    assert [name for name, _ in repo.calls] == ["create"]
    assert operation_log == [
        f"storage.save:{created.path}",
        "repo.create",
    ]


async def test_create_uc02_uc04_defaults_name_and_description() -> None:
    service, _, _, _ = make_service()

    created = await service.create(
        PhotoCreateDto(),
        make_upload(filename="my-photo.jpeg"),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert created.name == "my-photo"
    assert created.description == ""


async def test_create_uc12_empty_filename_is_client_error() -> None:
    service, repo, storage, _ = make_service()

    with pytest.raises(ClientError):
        await service.create(
            PhotoCreateDto(name="X"),
            make_upload(filename=""),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )

    assert repo.calls == []
    assert storage.calls == []


async def test_create_uc14_duplicate_name_gets_suffix() -> None:
    service, repo, _, _ = make_service()
    repo.add(make_photo(name="Photo"))

    created = await service.create(
        PhotoCreateDto(name="Photo"),
        make_upload(filename="x.png"),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert created.name == "Photo-2"


async def test_create_uc29_invalid_extension_uses_client_error() -> None:
    service, repo, storage, media_type_validator = make_service()
    media_type_validator.fail_for.add("doc.txt")

    with pytest.raises(ClientError):
        await service.create(
            PhotoCreateDto(name="Doc"),
            make_upload(filename="doc.txt", content=b"text", content_type="text/plain"),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )

    assert repo.calls == []
    assert storage.calls == []


async def test_create_uc23_rolls_back_saved_file_on_repository_failure() -> None:
    service, repo, storage, _ = make_service()
    repo.fail_on.add("create")

    with pytest.raises(RepositoryError):
        await service.create(
            PhotoCreateDto(name="Hero"),
            make_upload(filename="hero.png"),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )

    assert any(name == "save" for name, _ in storage.calls)
    assert any(name == "delete" for name, _ in storage.calls)
    assert storage.saved == {}


async def test_update_uc01_uc19_updates_only_provided_fields() -> None:
    service, repo, _, _ = make_service()
    photo = repo.add(make_photo(name="Old", description="Old desc"))

    updated = await service.update(
        photo.id,
        PhotoUpdateDto(description="New desc"),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert updated.name == "Old"
    assert updated.description == "New desc"


async def test_update_uc19_fixes_description_assignment_bug() -> None:
    service, repo, _, _ = make_service()
    photo = repo.add(make_photo(description="Old"))

    updated = await service.update(
        photo.id,
        PhotoUpdateDto(description="Exact value"),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert updated.description == "Exact value"


async def test_update_uc13_not_found_is_client_error() -> None:
    service, _, _, _ = make_service()

    with pytest.raises(ClientError):
        await service.update(
            uuid4(),
            PhotoUpdateDto(name="X"),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )


async def test_update_uc20_empty_update_is_noop() -> None:
    service, repo, storage, _ = make_service()
    photo = repo.add(make_photo(name="Still", description="Same"))

    updated = await service.update(
        photo.id, PhotoUpdateDto(), equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )

    assert updated == photo
    assert [name for name, _ in repo.calls] == ["get_by_id"]
    assert storage.calls == []


async def test_update_uc22_forwards_upload_content_type_to_validator() -> None:
    service, repo, _, media_type_validator = make_service()
    photo = repo.add(make_photo(path="old.png"))

    await service.update(
        photo.id,
        PhotoUpdateDto(),
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        upload=make_upload(
            filename="clip.mp4", content=b"video", content_type="video/mp4"
        ),
    )

    assert media_type_validator.calls == [("clip.mp4", 5, "video/mp4")]


async def test_update_uc22_uc23_replaces_file_and_rolls_back_on_delete_failure() -> (
    None
):
    service, repo, storage, _ = make_service()
    photo = repo.add(make_photo(path="old.png"))
    storage.saved["old.png"] = b"old"
    storage.fail_on_delete_for.add("old.png")

    with pytest.raises(StorageError):
        await service.update(
            photo.id,
            PhotoUpdateDto(),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
            upload=make_upload(filename="new.png", content=b"new"),
        )

    assert photo.path == "old.png"
    assert "old.png" in storage.saved
    assert any(name == "update" for name, _ in repo.calls)
    assert any(name == "delete" and fn != "old.png" for name, fn in storage.calls)


async def test_update_uc23_rolls_back_saved_file_on_repository_failure() -> None:
    service, repo, storage, _ = make_service()
    photo = repo.add(make_photo(path="old.png"))
    storage.saved["old.png"] = b"old"
    repo.fail_on.add("update")

    with pytest.raises(RepositoryError):
        await service.update(
            photo.id,
            PhotoUpdateDto(),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
            upload=make_upload(filename="new.png", content=b"new"),
        )

    assert photo.path == "old.png"
    assert "old.png" in storage.saved
    assert all(filename != "old.png" for filename in storage.deleted)
    assert storage.saved == {"old.png": b"old"}


async def test_delete_uc01_deletes_storage_before_repository() -> None:
    operation_log: list[str] = []
    service, repo, storage, _ = make_service(operation_log)
    photo = repo.add(make_photo(path="to-delete.png"))
    storage.saved["to-delete.png"] = b"payload"

    await service.delete(photo.id, equestrian_context=TEST_EQUESTRIAN_CONTEXT)

    assert storage.deleted == ["to-delete.png"]
    assert [name for name, _ in repo.calls] == ["get_by_id", "delete"]
    assert operation_log == [
        "repo.get_by_id",
        "storage.load:to-delete.png",
        "storage.delete:to-delete.png",
        "repo.delete",
    ]


async def test_delete_uc23_storage_failure_prevents_repository_delete() -> None:
    service, repo, storage, _ = make_service()
    photo = repo.add(make_photo(path="blocked.png"))
    storage.saved["blocked.png"] = b"payload"
    storage.fail_on_delete_for.add("blocked.png")

    with pytest.raises(StorageError):
        await service.delete(photo.id, equestrian_context=TEST_EQUESTRIAN_CONTEXT)

    assert [name for name, _ in repo.calls] == ["get_by_id"]


async def test_delete_uc23_repository_failure_restores_deleted_file() -> None:
    service, repo, storage, _ = make_service()
    photo = repo.add(make_photo(path="restore.png"))
    storage.saved["restore.png"] = b"payload"
    repo.fail_on.add("delete")

    with pytest.raises(RepositoryError):
        await service.delete(photo.id, equestrian_context=TEST_EQUESTRIAN_CONTEXT)

    assert storage.deleted == ["restore.png"]
    assert storage.saved["restore.png"] == b"payload"
    assert [name for name, _ in repo.calls] == ["get_by_id", "delete"]


async def test_batch_delete_uc13_skips_missing_and_deletes_existing_only() -> None:
    service, repo, storage, _ = make_service()
    existing = repo.add(make_photo(path="exists.png"))
    storage.saved["exists.png"] = b"payload"
    missing_id = uuid4()

    await service.batch_delete(
        [existing.id, missing_id], equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )

    assert storage.deleted == ["exists.png"]
    assert ("batch_delete", [existing.id]) in repo.calls


async def test_batch_delete_uc22_deletes_storage_before_repository_batch_delete() -> (
    None
):
    operation_log: list[str] = []
    service, repo, storage, _ = make_service(operation_log)
    first = repo.add(make_photo(path="first.png"))
    second = repo.add(make_photo(path="second.png"))
    storage.saved["first.png"] = b"first"
    storage.saved["second.png"] = b"second"

    await service.batch_delete(
        [first.id, second.id], equestrian_context=TEST_EQUESTRIAN_CONTEXT
    )

    assert storage.deleted == ["first.png", "second.png"]
    assert operation_log == [
        "repo.get_by_id",
        "repo.get_by_id",
        "storage.load:first.png",
        "storage.delete:first.png",
        "storage.load:second.png",
        "storage.delete:second.png",
        "repo.batch_delete",
        "repo.delete",
        "repo.delete",
    ]


async def test_batch_delete_uc23_storage_failure_prevents_repository_batch_delete() -> (
    None
):
    service, repo, storage, _ = make_service()
    photo = repo.add(make_photo(path="blocked.png"))
    storage.saved["blocked.png"] = b"blocked"
    storage.fail_on_delete_for.add("blocked.png")

    with pytest.raises(StorageError):
        await service.batch_delete(
            [photo.id], equestrian_context=TEST_EQUESTRIAN_CONTEXT
        )

    assert ("batch_delete", [photo.id]) not in repo.calls


async def test_batch_delete_uc23_partial_storage_failure_restores_deleted_files() -> (
    None
):
    service, repo, storage, _ = make_service()
    first = repo.add(make_photo(path="first.png"))
    second = repo.add(make_photo(path="second.png"))
    storage.saved["first.png"] = b"first"
    storage.saved["second.png"] = b"second"
    storage.fail_on_delete_for.add("second.png")

    with pytest.raises(StorageError):
        await service.batch_delete(
            [first.id, second.id], equestrian_context=TEST_EQUESTRIAN_CONTEXT
        )

    assert ("batch_delete", [first.id, second.id]) not in repo.calls
    assert storage.saved["first.png"] == b"first"
    assert storage.saved["second.png"] == b"second"


async def test_batch_delete_uc23_repository_failure_after_storage_delete_is_visible() -> (
    None
):
    service, repo, storage, _ = make_service()
    photo = repo.add(make_photo(path="deleted-first.png"))
    storage.saved["deleted-first.png"] = b"payload"
    repo.fail_on.add("batch_delete")

    with pytest.raises(RepositoryError):
        await service.batch_delete(
            [photo.id], equestrian_context=TEST_EQUESTRIAN_CONTEXT
        )

    assert storage.deleted == ["deleted-first.png"]
    assert storage.saved["deleted-first.png"] == b"payload"


async def test_get_filtered_uc25_uc26_uc27_passes_filters_through() -> None:
    service, repo, _, _ = make_service()
    photos = [make_photo(name="A"), make_photo(name="B")]
    repo.filtered_result = (photos, 2)

    entities, total = await service.get_filtered(
        name="A",
        description="desc",
        price_ids=[uuid4()],
        horse_ids=[uuid4()],
        sort=["name", "-created_at"],
        limit=10,
        offset=20,
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    assert entities == photos
    assert total == 2
    assert repo.calls[-1][0] == "get_filtered"


async def test_build_url_uc28_uses_url_builder() -> None:
    service, _, _, _ = make_service()
    assert service.build_url("image.png") == "https://cdn.local/media/image.png"


async def test_photo_service_uc30_has_no_fastapi_or_settings_dependency() -> None:
    import inspect

    import core.services.photos as photos_module

    module_source = inspect.getsource(photos_module)
    assert "fastapi" not in module_source
    assert "from settings import settings" not in module_source
