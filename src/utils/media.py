from __future__ import annotations

import asyncio
from os import getenv
from pathlib import Path

from core.exceptions.base import ClientError


class LocalMediaStorage:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, filename: str) -> Path:
        return self.base_dir / filename

    async def save(self, file_content: bytes, filename: str) -> str:
        file_path = self._path(filename)
        await asyncio.to_thread(file_path.write_bytes, file_content)
        return filename

    async def load(self, filename: str) -> bytes:
        file_path = self._path(filename)
        if not file_path.exists():
            raise FileNotFoundError(filename)
        return await asyncio.to_thread(file_path.read_bytes)

    async def delete(self, filename: str) -> None:
        file_path = self._path(filename)
        if file_path.exists():
            await asyncio.to_thread(file_path.unlink)


class SettingsPhotoUrlBuilder:
    def __init__(self, cms_backend_domain: str, debug: bool) -> None:
        self.cms_backend_domain = cms_backend_domain
        self.debug = debug

    def build(self, filename: str) -> str:
        protocol = "https" if not self.debug else "http"
        return f"{protocol}://{self.cms_backend_domain}/media/{filename}"


class AllowedMediaTypeValidator:
    IMAGE_EXTENSIONS = {
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
    VIDEO_EXTENSIONS = {
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

    def validate(
        self, filename: str, content: bytes, content_type: str | None = None
    ) -> None:
        extension = Path(filename).suffix.lower()
        allowed_extensions = self.IMAGE_EXTENSIONS | self.VIDEO_EXTENSIONS
        if extension not in allowed_extensions:
            raise ClientError(
                f"Недопустимый тип файла: {extension}. "
                f"Разрешены только изображения и видео файлы"
            )


def resolve_media_base_dir() -> Path:
    configured_path = getenv("MEDIA_STORAGE_PATH")
    if configured_path:
        return Path(configured_path).expanduser().resolve()
    return Path(__file__).resolve().parents[2] / "storage" / "media"
