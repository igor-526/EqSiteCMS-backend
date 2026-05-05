from typing import Annotated

from fastapi import Cookie, Depends

from core.protocols.repositories import (
    BreedRepositoryProtocol,
    CoatColorRepositoryProtocol,
    HorseOwnerRepositoryProtocol,
    HorseRepositoryProtocol,
    HorseServiceRepositoryProtocol,
    PhotoRepositoryProtocol,
    PriceGroupRepositoryProtocol,
    PriceRepositoryProtocol,
    SiteSettingsRepositoryProtocol,
    UserRepositoryProtocol,
)
from core.protocols.repositories.horse_repository import HorseChildrenRepositoryProtocol
from core.protocols.security import SecurityProtocol
from core.schemas.users import UserOutDto
from core.services.auth import AuthService
from core.services.breeds import BreedService
from core.services.coat_color import CoatColorService
from core.services.horse import HorseService
from core.services.horse_owner import HorseOwnerService
from core.services.horse_service import HorseServiceService
from core.services.photos import PhotoService
from core.services.prices import PriceGroupService, PriceService
from core.services.site_settings import SiteSettingsService
from depends.repositories import (
    get_breed_repository,
    get_coat_color_repository,
    get_horse_children_repository,
    get_horse_owner_repository,
    get_horse_repository,
    get_horse_service_repository,
    get_photo_repository,
    get_price_group_repository,
    get_price_repository,
    get_site_settings_repository,
    get_user_repository,
)
from depends.utils import get_security


async def get_auth_service(
    user_repository: Annotated[UserRepositoryProtocol, Depends(get_user_repository)],
    security: Annotated[SecurityProtocol, Depends(get_security)],
) -> AuthService:
    return AuthService(user_repository=user_repository, security=security)


async def get_current_user(
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    access_token: Annotated[str | None, Cookie(alias="access_token")] = None,
) -> UserOutDto | None:
    if access_token is None:
        return None

    return await auth_service.get_current_user(token=access_token)


async def get_breed_service(
    breed_repository: Annotated[BreedRepositoryProtocol, Depends(get_breed_repository)],
) -> BreedService:
    return BreedService(breed_repository=breed_repository)


async def get_coat_color_service(
    coat_color_repository: Annotated[
        CoatColorRepositoryProtocol, Depends(get_coat_color_repository)
    ],
) -> CoatColorService:
    return CoatColorService(coat_color_repository=coat_color_repository)


async def get_horse_owner_service(
    horse_owner_repository: Annotated[
        HorseOwnerRepositoryProtocol, Depends(get_horse_owner_repository)
    ],
) -> HorseOwnerService:
    return HorseOwnerService(horse_owner_repository=horse_owner_repository)


async def get_horse_service_service(
    horse_service_repository: Annotated[
        HorseServiceRepositoryProtocol, Depends(get_horse_service_repository)
    ],
) -> HorseServiceService:
    return HorseServiceService(horse_service_repository=horse_service_repository)


async def get_photo_service(
    photo_repository: Annotated[PhotoRepositoryProtocol, Depends(get_photo_repository)],
) -> PhotoService:
    return PhotoService(photo_repository=photo_repository)


async def get_site_settings_service(
    site_settings_repository: Annotated[
        SiteSettingsRepositoryProtocol, Depends(get_site_settings_repository)
    ],
) -> SiteSettingsService:
    return SiteSettingsService(site_settings_repository=site_settings_repository)


async def get_price_group_service(
    price_group_repository: Annotated[
        PriceGroupRepositoryProtocol, Depends(get_price_group_repository)
    ],
) -> PriceGroupService:
    return PriceGroupService(price_group_repository=price_group_repository)


async def get_price_service(
    price_repository: Annotated[PriceRepositoryProtocol, Depends(get_price_repository)],
    price_group_repository: Annotated[
        PriceGroupRepositoryProtocol, Depends(get_price_group_repository)
    ],
    photo_repository: Annotated[PhotoRepositoryProtocol, Depends(get_photo_repository)],
) -> PriceService:
    return PriceService(
        price_repository=price_repository,
        price_group_repository=price_group_repository,
        photo_repository=photo_repository,
    )


async def get_horse_service(
    horse_repository: Annotated[HorseRepositoryProtocol, Depends(get_horse_repository)],
    horse_children_repository: Annotated[
        HorseChildrenRepositoryProtocol, Depends(get_horse_children_repository)
    ],
    breed_repository: Annotated[BreedRepositoryProtocol, Depends(get_breed_repository)],
    coat_color_repository: Annotated[
        CoatColorRepositoryProtocol, Depends(get_coat_color_repository)
    ],
    horse_owner_repository: Annotated[
        HorseOwnerRepositoryProtocol, Depends(get_horse_owner_repository)
    ],
) -> HorseService:
    return HorseService(
        horse_repository=horse_repository,
        horse_children_repository=horse_children_repository,
        breed_repository=breed_repository,
        coat_color_repository=coat_color_repository,
        horse_owner_repository=horse_owner_repository,
    )
