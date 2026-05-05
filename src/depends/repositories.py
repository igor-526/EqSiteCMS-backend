from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.protocols.repositories import (
    BreedRepositoryProtocol,
    CoatColorRepositoryProtocol,
    HorseChildrenRepositoryProtocol,
    HorseOwnerRepositoryProtocol,
    HorseRepositoryProtocol,
    HorseServiceRepositoryProtocol,
    PhotoRepositoryProtocol,
    PriceGroupRepositoryProtocol,
    PriceRepositoryProtocol,
    SiteSettingsRepositoryProtocol,
    UserRepositoryProtocol,
)
from depends.utils import get_session
from repositories import (
    BreedRepository,
    CoatColorRepository,
    HorseChildrenRepository,
    HorseOwnerRepository,
    HorseRepository,
    HorseServiceRepository,
    PhotoRepository,
    PriceGroupRepository,
    PriceRepository,
    SiteSettingsRepository,
    UserRepository,
)


async def get_user_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> UserRepositoryProtocol:
    return UserRepository(session=session)


async def get_breed_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> BreedRepositoryProtocol:
    return BreedRepository(session=session)


async def get_coat_color_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CoatColorRepositoryProtocol:
    return CoatColorRepository(session=session)


async def get_horse_owner_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> HorseOwnerRepositoryProtocol:
    return HorseOwnerRepository(session=session)


async def get_horse_service_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> HorseServiceRepositoryProtocol:
    return HorseServiceRepository(session=session)


async def get_photo_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PhotoRepositoryProtocol:
    return PhotoRepository(session=session)


async def get_site_settings_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> SiteSettingsRepositoryProtocol:
    return SiteSettingsRepository(session=session)


async def get_price_group_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PriceGroupRepositoryProtocol:
    return PriceGroupRepository(session=session)


async def get_price_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PriceRepositoryProtocol:
    return PriceRepository(session=session)


async def get_horse_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> HorseRepositoryProtocol:
    return HorseRepository(session=session)


async def get_horse_children_repository(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> HorseChildrenRepositoryProtocol:
    return HorseChildrenRepository(session=session)
