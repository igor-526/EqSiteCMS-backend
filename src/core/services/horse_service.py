from typing import Literal
from uuid import UUID

from pydantic import ValidationError

from core.entities.base import _generate_slug
from core.entities.equestrian import EquestrianContext
from core.entities.horse_service import HorseServiceEntity
from core.exceptions.base import ClientError
from core.protocols.repositories.horse_service_repository import (
    HorseServiceRepositoryProtocol,
)
from core.schemas.horse_service import HorseServiceCreateDto, HorseServiceUpdateDto
from core.schemas.users import UserOutDto
from core.utils.html_security import validate_no_js_in_html

HORSE_SERVICE_NAME_MAX_LENGTH = 63
HORSE_SERVICE_SLUG_MAX_LENGTH = 63
HORSE_SERVICE_DESCRIPTION_MAX_LENGTH = 511
DEFAULT_PAGE_DATA = "<div></div>"
ALLOWED_SORT_FIELDS = {
    "name",
    "description",
    "slug",
    "price",
    "-name",
    "-description",
    "-slug",
    "-price",
}


class HorseServiceService:
    _ADMIN_SCOPE_NAMES: frozenset[str] = frozenset({"SUPERUSER", "DEVELOPER"})

    def __init__(self, horse_service_repository: HorseServiceRepositoryProtocol):
        self.horse_service_repository = horse_service_repository

    async def _check_admin_permission(
        self,
        *,
        user: UserOutDto,
        check_name_update: bool = False,
        is_create_or_delete: bool = False,
    ) -> None:
        """Проверить, что пользователь имеет права SUPERUSER или DEVELOPER."""
        if user is None:
            raise ClientError("Недостаточно прав для выполнения операции")
        has_admin_scope = any(
            scope.scope_name in self._ADMIN_SCOPE_NAMES for scope in user.scopes
        )
        # Если пользователь имеет SUPERUSER или DEVELOPER scope, разрешаем все операции
        if has_admin_scope:
            return
        # Если пользователь ADMIN
        has_admin_only = any(
            scope.scope_name == "ADMIN" for scope in user.scopes
        )
        if has_admin_only:
            # Для создания и удаления запрещаем
            if is_create_or_delete:
                raise ClientError("Недостаточно прав для выполнения операции")
            # Если пытается обновить наименование, запрещаем
            if check_name_update:
                raise ClientError("Недостаточно прав для изменения наименования")
            # Для обновления других полей разрешаем
            return
        # Для всех остальных операций запрещаем
        raise ClientError("Недостаточно прав для выполнения операции")

    def _parse_slug_or_id(self, slug_or_id: str) -> str | UUID:
        """Попытаться преобразовать строку в UUID, иначе вернуть как есть."""
        try:
            return UUID(slug_or_id)
        except ValueError:
            return slug_or_id

    def _validate_required_text(
        self, *, field: str, value: str | None, max_length: int
    ) -> str:
        if value is None:
            raise ClientError(f"{field} обязательно")

        normalized = value.strip()
        if not normalized:
            raise ClientError(f"{field} не может быть пустым")
        if len(normalized) > max_length:
            raise ClientError(f"{field} не может быть длиннее {max_length} символов")
        return normalized

    def _validate_optional_text(
        self, *, field: str, value: str | None, max_length: int | None = None
    ) -> str | None:
        if value is None:
            return None

        normalized = value.strip()
        if not normalized:
            raise ClientError(f"{field} не может быть пустым")
        if max_length is not None and len(normalized) > max_length:
            raise ClientError(f"{field} не может быть длиннее {max_length} символов")
        return normalized

    def _validate_non_negative_int(
        self, *, field: str, value: int | None
    ) -> int | None:
        if value is None:
            return None
        if value < 0:
            raise ClientError(f"{field} не может быть меньше 0")
        return value

    def _validate_service_data(self, data: dict[str, object], *, partial: bool) -> None:
        name_value = data.get("name")
        slug_value = data.get("slug")
        description_value = data.get("description")
        page_data_value = data.get("page_data")
        price_value = data.get("price")

        if not partial or "name" in data:
            data["name"] = self._validate_required_text(
                field="Название услуги",
                value=name_value if isinstance(name_value, str) else None,
                max_length=HORSE_SERVICE_NAME_MAX_LENGTH,
            )

        if "slug" in data:
            slug_raw = slug_value if isinstance(slug_value, str) else None
            if slug_raw is not None and not slug_raw.strip():
                del data["slug"]
            else:
                data["slug"] = self._validate_required_text(
                    field="Slug",
                    value=slug_raw,
                    max_length=HORSE_SERVICE_SLUG_MAX_LENGTH,
                )

        if "description" in data:
            desc_raw = description_value if isinstance(description_value, str) else None
            if desc_raw is not None and not desc_raw.strip():
                data["description"] = None
            else:
                data["description"] = self._validate_optional_text(
                    field="Описание услуги",
                    value=desc_raw,
                    max_length=HORSE_SERVICE_DESCRIPTION_MAX_LENGTH,
                )

        if "page_data" in data:
            data["page_data"] = self._validate_optional_text(
                field="Данные страницы услуги",
                value=page_data_value if isinstance(page_data_value, str) else None,
            )
            validated_page_data = data["page_data"]
            if isinstance(validated_page_data, str):
                validate_no_js_in_html("Данные страницы услуги", validated_page_data)

        if "price" in data:
            data["price"] = self._validate_non_negative_int(
                field="Цена услуги",
                value=price_value if isinstance(price_value, int) else None,
            )

    def _validate_pagination(self, *, limit: int | None, offset: int | None) -> None:
        if limit is not None and limit < 0:
            raise ClientError("Лимит не может быть меньше 0")
        if offset is not None and offset < 0:
            raise ClientError("Смещение не может быть меньше 0")

    def _validate_sort(
        self,
        sort: (
            list[
                Literal[
                    "name",
                    "description",
                    "slug",
                    "price",
                    "-name",
                    "-description",
                    "-slug",
                    "-price",
                ]
            ]
            | None
        ),
    ) -> (
        list[
            Literal[
                "name",
                "description",
                "slug",
                "price",
                "-name",
                "-description",
                "-slug",
                "-price",
            ]
        ]
        | None
    ):
        if sort is None:
            return None
        for item in sort:
            if item not in ALLOWED_SORT_FIELDS:
                raise ClientError(f"Недопустимое поле сортировки: {item}")
        return list(sort)

    async def _ensure_unique_slug(
        self,
        slug: str,
        *,
        equestrian_context: EquestrianContext,
        exclude_id: UUID | None = None,
    ) -> str:
        """Обеспечивает уникальность slug, добавляя суффиксы -1, -2 и т.д."""
        base_slug = slug
        counter = 1
        current_slug = base_slug

        while True:
            existing = await self.horse_service_repository.find_by_slug(
                current_slug, equestrian_id=equestrian_context.id
            )
            if existing is None or (
                exclude_id is not None and existing.id == exclude_id
            ):
                return current_slug
            current_slug = f"{base_slug}-{counter}"
            counter += 1

    async def create(
        self,
        data: HorseServiceCreateDto,
        *,
        equestrian_context: EquestrianContext,
        user: UserOutDto | None = None,
    ) -> HorseServiceEntity:
        """Создать новую услугу."""
        if user is not None:
            await self._check_admin_permission(user=user, is_create_or_delete=True)
        horse_service_data = data.model_dump(exclude_none=True)
        self._validate_service_data(horse_service_data, partial=False)

        # Проверяем уникальность name
        existing = await self.horse_service_repository.find_by_name(
            horse_service_data["name"], equestrian_id=equestrian_context.id
        )
        if existing is not None:
            raise ClientError(
                f"Услуга с названием '{horse_service_data['name']}' уже существует"
            )

        # Если slug не задан, генерируем из name
        if "slug" not in horse_service_data:
            horse_service_data["slug"] = _generate_slug(horse_service_data["name"])

        # Обеспечиваем уникальность slug
        horse_service_data["slug"] = await self._ensure_unique_slug(
            horse_service_data["slug"], equestrian_context=equestrian_context
        )

        # Устанавливаем page_data по умолчанию, если не задан
        if "page_data" not in horse_service_data:
            horse_service_data["page_data"] = DEFAULT_PAGE_DATA

        try:
            horse_service = HorseServiceEntity(
                **horse_service_data, equestrian_id=equestrian_context.id
            )
        except ValidationError as ex:
            raise ClientError(str(ex)) from ex
        return await self.horse_service_repository.create(horse_service)

    async def update(
        self,
        slug_or_id: str,
        data: HorseServiceUpdateDto,
        *,
        equestrian_context: EquestrianContext,
        user: UserOutDto | None = None,
    ) -> HorseServiceEntity:
        """Обновить услугу."""
        parsed = self._parse_slug_or_id(slug_or_id)
        horse_service = await self.horse_service_repository.get_by_slug_or_id(
            parsed, equestrian_id=equestrian_context.id
        )
        if horse_service is None:
            raise ClientError("Услуга не найдена")

        if user is not None:
            # Проверяем, пытается ли пользователь изменить наименование
            update_data = data.model_dump(exclude_none=True)
            is_name_update = "name" in update_data and update_data["name"] != horse_service.name
            await self._check_admin_permission(user=user, check_name_update=is_name_update)

        update_data = data.model_dump(exclude_none=True)
        if not update_data:
            raise ClientError("Нет данных для обновления")
        self._validate_service_data(update_data, partial=True)

        # Если обновляется name, проверяем уникальность
        if "name" in update_data:
            existing = await self.horse_service_repository.find_by_name(
                update_data["name"], equestrian_id=equestrian_context.id
            )
            if existing is not None and existing.id != horse_service.id:
                raise ClientError(
                    f"Услуга с названием '{update_data['name']}' уже существует"
                )

        # Если обновляется slug, проверяем уникальность
        if "slug" in update_data:
            update_data["slug"] = await self._ensure_unique_slug(
                update_data["slug"],
                equestrian_context=equestrian_context,
                exclude_id=horse_service.id,
            )

        # Если slug был очищен (передана пустая строка), регенерируем из name
        if (
            data.slug is not None
            and not data.slug.strip()
            and "slug" not in update_data
        ):
            name_for_slug = update_data.get("name", horse_service.name)
            new_slug = _generate_slug(name_for_slug)
            update_data["slug"] = await self._ensure_unique_slug(
                new_slug,
                equestrian_context=equestrian_context,
                exclude_id=horse_service.id,
            )

        # Если обновляется name и slug не задан, генерируем slug из name
        if "name" in update_data and "slug" not in update_data:
            new_slug = _generate_slug(update_data["name"])
            update_data["slug"] = await self._ensure_unique_slug(
                new_slug,
                equestrian_context=equestrian_context,
                exclude_id=horse_service.id,
            )

        for key, value in update_data.items():
            setattr(horse_service, key, value)

        return await self.horse_service_repository.update(horse_service)

    async def get_by_slug_or_id(
        self, slug_or_id: str, *, equestrian_context: EquestrianContext
    ) -> HorseServiceEntity:
        """Получить услугу по slug или UUID."""
        parsed = self._parse_slug_or_id(slug_or_id)
        horse_service = await self.horse_service_repository.get_by_slug_or_id(
            parsed, equestrian_id=equestrian_context.id
        )
        if horse_service is None:
            raise ClientError("Услуга не найдена")
        return horse_service

    async def delete(
        self,
        slug_or_id: str,
        *,
        equestrian_context: EquestrianContext,
        user: UserOutDto | None = None,
    ) -> None:
        """Удалить услугу."""
        if user is not None:
            await self._check_admin_permission(user=user, is_create_or_delete=True)
        parsed = self._parse_slug_or_id(slug_or_id)
        horse_service = await self.horse_service_repository.get_by_slug_or_id(
            parsed, equestrian_id=equestrian_context.id
        )
        if horse_service is None:
            raise ClientError("Услуга не найдена")
        await self.horse_service_repository.delete(
            horse_service.id, equestrian_id=equestrian_context.id
        )

    async def get_filtered(
        self,
        *,
        equestrian_context: EquestrianContext,
        name: str | None = None,
        slug: str | None = None,
        description: str | None = None,
        page_data: str | None = None,
        sort: (
            list[
                Literal[
                    "name",
                    "description",
                    "slug",
                    "price",
                    "-name",
                    "-description",
                    "-slug",
                    "-price",
                ]
            ]
            | None
        ) = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[list[HorseServiceEntity], int]:
        """Получить отфильтрованный список услуг."""
        self._validate_pagination(limit=limit, offset=offset)
        validated_sort = self._validate_sort(sort)
        return await self.horse_service_repository.get_filtered(
            equestrian_id=equestrian_context.id,
            name=name,
            slug=slug,
            description=description,
            page_data=page_data,
            sort=validated_sort,
            limit=limit,
            offset=offset,
        )
