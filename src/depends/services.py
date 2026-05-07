from typing import Annotated

from fastapi import Cookie, Depends, Header

from core.entities.equestrian import EquestrianContext
from core.exceptions.auth import InvalidCredentials
from core.exceptions.base import ClientError
from core.exceptions.tenant import TenantNotFound
from core.protocols.media import (
    MediaStorageProtocol,
    MediaTypeValidatorProtocol,
    PhotoUrlBuilderProtocol,
)
from core.protocols.repositories import (
    BreedRepositoryProtocol,
    CoatColorRepositoryProtocol,
    EquestrianRepositoryProtocol,
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
from core.services.users import UserService
from depends.repositories import (
    get_breed_repository,
    get_coat_color_repository,
    get_equestrian_repository,
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
from depends.utils import (
    get_media_storage,
    get_media_type_validator,
    get_photo_url_builder,
    get_security,
)


async def get_auth_service(
    user_repository: Annotated[UserRepositoryProtocol, Depends(get_user_repository)],
    security: Annotated[SecurityProtocol, Depends(get_security)],
) -> AuthService:
    return AuthService(user_repository=user_repository, security=security)


async def get_user_service(
    user_repository: Annotated[UserRepositoryProtocol, Depends(get_user_repository)],
) -> UserService:
    return UserService(repository=user_repository)


async def get_current_user(
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    access_token: Annotated[str | None, Cookie(alias="access_token")] = None,
) -> UserOutDto:
    if access_token is None:
        raise InvalidCredentials("Отсутствуют учетные данные")

    return await auth_service.get_current_user(token=access_token)


async def get_optional_current_user(
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
    access_token: Annotated[str | None, Cookie(alias="access_token")] = None,
) -> UserOutDto | None:
    if access_token is None:
        return None
    return await auth_service.get_current_user(token=access_token)


async def get_public_equestrian_context(
    equestrian_repository: Annotated[
        EquestrianRepositoryProtocol, Depends(get_equestrian_repository)
    ],
    service_key: Annotated[str | None, Header(alias="X-Equestrian-Service-Key")] = None,
) -> EquestrianContext:
    if service_key is None or not service_key.strip():
        raise ClientError("Отсутствует X-Equestrian-Service-Key")

    equestrian = await equestrian_repository.get_by_service_key(service_key.strip())
    if equestrian is None:
        raise TenantNotFound("Конюшня не найдена")
    return EquestrianContext(id=equestrian.id, source="public")


async def get_protected_equestrian_context(
    current_user: Annotated[UserOutDto, Depends(get_current_user)],
) -> EquestrianContext:
    return EquestrianContext(id=current_user.equestrian_id, source="authenticated")


async def get_read_equestrian_context(
    current_user: Annotated[UserOutDto | None, Depends(get_optional_current_user)],
    equestrian_repository: Annotated[
        EquestrianRepositoryProtocol, Depends(get_equestrian_repository)
    ],
    service_key: Annotated[str | None, Header(alias="X-Equestrian-Service-Key")] = None,
) -> EquestrianContext:
    if current_user is not None:
        return EquestrianContext(id=current_user.equestrian_id, source="authenticated")
    if service_key is None or not service_key.strip():
        raise ClientError("Отсутствует X-Equestrian-Service-Key")
    equestrian = await equestrian_repository.get_by_service_key(service_key.strip())
    if equestrian is None:
        raise TenantNotFound("Конюшня не найдена")
    return EquestrianContext(id=equestrian.id, source="public")


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
    media_storage: Annotated[MediaStorageProtocol, Depends(get_media_storage)],
    photo_url_builder: Annotated[
        PhotoUrlBuilderProtocol, Depends(get_photo_url_builder)
    ],
    media_type_validator: Annotated[
        MediaTypeValidatorProtocol, Depends(get_media_type_validator)
    ],
) -> PhotoService:
    # Service stays framework-agnostic; adapters are wired via DI.
    return PhotoService(
        photo_repository=photo_repository,
        media_storage=media_storage,
        photo_url_builder=photo_url_builder,
        media_type_validator=media_type_validator,
    )


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
    price_repository: Annotated[PriceRepositoryProtocol, Depends(get_price_repository)],
) -> PriceGroupService:
    return PriceGroupService(
        price_group_repository=price_group_repository,
        price_repository=price_repository,
    )


async def get_price_service(
    price_repository: Annotated[PriceRepositoryProtocol, Depends(get_price_repository)],
    price_group_repository: Annotated[
        PriceGroupRepositoryProtocol, Depends(get_price_group_repository)
    ],
    photo_repository: Annotated[PhotoRepositoryProtocol, Depends(get_photo_repository)],
    photo_url_builder: Annotated[
        PhotoUrlBuilderProtocol, Depends(get_photo_url_builder)
    ],
) -> PriceService:
    return PriceService(
        price_repository=price_repository,
        price_group_repository=price_group_repository,
        photo_repository=photo_repository,
        photo_url_builder=photo_url_builder,
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
