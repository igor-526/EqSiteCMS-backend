import os
import uuid
from pathlib import Path
from typing import Literal
from uuid import UUID

from core.entities.photos import Photo
from core.exceptions.base import ClientError
from core.protocols.repositories.photo_repository import PhotoRepositoryProtocol
from core.schemas.photos import PhotoCreateDto, PhotoUpdateDto
from settings import settings


class PhotoService:
    def __init__(self, photo_repository: PhotoRepositoryProtocol):
        self.photo_repository = photo_repository
        self.media_dir = Path(__file__).parent.parent.parent / "media"
        self.media_dir.mkdir(parents=True, exist_ok=True)

    async def _generate_unique_name(
        self, base_name: str, exclude_id: UUID | None = None
    ) -> str:
        counter = 1
        current_name = base_name

        while True:
            existing = await self.photo_repository.find_by_name(current_name)
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

    def _get_file_path(self, filename: str) -> Path:
        return self.media_dir / filename

    def _get_url(self, filename: str) -> str:
        protocol = "https" if not settings.debug else "http"
        return f"{protocol}://{settings.cms_backend_domain}/media/{filename}"

    async def _save_file(self, file_content: bytes, filename: str) -> str:
        import asyncio

        file_path = self._get_file_path(filename)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: file_path.write_bytes(file_content))
        return filename

    async def _delete_file(self, filename: str) -> None:
        import asyncio

        file_path = self._get_file_path(filename)
        if file_path.exists():
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, file_path.unlink)

    def _get_name_from_filename(self, filename: str) -> str:
        return Path(filename).stem

    def _validate_file_type(self, filename: str, content: bytes) -> None:
        extension = self._get_file_extension(filename).lower()

        image_extensions = {
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".bmp",
            ".webp",
            ".svg",
            ".ico",
            ".tiff",
            ".tif",
            ".heic",
            ".heif",
        }

        video_extensions = {
            ".mp4",
            ".avi",
            ".mov",
            ".wmv",
            ".flv",
            ".webm",
            ".mkv",
            ".m4v",
            ".3gp",
            ".ogv",
            ".mpeg",
            ".mpg",
        }

        allowed_extensions = image_extensions | video_extensions

        if extension not in allowed_extensions:
            raise ClientError(
                f"Недопустимый тип файла: {extension}. "
                f"Разрешены только изображения и видео файлы"
            )

    async def create_from_upload(
        self, data: PhotoCreateDto, file, original_filename: str | None
    ) -> Photo:
        from fastapi import UploadFile

        from core.exceptions.base import ClientError

        if not original_filename:
            raise ClientError("Имя файла не указано")

        file_content = await file.read()
        return await self.create(data, file_content, original_filename)

    async def create(
        self, data: PhotoCreateDto, file_content: bytes, original_filename: str
    ) -> Photo:
        self._validate_file_type(original_filename, file_content)
        filename = self._generate_filename(original_filename)
        await self._save_file(file_content, filename)

        name = data.name
        if not name or name.strip() == "":
            name = self._get_name_from_filename(original_filename)

        name = await self._generate_unique_name(name)
        description = data.description if data.description is not None else ""

        photo = Photo(
            name=name,
            description=description,
            path=filename,
        )

        return await self.photo_repository.create(photo)

    async def update_from_upload(
        self, id: UUID, data: PhotoUpdateDto, file, original_filename: str | None
    ) -> Photo:
        from fastapi import UploadFile

        from core.exceptions.base import ClientError

        file_content = None
        filename = None

        if file:
            if not original_filename:
                raise ClientError("Имя файла не указано")
            file_content = await file.read()
            filename = original_filename

        return await self.update(id, data, file_content, filename)

    async def update(
        self,
        id: UUID,
        data: PhotoUpdateDto,
        file_content: bytes | None = None,
        original_filename: str | None = None,
    ) -> Photo:
        photo = await self.photo_repository.get_by_id(id)
        if photo is None:
            raise ClientError("Фотография не найдена")

        if file_content is not None and original_filename is not None:
            self._validate_file_type(original_filename, file_content)
            old_filename = photo.path
            await self._delete_file(old_filename)
            filename = self._generate_filename(original_filename)
            await self._save_file(file_content, filename)
            photo.path = filename

        update_data = {}

        if data.name is not None:
            name_value = data.name
            if not name_value or name_value.strip() == "":
                if original_filename:
                    name_value = self._get_name_from_filename(original_filename)
                else:
                    name_value = self._get_name_from_filename(photo.path)

            name_value = await self._generate_unique_name(
                name_value, exclude_id=photo.id
            )
            update_data["name"] = name_value

        if data.description is not None:
            update_data["description"] = ""

        for key, value in update_data.items():
            setattr(photo, key, value)

        return await self.photo_repository.update(photo)

    async def get_by_id(self, id: UUID) -> Photo | None:
        return await self.photo_repository.get_by_id(id)

    async def delete(self, id: UUID) -> None:
        photo = await self.photo_repository.get_by_id(id)
        if photo is None:
            raise ClientError("Фотография не найдена")

        filename = photo.path
        await self._delete_file(filename)

        await self.photo_repository.delete(id)

    async def get_filtered(
        self,
        *,
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
            name=name,
            description=description,
            price_ids=price_ids,
            horse_ids=horse_ids,
            sort=sort,
            limit=limit,
            offset=offset,
        )

    async def batch_delete(self, ids: list[UUID]) -> None:
        if not ids:
            return

        photos_to_delete = []
        for photo_id in ids:
            photo = await self.photo_repository.get_by_id(photo_id)
            if photo:
                photos_to_delete.append(photo)

        for photo in photos_to_delete:
            await self._delete_file(photo.path)

        await self.photo_repository.batch_delete(ids)
