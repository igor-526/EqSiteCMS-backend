from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

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
    LocalMediaStorage,
    SettingsPhotoUrlBuilder,
    resolve_media_base_dir,
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
    base_dir = resolve_media_base_dir()
    return LocalMediaStorage(base_dir=base_dir)


async def get_photo_url_builder() -> PhotoUrlBuilderProtocol:
    return SettingsPhotoUrlBuilder(
        cms_backend_domain=settings.cms_backend_domain,
        debug=settings.debug,
    )


async def get_media_type_validator() -> MediaTypeValidatorProtocol:
    return AllowedMediaTypeValidator()
