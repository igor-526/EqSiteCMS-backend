from __future__ import annotations

from pathlib import Path

from core.exceptions.base import ClientError


class S3MediaStorage:
    def __init__(
        self,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
        bucket_name: str,
    ) -> None:
        self.endpoint_url = endpoint_url
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket_name = bucket_name

    async def save(self, file_content: bytes, filename: str) -> str:
        import aioboto3

        session = aioboto3.Session()
        async with session.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
        ) as s3:
            await s3.put_object(
                Bucket=self.bucket_name,
                Key=filename,
                Body=file_content,
            )
        return filename

    async def load(self, filename: str) -> bytes:
        import aioboto3

        session = aioboto3.Session()
        async with session.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
        ) as s3:
            response = await s3.get_object(Bucket=self.bucket_name, Key=filename)
            return await response["Body"].read()

    async def delete(self, filename: str) -> None:
        import aioboto3

        session = aioboto3.Session()
        async with session.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
        ) as s3:
            await s3.delete_object(Bucket=self.bucket_name, Key=filename)


class S3PhotoUrlBuilder:
    def __init__(self, public_endpoint_url: str, bucket_name: str) -> None:
        self.public_endpoint_url = public_endpoint_url.rstrip("/")
        self.bucket_name = bucket_name

    def build(self, filename: str) -> str:
        return f"{self.public_endpoint_url}/{self.bucket_name}/{filename}"


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
