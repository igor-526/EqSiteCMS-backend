import uuid
from pathlib import Path
from typing import Literal
from uuid import UUID

from core.entities.equestrian import EquestrianContext
from core.entities.photos import Photo
from core.exceptions.base import ClientError
from core.protocols.media import (
    MediaStorageProtocol,
    MediaTypeValidatorProtocol,
    PhotoUrlBuilderProtocol,
)
from core.protocols.repositories.photo_repository import PhotoRepositoryProtocol
from core.schemas.photos import PhotoCreateDto, PhotoUpdateDto, PhotoUploadDto


class PhotoService:
    def __init__(
        self,
        photo_repository: PhotoRepositoryProtocol,
        media_storage: MediaStorageProtocol,
        photo_url_builder: PhotoUrlBuilderProtocol,
        media_type_validator: MediaTypeValidatorProtocol,
    ):
        self.photo_repository = photo_repository
        self.media_storage = media_storage
        self.photo_url_builder = photo_url_builder
        self.media_type_validator = media_type_validator

    async def _generate_unique_name(
        self,
        base_name: str,
        *,
        equestrian_context: EquestrianContext,
        exclude_id: UUID | None = None,
    ) -> str:
        counter = 1
        current_name = base_name

        while True:
            existing = await self.photo_repository.find_by_name(
                current_name, equestrian_id=equestrian_context.id
            )
            if existing is None or (
                exclude_id is not None and existing.id == exclude_id
            ):
                return current_name
            current_name = f"{base_name}-{counter}"
            counter += 1

    def _get_file_extension(self, filename: str) -> str:
        return Path(filename).suffix

    def _generate_filename(self, original_filename: str) -> str:
        extension = self._get_file_extension(original_filename)
        unique_id = str(uuid.uuid4())
        return f"{unique_id}{extension}"

    def build_url(self, filename: str) -> str:
        return self.photo_url_builder.build(filename)

    def _get_name_from_filename(self, filename: str) -> str:
        return Path(filename).stem

    def _validate_file_type(
        self, filename: str, content: bytes, content_type: str | None = None
    ) -> None:
        self.media_type_validator.validate(filename, content, content_type)

    async def _safe_delete_file(self, filename: str) -> None:
        try:
            await self.media_storage.delete(filename)
        except Exception:
            # Rollback path may call best-effort cleanup; preserve original error.
            pass

    async def _safe_restore_file(self, filename: str, payload: bytes) -> None:
        try:
            await self.media_storage.save(payload, filename)
        except Exception:
            # Rollback is best-effort; keep bubbling original error.
            pass

    async def create(
        self,
        data: PhotoCreateDto,
        upload: PhotoUploadDto,
        *,
        equestrian_context: EquestrianContext,
    ) -> Photo:
        if not upload.filename:
            raise ClientError("Имя файла не указано")
        self._validate_file_type(upload.filename, upload.content, upload.content_type)
        name = data.name
        if not name or name.strip() == "":
            name = self._get_name_from_filename(upload.filename)

        name = await self._generate_unique_name(
            name, equestrian_context=equestrian_context
        )
        description = data.description if data.description is not None else ""
        filename = self._generate_filename(upload.filename)
        await self.media_storage.save(upload.content, filename)

        photo = Photo(
            equestrian_id=equestrian_context.id,
            name=name,
            description=description,
            path=filename,
        )
        try:
            return await self.photo_repository.create(photo)
        except Exception:
            await self._safe_delete_file(filename)
            raise

    async def update(
        self,
        id: UUID,
        data: PhotoUpdateDto,
        *,
        equestrian_context: EquestrianContext,
        upload: PhotoUploadDto | None = None,
    ) -> Photo:
        photo = await self.photo_repository.get_by_id(
            id, equestrian_id=equestrian_context.id
        )
        if photo is None:
            raise ClientError("Фотография не найдена")

        old_filename: str | None = None
        new_filename: str | None = None
        file_changed = False
        if upload is not None:
            if not upload.filename:
                raise ClientError("Имя файла не указано")
            self._validate_file_type(
                upload.filename, upload.content, upload.content_type
            )
            old_filename = photo.path
            new_filename = self._generate_filename(upload.filename)
            await self.media_storage.save(upload.content, new_filename)
            photo.path = new_filename
            file_changed = True

        update_data = {}

        if data.name is not None:
            name_value = data.name
            if not name_value or name_value.strip() == "":
                if upload is not None:
                    name_value = self._get_name_from_filename(upload.filename)
                else:
                    name_value = self._get_name_from_filename(photo.path)

            name_value = await self._generate_unique_name(
                name_value,
                equestrian_context=equestrian_context,
                exclude_id=photo.id,
            )
            update_data["name"] = name_value

        if data.description is not None:
            update_data["description"] = data.description

        for key, value in update_data.items():
            setattr(photo, key, value)

        if not file_changed and not update_data:
            return photo

        try:
            updated = await self.photo_repository.update(photo)
        except Exception:
            if old_filename is not None and new_filename is not None:
                photo.path = old_filename
                await self._safe_delete_file(new_filename)
            raise

        if old_filename is not None and new_filename is not None:
            try:
                await self.media_storage.delete(old_filename)
            except Exception:
                photo.path = old_filename
                try:
                    await self.photo_repository.update(photo)
                except Exception:
                    await self._safe_delete_file(new_filename)
                    raise
                await self._safe_delete_file(new_filename)
                raise

        return updated

    async def get_by_id(
        self, id: UUID, *, equestrian_context: EquestrianContext
    ) -> Photo | None:
        return await self.photo_repository.get_by_id(
            id, equestrian_id=equestrian_context.id
        )

    async def delete(self, id: UUID, *, equestrian_context: EquestrianContext) -> None:
        photo = await self.photo_repository.get_by_id(
            id, equestrian_id=equestrian_context.id
        )
        if photo is None:
            raise ClientError("Фотография не найдена")

        deleted_payload = await self.media_storage.load(photo.path)
        await self.media_storage.delete(photo.path)
        try:
            await self.photo_repository.delete(id, equestrian_id=equestrian_context.id)
        except Exception:
            await self._safe_restore_file(photo.path, deleted_payload)
            raise

    async def get_filtered(
        self,
        *,
        equestrian_context: EquestrianContext,
        name: str | None = None,
        description: str | None = None,
        price_ids: list[UUID] | None = None,
        horse_ids: list[UUID] | None = None,
        sort: (
            list[
                Literal[
                    "name",
                    "description",
                    "created_at",
                    "-name",
                    "-description",
                    "-created_at",
                ]
            ]
            | None
        ) = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[list[Photo], int]:
        return await self.photo_repository.get_filtered(
            equestrian_id=equestrian_context.id,
            name=name,
            description=description,
            price_ids=price_ids,
            horse_ids=horse_ids,
            sort=sort,
            limit=limit,
            offset=offset,
        )

    async def batch_delete(
        self, ids: list[UUID], *, equestrian_context: EquestrianContext
    ) -> None:
        if not ids:
            return

        existing_photos: list[Photo] = []
        for photo_id in ids:
            photo = await self.photo_repository.get_by_id(
                photo_id, equestrian_id=equestrian_context.id
            )
            if photo is None:
                continue
            existing_photos.append(photo)

        if not existing_photos:
            return

        deleted_files: list[tuple[str, bytes]] = []
        try:
            for photo in existing_photos:
                payload = await self.media_storage.load(photo.path)
                await self.media_storage.delete(photo.path)
                deleted_files.append((photo.path, payload))
        except Exception:
            # Rollback intent: restore already deleted files if storage loop fails midway.
            for filename, payload in reversed(deleted_files):
                await self._safe_restore_file(filename, payload)
            raise

        existing_ids = [photo.id for photo in existing_photos]
        try:
            await self.photo_repository.batch_delete(
                existing_ids, equestrian_id=equestrian_context.id
            )
        except Exception:
            # Rollback intent: try to restore media files if DB deletion fails.
            for filename, payload in reversed(deleted_files):
                await self._safe_restore_file(filename, payload)
            raise
