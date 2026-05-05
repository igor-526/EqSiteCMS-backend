from typing import Literal
from uuid import UUID

from core.entities.coat_color import CoatColor
from core.exceptions.base import ClientError
from core.protocols.repositories.coat_color_repository import (
    CoatColorRepositoryProtocol,
)
from core.schemas.coat_color import CoatColorCreateDto, CoatColorUpdateDto


class CoatColorService:
    def __init__(self, coat_color_repository: CoatColorRepositoryProtocol):
        self.coat_color_repository = coat_color_repository

    def _parse_slug_or_id(self, slug_or_id: str) -> str | UUID:
        """Попытаться преобразовать строку в UUID, иначе вернуть как есть."""

        try:
            return UUID(slug_or_id)
        except ValueError:
            return slug_or_id

    async def _ensure_unique_slug(
        self, slug: str, exclude_id: UUID | None = None
    ) -> str:
        """Обеспечивает уникальность slug, добавляя суффиксы -1, -2 и т.д."""

        base_slug = slug
        counter = 1
        current_slug = base_slug

        while True:
            existing = await self.coat_color_repository.find_by_slug(current_slug)
            if existing is None or (
                exclude_id is not None and existing.id == exclude_id
            ):
                return current_slug
            current_slug = f"{base_slug}-{counter}"
            counter += 1

    async def create(self, data: CoatColorCreateDto) -> CoatColor:
        """Создать новую масть."""

        coat_color_data = data.model_dump(exclude_none=True)

        existing = await self.coat_color_repository.find_by_name(
            coat_color_data["name"]
        )
        if existing is not None:
            raise ClientError(
                f"Масть с названием '{coat_color_data['name']}' уже существует"
            )

        if "slug" not in coat_color_data or coat_color_data["slug"] is None:
            from core.entities.base import _generate_slug

            coat_color_data["slug"] = _generate_slug(coat_color_data["name"])

        coat_color_data["slug"] = await self._ensure_unique_slug(
            coat_color_data["slug"]
        )

        if "page_data" not in coat_color_data or coat_color_data["page_data"] is None:
            coat_color_data["page_data"] = "<div></div>"

        coat_color = CoatColor(**coat_color_data)
        return await self.coat_color_repository.create(coat_color)

    async def update(self, slug_or_id: str, data: CoatColorUpdateDto) -> CoatColor:
        """Обновить масть."""
        parsed = self._parse_slug_or_id(slug_or_id)
        coat_color = await self.coat_color_repository.get_by_slug_or_id(parsed)
        if coat_color is None:
            raise ClientError("Масть не найдена")

        update_data = data.model_dump(exclude_none=True)

        if "name" in update_data:
            existing = await self.coat_color_repository.find_by_name(
                update_data["name"]
            )
            if existing is not None and existing.id != coat_color.id:
                raise ClientError(
                    f"Масть с названием '{update_data['name']}' уже существует"
                )

        if "slug" in update_data:
            update_data["slug"] = await self._ensure_unique_slug(
                update_data["slug"], exclude_id=coat_color.id
            )

        if "name" in update_data and "slug" not in update_data:
            from core.entities.base import _generate_slug

            new_slug = _generate_slug(update_data["name"])
            update_data["slug"] = await self._ensure_unique_slug(
                new_slug, exclude_id=coat_color.id
            )

        for key, value in update_data.items():
            setattr(coat_color, key, value)

        return await self.coat_color_repository.update(coat_color)

    async def get_by_slug_or_id(self, slug_or_id: str) -> CoatColor | None:
        """Получить масть по slug или UUID."""

        parsed = self._parse_slug_or_id(slug_or_id)
        return await self.coat_color_repository.get_by_slug_or_id(parsed)

    async def delete(self, slug_or_id: str) -> None:
        """Удалить масть."""

        parsed = self._parse_slug_or_id(slug_or_id)
        coat_color = await self.coat_color_repository.get_by_slug_or_id(parsed)
        if coat_color is None:
            raise ClientError("Масть не найдена")
        await self.coat_color_repository.delete(coat_color.id)

    async def get_filtered(
        self,
        *,
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
        return await self.coat_color_repository.get_filtered(
            name=name,
            slug=slug,
            description=description,
            page_data=page_data,
            sort=sort,
            limit=limit,
            offset=offset,
        )
