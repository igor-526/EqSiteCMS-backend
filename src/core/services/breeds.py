from typing import Literal
from uuid import UUID

from pydantic import ValidationError

from core.entities.base import _generate_slug
from core.entities.breeds import Breed
from core.entities.equestrian import EquestrianContext
from core.entities.horse import HorseKindEnum
from core.exceptions.auth import ForbiddenError
from core.exceptions.base import ClientError
from core.protocols.repositories.breed_repository import BreedRepositoryProtocol
from core.schemas.breeds import BreedCreateDto, BreedUpdateDto
from core.schemas.users import UserOutDto
from core.utils.html_security import validate_no_js_in_html

BREED_NAME_MAX_LENGTH = 63
BREED_SHORT_NAME_MAX_LENGTH = 63
BREED_SLUG_MAX_LENGTH = 63
BREED_DESCRIPTION_MAX_LENGTH = 511
DEFAULT_PAGE_DATA = "<div></div>"
ADMIN_SCOPE_NAMES: frozenset[str] = frozenset({"SUPERUSER", "ADMIN", "DEVELOPER"})


def _derive_short_name(name: str) -> str:
    """Генерировать short_name из name, обрезая до максимально допустимой длины."""
    return name[:BREED_SHORT_NAME_MAX_LENGTH]


