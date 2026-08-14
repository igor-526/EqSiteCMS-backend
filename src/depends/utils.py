from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from clients.nats.client import NatsJetstreamClient
from containers import container
from core.protocols.media import (
    MediaStorageProtocol,
    MediaTypeValidatorProtocol,
    PhotoUrlBuilderProtocol,
)
from core.protocols.security import SecurityProtocol
from settings import settings
from utils.database import AsyncSessionLocal
from utils.media import (
    AllowedMediaTypeValidator,
    S3MediaStorage,
    S3PhotoUrlBuilder,
)
from utils.security import Security


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    session: AsyncSession = AsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def get_security() -> SecurityProtocol:
    return Security()


async def get_media_storage() -> MediaStorageProtocol:
    return S3MediaStorage(
        endpoint_url=settings.s3_endpoint_url,
        access_key=settings.s3_access_key,
        secret_key=settings.s3_secret_key,
        bucket_name=settings.s3_bucket_name,
    )


async def get_photo_url_builder() -> PhotoUrlBuilderProtocol:
    return S3PhotoUrlBuilder(
        public_endpoint_url=settings.s3_public_endpoint_url,
        bucket_name=settings.s3_bucket_name,
        include_bucket_in_path=settings.s3_public_include_bucket,
    )


async def get_media_type_validator() -> MediaTypeValidatorProtocol:
    return AllowedMediaTypeValidator()


async def get_nats_client() -> NatsJetstreamClient:
    return container.nats_client()
