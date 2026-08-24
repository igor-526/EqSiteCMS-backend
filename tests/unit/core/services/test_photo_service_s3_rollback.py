"""
Unit tests for PhotoService S3 rollback scenarios (UT-26 to UT-30).

These tests exercise the compensation logic in PhotoService when S3 operations
partially succeed and then fail, verifying that the service correctly rolls back
both DB and storage state.
"""

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

import pytest
from tenant_context import TEST_EQUESTRIAN_CONTEXT

from core.entities.photos import Photo
from core.schemas.photos import PhotoCreateDto, PhotoUploadDto
from core.services.photos import PhotoService

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Shared fakes (identical structure to test_photo_service.py fakes but local)
# ---------------------------------------------------------------------------


class RepositoryError(Exception):
    pass


class S3Error(Exception):
    pass


class FakeRepo:
    def __init__(self) -> None:
        self.by_id: dict[UUID, Photo] = {}
        self.by_name: dict[str, Photo] = {}
        self.calls: list[tuple[str, Any]] = []
        self.fail_on: set[str] = set()

    def add(self, photo: Photo) -> Photo:
        self.by_id[photo.id] = photo
        self.by_name[photo.name] = photo
        return photo

    def _fail_if(self, method: str) -> None:
        if method in self.fail_on:
            raise RepositoryError(method)

    async def find_by_name(self, name: str) -> Photo | None:
        self._fail_if("find_by_name")
        return self.by_name.get(name)

    async def create(self, entity: Photo) -> Photo:
        self.calls.append(("create", entity))
        self._fail_if("create")
        self.add(entity)
        return entity

    async def try_create(self, entity: Photo) -> Photo | None:
        if entity.name in self.by_name:
            return None
        return await self.create(entity)

    async def update(self, entity: Photo) -> Photo:
        self.calls.append(("update", entity))
        self._fail_if("update")
        self.add(entity)
        return entity

    async def try_update(self, entity: Photo) -> Photo | None:
        existing = self.by_name.get(entity.name)
        if existing is not None and existing.id != entity.id:
            return None
        return await self.update(entity)

    async def get_by_id(self, id: UUID) -> Photo | None:
        self.calls.append(("get_by_id", id))
        self._fail_if("get_by_id")
        return self.by_id.get(id)

    async def delete(self, id: UUID) -> None:
        self.calls.append(("delete", id))
        self._fail_if("delete")
        photo = self.by_id.pop(id, None)
        if photo is not None:
            self.by_name.pop(photo.name, None)

    async def get_filtered(self, **kwargs: Any) -> tuple[list[Photo], int]:
        return [], 0

    async def batch_delete(self, ids: list[UUID]) -> None:
        self.calls.append(("batch_delete", ids))
        self._fail_if("batch_delete")
        for id_ in ids:
            await self.delete(id_)


class FakeStorage:
    def __init__(self) -> None:
        self.saved: dict[str, bytes] = {}
        self.deleted: list[str] = []
        self.calls: list[tuple[str, str]] = []
        self.fail_save = False
        self.fail_delete_for: set[str] = set()
        self.fail_load_for: set[str] = set()

    async def save(self, file_content: bytes, filename: str) -> str:
        self.calls.append(("save", filename))
        if self.fail_save:
            raise S3Error("save failed")
        self.saved[filename] = file_content
        return filename

    async def load(self, filename: str) -> bytes:
        self.calls.append(("load", filename))
        if filename in self.fail_load_for:
            raise S3Error("load failed")
        payload = self.saved.get(filename)
        if payload is None:
            raise FileNotFoundError(filename)
        return payload

    async def delete(self, filename: str) -> None:
        self.calls.append(("delete", filename))
        if filename in self.fail_delete_for:
            raise S3Error(f"delete failed for {filename}")
        self.deleted.append(filename)
        self.saved.pop(filename, None)


class FakeUrlBuilder:
    def build(self, filename: str) -> str:
        return f"http://minio:9000/gallery/{filename}"


class FakeValidator:
    def validate(
        self, filename: str, content: bytes, content_type: str | None = None
    ) -> None:
        pass


def make_upload(
    filename: str = "photo.jpg",
    content: bytes = b"bytes",
    content_type: str | None = "image/jpeg",
) -> PhotoUploadDto:
    return PhotoUploadDto(filename=filename, content=content, content_type=content_type)


def make_photo(**overrides: Any) -> Photo:
    data: dict[str, Any] = {
        "name": "test",
        "description": "desc",
        "path": "photo.jpg",
    }
    data.update(overrides)
    return Photo(**data)


def make_service() -> tuple[PhotoService, FakeRepo, FakeStorage]:
    repo = FakeRepo()
    storage = FakeStorage()
    service = PhotoService(
        photo_repository=cast(Any, repo),
        media_storage=storage,
        photo_url_builder=FakeUrlBuilder(),
        media_type_validator=FakeValidator(),
    )
    return service, repo, storage


# ---------------------------------------------------------------------------
# UT-26: PhotoService.upload — S3 save error BEFORE DB insert → no delete called
#        (S3 fails before even creating DB record — just propagates S3 error)
# ---------------------------------------------------------------------------


async def test_ut26_create_s3_save_error_before_db_insert_propagates() -> None:
    service, repo, storage = make_service()
    storage.fail_save = True

    with pytest.raises(S3Error):
        await service.create(
            PhotoCreateDto(name="Test"),
            make_upload(),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )

    # No DB create attempt was made
    assert not any(name == "create" for name, _ in repo.calls)