class BreedService:
    def __init__(self, breed_repository: BreedRepositoryProtocol):
        self.breed_repository = breed_repository

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

    def _validate_breed_data(
        self, data: dict[str, str | None], *, partial: bool
    ) -> None:
        if not partial or "name" in data:
            data["name"] = self._validate_required_text(
                field="Название породы",
                value=data.get("name"),
                max_length=BREED_NAME_MAX_LENGTH,
            )

        if "short_name" in data:
            raw = data["short_name"]
            if raw is None or (isinstance(raw, str) and not raw.strip()):
                # Пустое/None short_name — удаляем, чтобы автоматически
                # сгенерировать из name после валидации.
                del data["short_name"]
            else:
                data["short_name"] = self._validate_optional_text(
                    field="Короткое название породы",
                    value=raw,
                    max_length=BREED_SHORT_NAME_MAX_LENGTH,
                )
        if "slug" in data:
            data["slug"] = self._validate_required_text(
                field="Slug",
                value=data["slug"],
                max_length=BREED_SLUG_MAX_LENGTH,
            )
        if "description" in data:
            data["description"] = self._validate_optional_text(
                field="Описание породы",
                value=data["description"],
                max_length=BREED_DESCRIPTION_MAX_LENGTH,
            )
        if "page_data" in data:
            data["page_data"] = self._validate_optional_text(
                field="Данные страницы породы",
                value=data["page_data"],
            )
            if data["page_data"] is not None:
                validate_no_js_in_html("Данные страницы породы", data["page_data"])

    def _check_admin_permission(self, *, user: UserOutDto | None) -> None:
        if user is None:
            return
        if not any(scope.scope_name in ADMIN_SCOPE_NAMES for scope in user.scopes):
            raise ForbiddenError("Недостаточно прав для выполнения операции")

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
            existing = await self.breed_repository.find_by_slug(
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
        data: BreedCreateDto,
        *,
        equestrian_context: EquestrianContext,
        user: UserOutDto | None = None,
    ) -> Breed:
        """Создать новую породу."""

        self._check_admin_permission(user=user)
        breed_data = data.model_dump(exclude_none=True)
        self._validate_breed_data(breed_data, partial=False)

        existing = await self.breed_repository.find_by_name(
            breed_data["name"], equestrian_id=equestrian_context.id
        )
        if existing is not None:
            raise ClientError(
                f"Порода с названием '{breed_data['name']}' уже существует"
            )

        if "slug" not in breed_data:
            breed_data["slug"] = _generate_slug(breed_data["name"])

        breed_data["slug"] = await self._ensure_unique_slug(
            breed_data["slug"], equestrian_context=equestrian_context
        )

        if "short_name" not in breed_data:
            breed_data["short_name"] = _derive_short_name(breed_data["name"])

        if "page_data" not in breed_data:
            breed_data["page_data"] = DEFAULT_PAGE_DATA

        try:
            breed = Breed(**breed_data, equestrian_id=equestrian_context.id)
        except ValidationError as ex:
            raise ClientError(str(ex)) from ex
        return await self.breed_repository.create(breed)

    async def update(
        self,
        slug_or_id: str,
        data: BreedUpdateDto,
        *,
        equestrian_context: EquestrianContext,
        user: UserOutDto | None = None,
    ) -> Breed:
        """Обновить породу."""

        self._check_admin_permission(user=user)
        parsed = self._parse_slug_or_id(slug_or_id)
        breed = await self.breed_repository.get_by_slug_or_id(
            parsed, equestrian_id=equestrian_context.id
        )
        if breed is None:
            raise ClientError("Порода не найдена")

        update_data = data.model_dump(exclude_none=True)
        if not update_data:
            raise ClientError("Нет данных для обновления")
        had_short_name = "short_name" in update_data
        self._validate_breed_data(update_data, partial=True)
        short_name_cleared = had_short_name and "short_name" not in update_data

        if "name" in update_data:
            existing = await self.breed_repository.find_by_name(
                update_data["name"], equestrian_id=equestrian_context.id
            )
            if existing is not None and existing.id != breed.id:
                raise ClientError(
                    f"Порода с названием '{update_data['name']}' уже существует"
                )

        if "slug" in update_data:
            update_data["slug"] = await self._ensure_unique_slug(
                update_data["slug"],
                equestrian_context=equestrian_context,
                exclude_id=breed.id,
            )

        if "name" in update_data and "slug" not in update_data:
            new_slug = _generate_slug(update_data["name"])
            update_data["slug"] = await self._ensure_unique_slug(
                new_slug, equestrian_context=equestrian_context, exclude_id=breed.id
            )

        if short_name_cleared:
            source_name = update_data.get("name", breed.name)
            update_data["short_name"] = _derive_short_name(source_name)

        for key, value in update_data.items():
            setattr(breed, key, value)

        return await self.breed_repository.update(breed)

    async def get_by_slug_or_id(
        self, slug_or_id: str, *, equestrian_context: EquestrianContext
    ) -> Breed:
        """Получить породу по slug или UUID."""

        parsed = self._parse_slug_or_id(slug_or_id)
        breed = await self.breed_repository.get_by_slug_or_id(
            parsed, equestrian_id=equestrian_context.id
        )
        if breed is None:
            raise ClientError("Порода не найдена")
        return breed

    async def delete(
        self,
        slug_or_id: str,
        *,
        equestrian_context: EquestrianContext,
        user: UserOutDto | None = None,
    ) -> None:
        """Удалить породу."""

        self._check_admin_permission(user=user)
        parsed = self._parse_slug_or_id(slug_or_id)
        breed = await self.breed_repository.get_by_slug_or_id(
            parsed, equestrian_id=equestrian_context.id
        )
        if breed is None:
            raise ClientError("Порода не найдена")
        await self.breed_repository.delete(
            breed.id, equestrian_id=equestrian_context.id
        )

    async def get_filtered(
        self,
        *,
        equestrian_context: EquestrianContext,
        name: str | None = None,
        short_name: str | None = None,
        slug: str | None = None,
        description: str | None = None,
        page_data: str | None = None,
        kind: list[HorseKindEnum] | None = None,
        sort: (
            list[
                Literal[
                    "name",
                    "short_name",
                    "description",
                    "slug",
                    "kind",
                    "-name",
                    "-short_name",
                    "-description",
                    "-slug",
                    "-kind",
                ]
            ]
            | None
        ) = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[list[Breed], int]:
        """Получить отфильтрованный список пород."""
        return await self.breed_repository.get_filtered(
            equestrian_id=equestrian_context.id,
            name=name,
            short_name=short_name,
            slug=slug,
            description=description,
            page_data=page_data,
            kind=kind,
            sort=sort,
            limit=limit,
            offset=offset,
        )
