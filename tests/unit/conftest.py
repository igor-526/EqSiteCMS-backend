from __future__ import annotations

import inspect
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from functools import wraps
from typing import Any
from uuid import UUID

import pytest

from core.entities.breeds import Breed
from core.entities.coat_color import CoatColor
from core.entities.equestrian import EquestrianContext
from core.entities.horse import Horse
from core.entities.horse_owner import HorseOwner
from core.entities.horse_service import HorseServiceEntity
from core.entities.news import News
from core.entities.photos import Photo
from core.entities.prices import Price, PriceGroup
from core.entities.site_settings import SiteSetting
from core.entities.user import User, UserScope
from core.schemas.users import UserOutDto
from core.services.breeds import BreedService
from core.services.coat_color import CoatColorService
from core.services.horse import HorseService
from core.services.horse_owner import HorseOwnerService
from core.services.horse_service import HorseServiceService
from core.services.horse_service_relations import HorseServiceRelationsService
from core.services.news import NewsService
from core.services.photos import PhotoService
from core.services.prices import PriceGroupService, PriceService
from core.services.site_settings import SiteSettingsService

TEST_EQUESTRIAN_ID = UUID("11111111-1111-4111-8111-111111111111")
TEST_EQUESTRIAN_CONTEXT = EquestrianContext(
    id=TEST_EQUESTRIAN_ID,
    source="unit-test",
)
TEST_ADMIN_USER = UserOutDto(
    id=UUID("99999999-9999-4999-8999-999999999999"),
    equestrian_id=TEST_EQUESTRIAN_ID,
    username="unit-admin",
    created_at=datetime.now(timezone.utc),
    scopes=[UserScope(scope_name="ADMIN", scope_description="Admin scope")],
)

_TENANT_ENTITY_CLASSES = (
    Breed,
    CoatColor,
    Horse,
    HorseOwner,
    HorseServiceEntity,
    News,
    Photo,
    Price,
    PriceGroup,
    SiteSetting,
    User,
    UserOutDto,
)

_TENANT_SERVICE_CLASSES = (
    BreedService,
    CoatColorService,
    HorseOwnerService,
    HorseService,
    HorseServiceService,
    HorseServiceRelationsService,
    NewsService,
    PhotoService,
    PriceGroupService,
    PriceService,
    SiteSettingsService,
)


def _patch_entity_default_tenant(entity_class: type[Any]) -> None:
    original_init = entity_class.__init__
    if getattr(original_init, "_unit_tenant_patched", False):
        return

    @wraps(original_init)
    def wrapped_init(self: Any, **data: Any) -> None:
        data.setdefault("equestrian_id", TEST_EQUESTRIAN_ID)
        original_init(self, **data)

    wrapped_init._unit_tenant_patched = True  # type: ignore[attr-defined]
    entity_class.__init__ = wrapped_init


def _patch_user_out_model_validate() -> None:
    original_model_validate = UserOutDto.model_validate
    if getattr(original_model_validate, "_unit_tenant_patched", False):
        return

    @wraps(original_model_validate)
    def wrapped_model_validate(obj: Any, *args: Any, **kwargs: Any) -> UserOutDto:
        if isinstance(obj, dict):
            obj = {**obj}
            obj.setdefault("equestrian_id", TEST_EQUESTRIAN_ID)
        return original_model_validate(obj, *args, **kwargs)

    wrapped_model_validate._unit_tenant_patched = True  # type: ignore[attr-defined]
    UserOutDto.model_validate = wrapped_model_validate  # type: ignore[method-assign]


def _patch_service_default_context(service_class: type[Any]) -> None:
    for name, method in inspect.getmembers(service_class, inspect.iscoroutinefunction):
        signature = inspect.signature(method)
        if "equestrian_context" not in signature.parameters:
            continue
        if getattr(method, "_unit_context_patched", False):
            continue

        async def wrapped(
            self: Any, *args: Any, __method: Callable[..., Any] = method, **kwargs: Any
        ) -> Any:
            if (
                __method.__qualname__ == "PhotoService.update"
                and len(args) == 3
                and "upload" not in kwargs
            ):
                upload = args[2]
                args = (args[0], args[1])
                kwargs["upload"] = upload
            kwargs.setdefault("equestrian_context", TEST_EQUESTRIAN_CONTEXT)
            if __method.__qualname__.startswith(
                "HorseServiceRelationsService."
            ) and __method.__name__ in {
                "create",
                "update",
                "delete",
                "get_available_services",
            }:
                kwargs.setdefault("user", TEST_ADMIN_USER)
            return await __method(self, *args, **kwargs)

        wrapped._unit_context_patched = True  # type: ignore[attr-defined]
        setattr(service_class, name, wrapped)


def _patch_fake_method(
    fake_class: type[Any], name: str, method: Callable[..., Any]
) -> None:
    if getattr(method, "_unit_fake_patched", False):
        return

    signature = inspect.signature(method)
    explicit_parameters = set(signature.parameters)
    accepts_kwargs = any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in signature.parameters.values()
    )
    allowed_kwargs = {
        parameter_name
        for parameter_name, parameter in signature.parameters.items()
        if parameter_name != "self"
        and parameter.kind
        in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
    }

    if inspect.iscoroutinefunction(method):

        @wraps(method)
        async def async_wrapped(self: Any, *args: Any, **kwargs: Any) -> Any:
            if "equestrian_id" not in explicit_parameters:
                kwargs.pop("equestrian_id", None)
            if not accepts_kwargs:
                kwargs = {
                    key: value for key, value in kwargs.items() if key in allowed_kwargs
                }
            return await method(self, *args, **kwargs)

        async_wrapped._unit_fake_patched = True  # type: ignore[attr-defined]
        setattr(fake_class, name, async_wrapped)
        return

    @wraps(method)
    def sync_wrapped(self: Any, *args: Any, **kwargs: Any) -> Any:
        if "equestrian_id" not in explicit_parameters:
            kwargs.pop("equestrian_id", None)
        if not accepts_kwargs:
            kwargs = {
                key: value for key, value in kwargs.items() if key in allowed_kwargs
            }
        return method(self, *args, **kwargs)

    sync_wrapped._unit_fake_patched = True  # type: ignore[attr-defined]
    setattr(fake_class, name, sync_wrapped)


def _patch_fake_repositories() -> None:
    for module_name, module in list(sys.modules.items()):
        module_file = getattr(module, "__file__", "") or ""
        if (
            not module_name.startswith("tests.unit.")
            and "/tests/unit/" not in module_file
        ):
            continue
        for _, fake_class in inspect.getmembers(module, inspect.isclass):
            if not fake_class.__name__.startswith("Fake"):
                continue
            for method_name, method in inspect.getmembers(
                fake_class, inspect.isfunction
            ):
                _patch_fake_method(fake_class, method_name, method)


for _entity_class in _TENANT_ENTITY_CLASSES:
    _patch_entity_default_tenant(_entity_class)

for _service_class in _TENANT_SERVICE_CLASSES:
    _patch_service_default_context(_service_class)

_patch_user_out_model_validate()


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    _patch_fake_repositories()