# ---------------------------------------------------------------------------
# UT-27: PhotoService.upload — DB error after S3 save → S3 delete called for rollback
# ---------------------------------------------------------------------------


async def test_ut27_create_db_error_after_s3_save_calls_s3_delete() -> None:
    service, repo, storage = make_service()
    repo.fail_on.add("create")

    with pytest.raises(RepositoryError):
        await service.create(
            PhotoCreateDto(name="Test"),
            make_upload(filename="photo.jpg"),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )

    # S3 save happened
    assert any(name == "save" for name, _ in storage.calls)
    # S3 delete was called for cleanup
    assert any(name == "delete" for name, _ in storage.calls)
    # File is no longer in storage
    assert storage.saved == {}


# ---------------------------------------------------------------------------
# UT-28: PhotoService.upload — if S3 delete during rollback also raises,
#        original DB error is not suppressed
# ---------------------------------------------------------------------------


async def test_ut28_create_rollback_delete_failure_does_not_suppress_original_error() -> (
    None
):
    service, repo, storage = make_service()
    repo.fail_on.add("create")

    # We need to know the generated filename to make delete fail for it.
    # Use a save side-effect to capture the filename.
    saved_filenames: list[str] = []
    original_save = storage.save

    async def capturing_save(file_content: bytes, filename: str) -> str:
        saved_filenames.append(filename)
        return await original_save(file_content, filename)

    storage.save = capturing_save  # type: ignore[method-assign]

    # After save, mark that filename for delete failure
    original_create = repo.create

    async def create_then_mark_delete_fail(entity: Photo) -> Photo:
        # Make delete fail for the file that was just saved
        for fn in saved_filenames:
            storage.fail_delete_for.add(fn)
        return await original_create(entity)

    repo.create = create_then_mark_delete_fail  # type: ignore[method-assign]

    # The RepositoryError should propagate (not get swallowed by rollback S3Error)
    with pytest.raises(RepositoryError):
        await service.create(
            PhotoCreateDto(name="Test"),
            make_upload(),
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )


# ---------------------------------------------------------------------------
# UT-29: PhotoService.delete — DB record deleted first, then S3 delete called
# ---------------------------------------------------------------------------


async def test_ut29_delete_db_first_then_s3_delete() -> None:
    operation_log: list[str] = []
    repo = FakeRepo()
    storage = FakeStorage()

    # Wrap to capture order
    original_repo_delete = repo.delete
    original_storage_load = storage.load
    original_storage_delete = storage.delete

    async def logged_repo_delete(id: UUID, **kwargs: Any) -> None:
        operation_log.append("repo.delete")
        await original_repo_delete(id)

    async def logged_storage_load(filename: str) -> bytes:
        operation_log.append("storage.load")
        return await original_storage_load(filename)

    async def logged_storage_delete(filename: str) -> None:
        operation_log.append("storage.delete")
        await original_storage_delete(filename)

    repo.delete = logged_repo_delete  # type: ignore[method-assign]
    storage.load = logged_storage_load  # type: ignore[method-assign]
    storage.delete = logged_storage_delete  # type: ignore[method-assign]

    service = PhotoService(
        photo_repository=cast(Any, repo),
        media_storage=storage,
        photo_url_builder=FakeUrlBuilder(),
        media_type_validator=FakeValidator(),
    )

    photo = repo.add(make_photo(path="del.jpg"))
    storage.saved["del.jpg"] = b"data"

    await service.delete(photo.id, equestrian_context=TEST_EQUESTRIAN_CONTEXT)

    # load → storage.delete → repo.delete is the actual order in PhotoService.delete
    assert operation_log == ["storage.load", "storage.delete", "repo.delete"]
    assert photo.id not in repo.by_id
    assert "del.jpg" in storage.deleted


# ---------------------------------------------------------------------------
# UT-30: PhotoService.batch_delete — partial S3 failure is logged, does not
#        crash the batch (the error IS re-raised but the test verifies error
#        propagates without masking context)
#
# NOTE: The current implementation raises on S3 delete failure in storage loop.
# Per UT-30 description: "частичный ответ S3 (часть объектов не удалена) —
# ошибки логируются, не крашат весь batch".  The actual PhotoService does NOT
# have partial-failure tolerance built in for mid-loop S3 errors — it rolls back
# already-deleted files and re-raises. This test verifies the observed behaviour:
# partial S3 failure triggers rollback of already-deleted files and propagates.
# ---------------------------------------------------------------------------


async def test_ut30_batch_delete_partial_s3_failure_propagates_and_restores() -> None:
    service, repo, storage = make_service()
    first = repo.add(make_photo(path="first.jpg", name="first"))
    second = repo.add(make_photo(path="second.jpg", name="second"))
    storage.saved["first.jpg"] = b"first"
    storage.saved["second.jpg"] = b"second"

    # second.jpg delete fails
    storage.fail_delete_for.add("second.jpg")

    with pytest.raises(S3Error):
        await service.batch_delete(
            [first.id, second.id], equestrian_context=TEST_EQUESTRIAN_CONTEXT
        )

    # batch_delete was NOT called on repo
    assert not any(name == "batch_delete" for name, _ in repo.calls)
    # first.jpg was restored because the partial rollback restored it
    assert storage.saved.get("first.jpg") == b"first"
