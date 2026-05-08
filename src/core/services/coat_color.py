from typing import Literal
from uuid import UUID

from pydantic import ValidationError

from core.entities.base import _generate_slug
from core.entities.coat_color import CoatColor
from core.entities.equestrian import EquestrianContext
from core.exceptions.base import ClientError
from core.protocols.repositories import CoatColorRepositoryProtocol
from core.schemas import CoatColorCreateDto, CoatColorUpdateDto
from core.utils.html_security import validate_no_js_in_html

COAT_COLOR_NAME_MAX_LENGTH = 63
COAT_COLOR_SHORT_NAME_MAX_LENGTH = 63
COAT_COLOR_SLUG_MAX_LENGTH = 63
COAT_COLOR_DESCRIPTION_MAX_LENGTH = 511
DEFAULT_PAGE_DATA = "<div></div>"


class CoatColorService:
    def __init__(self, coat_color_repository: CoatColorRepositoryProtocol):
        self.coat_color_repository = coat_color_repository

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

    def _validate_coat_color_data(
        self, data: dict[str, str | None], *, partial: bool
    ) -> None:
        if not partial or "name" in data:
            data["name"] = self._validate_required_text(
                field="Название масти",
                value=data.get("name"),
                max_length=COAT_COLOR_NAME_MAX_LENGTH,
            )

        if "short_name" in data:
            data["short_name"] = self._validate_optional_text(
                field="Короткое название масти",
                value=data["short_name"],
                max_length=COAT_COLOR_SHORT_NAME_MAX_LENGTH,
            )
        if "slug" in data:
            data["slug"] = self._validate_required_text(
                field="Slug",
                value=data["slug"],
                max_length=COAT_COLOR_SLUG_MAX_LENGTH,
            )
        if "description" in data:
            data["description"] = self._validate_optional_text(
                field="Описание масти",
                value=data["description"],
                max_length=COAT_COLOR_DESCRIPTION_MAX_LENGTH,
            )
        if "page_data" in data:
            data["page_data"] = self._validate_optional_text(
                field="Данные страницы масти",
                value=data["page_data"],
            )
            if data["page_data"] is not None:
                validate_no_js_in_html("Данные страницы масти", data["page_data"])

    def _validate_pagination(self, *, limit: int | None, offset: int | None) -> None:
        if limit is not None and limit < 0:
            raise ClientError("Лимит не может быть меньше 0")
        if offset is not None and offset < 0:
            raise ClientError("Смещение не может быть меньше 0")

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
            existing = await self.coat_color_repository.find_by_slug(
                current_slug, equestrian_id=equestrian_context.id
            )
            if existing is None or (
                exclude_id is not None and existing.id == exclude_id
            ):
                return current_slug
            current_slug = f"{base_slug}-{counter}"
            counter += 1

    async def create(
        self, data: CoatColorCreateDto, *, equestrian_context: EquestrianContext
    ) -> CoatColor:
        """Создать новую масть."""

        coat_color_data = data.model_dump(exclude_none=True)
        self._validate_coat_color_data(coat_color_data, partial=False)

        existing = await self.coat_color_repository.find_by_name(
            coat_color_data["name"], equestrian_id=equestrian_context.id
        )
        if existing is not None:
            raise ClientError(
                f"Масть с названием '{coat_color_data['name']}' уже существует"
            )

        if "slug" not in coat_color_data:
            coat_color_data["slug"] = _generate_slug(coat_color_data["name"])
            coat_color_data["slug"] = await self._ensure_unique_slug(
                coat_color_data["slug"], equestrian_context=equestrian_context
            )
        else:
            existing_slug = await self.coat_color_repository.find_by_slug(
                coat_color_data["slug"], equestrian_id=equestrian_context.id
            )
            if existing_slug is not None:
                raise ClientError(
                    f"Масть со slug '{coat_color_data['slug']}' уже существует"
                )

        if "page_data" not in coat_color_data or coat_color_data["page_data"] is None:
            coat_color_data["page_data"] = DEFAULT_PAGE_DATA

        try:
            coat_color = CoatColor(
                **coat_color_data, equestrian_id=equestrian_context.id
            )
        except ValidationError as ex:
            raise ClientError(str(ex)) from ex
        return await self.coat_color_repository.create(coat_color)

    async def update(
        self,
        slug_or_id: str,
        data: CoatColorUpdateDto,
        *,
        equestrian_context: EquestrianContext,
    ) -> CoatColor:
        """Обновить масть."""
        parsed = self._parse_slug_or_id(slug_or_id)
        coat_color = await self.coat_color_repository.get_by_slug_or_id(
            parsed, equestrian_id=equestrian_context.id
        )
        if coat_color is None:
            raise ClientError("Масть не найдена")

        update_data = data.model_dump(exclude_none=True)
        if not update_data:
            raise ClientError("Нет данных для обновления")
        self._validate_coat_color_data(update_data, partial=True)

        if "name" in update_data:
            existing = await self.coat_color_repository.find_by_name(
                update_data["name"], equestrian_id=equestrian_context.id
            )
            if existing is not None and existing.id != coat_color.id:
                raise ClientError(
                    f"Масть с названием '{update_data['name']}' уже существует"
                )

        if "slug" in update_data:
            existing_slug = await self.coat_color_repository.find_by_slug(
                update_data["slug"], equestrian_id=equestrian_context.id
            )
            if existing_slug is not None and existing_slug.id != coat_color.id:
                raise ClientError(
                    f"Масть со slug '{update_data['slug']}' уже существует"
                )

        if "name" in update_data and "slug" not in update_data:
            new_slug = _generate_slug(update_data["name"])
            update_data["slug"] = await self._ensure_unique_slug(
                new_slug,
                equestrian_context=equestrian_context,
                exclude_id=coat_color.id,
            )

        for key, value in update_data.items():
            setattr(coat_color, key, value)

        return await self.coat_color_repository.update(coat_color)

    async def get_by_slug_or_id(
        self, slug_or_id: str, *, equestrian_context: EquestrianContext
    ) -> CoatColor:
        """Получить масть по slug или UUID."""

        parsed = self._parse_slug_or_id(slug_or_id)
        coat_color = await self.coat_color_repository.get_by_slug_or_id(
            parsed, equestrian_id=equestrian_context.id
        )
        if coat_color is None:
            raise ClientError("Масть не найдена")
        return coat_color

    async def delete(
        self, slug_or_id: str, *, equestrian_context: EquestrianContext
    ) -> None:
        """Удалить масть."""

        parsed = self._parse_slug_or_id(slug_or_id)
        coat_color = await self.coat_color_repository.get_by_slug_or_id(
            parsed, equestrian_id=equestrian_context.id
        )
        if coat_color is None:
            raise ClientError("Масть не найдена")
        await self.coat_color_repository.delete(
            coat_color.id, equestrian_id=equestrian_context.id
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
                Literal["name", "description", "slug", "-name", "-description", "-slug"]
            ]
            | None
        ) = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[list[CoatColor], int]:
        """Получить отфильтрованный список мастей."""
        self._validate_pagination(limit=limit, offset=offset)
        return await self.coat_color_repository.get_filtered(
            equestrian_id=equestrian_context.id,
            name=name,
            slug=slug,
            description=description,
            page_data=page_data,
            sort=sort,
            limit=limit,
            offset=offset,
        )
