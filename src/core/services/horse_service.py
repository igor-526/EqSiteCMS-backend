from typing import Literal
from uuid import UUID

from core.entities.horse_service import HorseServiceEntity
from core.exceptions.base import ClientError
from core.protocols.repositories.horse_service_repository import (
    HorseServiceRepositoryProtocol,
)
from core.schemas.horse_service import HorseServiceCreateDto, HorseServiceUpdateDto


class HorseServiceService:
    def __init__(self, horse_service_repository: HorseServiceRepositoryProtocol):
        self.horse_service_repository = horse_service_repository

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
            existing = await self.horse_service_repository.find_by_slug(current_slug)
            if existing is None or (
                exclude_id is not None and existing.id == exclude_id
            ):
                return current_slug
            current_slug = f"{base_slug}-{counter}"
            counter += 1

    async def create(self, data: HorseServiceCreateDto) -> HorseServiceEntity:
        """Создать новую услугу."""
        horse_service_data = data.model_dump(exclude_none=True)

        # Проверяем уникальность name
        existing = await self.horse_service_repository.find_by_name(
            horse_service_data["name"]
        )
        if existing is not None:
            raise ClientError(
                f"Услуга с названием '{horse_service_data['name']}' уже существует"
            )

        # Если slug не задан, генерируем из name
        if "slug" not in horse_service_data or horse_service_data["slug"] is None:
            from core.entities.base import _generate_slug

            horse_service_data["slug"] = _generate_slug(horse_service_data["name"])

        # Обеспечиваем уникальность slug
        horse_service_data["slug"] = await self._ensure_unique_slug(
            horse_service_data["slug"]
        )

        # Устанавливаем page_data по умолчанию, если не задан
        if (
            "page_data" not in horse_service_data
            or horse_service_data["page_data"] is None
        ):
            horse_service_data["page_data"] = "<div></div>"

        horse_service = HorseServiceEntity(**horse_service_data)
        return await self.horse_service_repository.create(horse_service)

    async def update(
        self, slug_or_id: str, data: HorseServiceUpdateDto
    ) -> HorseServiceEntity:
        """Обновить услугу."""
        parsed = self._parse_slug_or_id(slug_or_id)
        horse_service = await self.horse_service_repository.get_by_slug_or_id(parsed)
        if horse_service is None:
            raise ClientError("Услуга не найдена")

        update_data = data.model_dump(exclude_none=True)

        # Если обновляется name, проверяем уникальность
        if "name" in update_data:
            existing = await self.horse_service_repository.find_by_name(
                update_data["name"]
            )
            if existing is not None and existing.id != horse_service.id:
                raise ClientError(
                    f"Услуга с названием '{update_data['name']}' уже существует"
                )

        # Если обновляется slug, проверяем уникальность
        if "slug" in update_data:
            update_data["slug"] = await self._ensure_unique_slug(
                update_data["slug"], exclude_id=horse_service.id
            )

        # Если обновляется name и slug не задан, генерируем slug из name
        if "name" in update_data and "slug" not in update_data:
            from core.entities.base import _generate_slug

            new_slug = _generate_slug(update_data["name"])
            update_data["slug"] = await self._ensure_unique_slug(
                new_slug, exclude_id=horse_service.id
            )

        for key, value in update_data.items():
            setattr(horse_service, key, value)

        return await self.horse_service_repository.update(horse_service)

    async def get_by_slug_or_id(self, slug_or_id: str) -> HorseServiceEntity | None:
        """Получить услугу по slug или UUID."""
        parsed = self._parse_slug_or_id(slug_or_id)
        return await self.horse_service_repository.get_by_slug_or_id(parsed)

    async def delete(self, slug_or_id: str) -> None:
        """Удалить услугу."""
        parsed = self._parse_slug_or_id(slug_or_id)
        horse_service = await self.horse_service_repository.get_by_slug_or_id(parsed)
        if horse_service is None:
            raise ClientError("Услуга не найдена")
        await self.horse_service_repository.delete(horse_service.id)

    async def get_filtered(
        self,
        *,
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
        return await self.horse_service_repository.get_filtered(
            name=name,
            slug=slug,
            description=description,
            page_data=page_data,
            sort=sort,
            limit=limit,
            offset=offset,
        )
