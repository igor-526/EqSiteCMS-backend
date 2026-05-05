from typing import Literal
from uuid import UUID

from core.entities.prices import Price, PriceGroup
from core.exceptions.base import ClientError
from core.protocols.repositories.photo_repository import PhotoRepositoryProtocol
from core.protocols.repositories.price_repository import (
    PriceGroupRepositoryProtocol,
    PriceRepositoryProtocol,
)
from core.schemas.prices import (
    PriceCreateDto,
    PriceGroupCreateDto,
    PriceGroupUpdateDto,
    PricePhotosUpdateDto,
    PriceUpdateDto,
)


class PriceGroupService:
    def __init__(self, price_group_repository: PriceGroupRepositoryProtocol):
        self.price_group_repository = price_group_repository

    async def _ensure_unique_name(
        self, name: str, exclude_id: UUID | None = None
    ) -> str:
        """Обеспечивает уникальность name."""
        existing = await self.price_group_repository.find_by_name(name)
        if existing is None or (exclude_id is not None and existing.id == exclude_id):
            return name
        raise ClientError(f"Группа с названием '{name}' уже существует")

    async def create(self, data: PriceGroupCreateDto) -> PriceGroup:
        """Создать новую группу."""
        group_data = data.model_dump(exclude_none=True)

        # Проверяем уникальность name
        await self._ensure_unique_name(group_data["name"])

        price_group = PriceGroup(**group_data)
        return await self.price_group_repository.create(price_group)

    async def update(self, id: UUID, data: PriceGroupUpdateDto) -> PriceGroup:
        """Обновить группу."""
        price_group = await self.price_group_repository.get_by_id(id)
        if price_group is None:
            raise ClientError("Группа не найдена")

        update_data = data.model_dump(exclude_none=True)

        # Если обновляется name, проверяем уникальность
        if "name" in update_data:
            await self._ensure_unique_name(
                update_data["name"], exclude_id=price_group.id
            )

        for key, value in update_data.items():
            setattr(price_group, key, value)

        return await self.price_group_repository.update(price_group)

    async def get_by_id(self, id: UUID) -> PriceGroup | None:
        """Получить группу по UUID."""
        return await self.price_group_repository.get_by_id(id)

    async def delete(self, id: UUID) -> None:
        """Удалить группу."""
        price_group = await self.price_group_repository.get_by_id(id)
        if price_group is None:
            raise ClientError("Группа не найдена")
        await self.price_group_repository.delete(id)

    async def get_filtered(
        self,
        *,
        name: str | None = None,
        description: str | None = None,
        sort: list[Literal["name", "-name"]] | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[list[PriceGroup], int]:
        """Получить отфильтрованный список групп."""
        return await self.price_group_repository.get_filtered(
            name=name,
            description=description,
            sort=sort,
            limit=limit,
            offset=offset,
        )


class PriceService:
    def __init__(
        self,
        price_repository: PriceRepositoryProtocol,
        price_group_repository: PriceGroupRepositoryProtocol,
        photo_repository: PhotoRepositoryProtocol,
    ):
        self.price_repository = price_repository
        self.price_group_repository = price_group_repository
        self.photo_repository = photo_repository

    def _parse_slug_or_id(self, slug_or_id: str) -> str | UUID:
        """Попытаться преобразовать строку в UUID, иначе вернуть как есть."""
        try:
            return UUID(slug_or_id)
        except ValueError:
            return slug_or_id

    async def _ensure_unique_name(
        self, name: str, exclude_id: UUID | None = None
    ) -> str:
        """Обеспечивает уникальность name."""
        existing = await self.price_repository.find_by_name(name)
        if existing is None or (exclude_id is not None and existing.id == exclude_id):
            return name
        raise ClientError(f"Цена с названием '{name}' уже существует")

    async def _ensure_unique_slug(
        self, slug: str, exclude_id: UUID | None = None
    ) -> str:
        """Обеспечивает уникальность slug."""
        base_slug = slug
        counter = 1
        current_slug = base_slug

        while True:
            existing = await self.price_repository.get_by_slug_or_id(current_slug)
            if existing is None or (
                exclude_id is not None and existing.id == exclude_id
            ):
                return current_slug
            current_slug = f"{base_slug}-{counter}"
            counter += 1

    async def create(self, data: PriceCreateDto) -> Price:
        """Создать новую цену."""
        price_data = data.model_dump(exclude_none=True)
        groups = price_data.pop("groups", [])

        # Проверяем уникальность name
        await self._ensure_unique_name(price_data["name"])

        # Если slug не задан, генерируем из name
        if "slug" not in price_data or price_data["slug"] is None:
            from core.entities.base import _generate_slug

            price_data["slug"] = _generate_slug(price_data["name"])

        # Обеспечиваем уникальность slug
        price_data["slug"] = await self._ensure_unique_slug(price_data["slug"])

        # Устанавливаем page_data по умолчанию, если не задан
        if "page_data" not in price_data or price_data["page_data"] is None:
            price_data["page_data"] = "<div></div>"

        price = Price(**price_data)
        price = await self.price_repository.create(price)

        # Устанавливаем связи с группами
        if groups:
            # Проверяем, что все группы существуют
            for group_id in groups:
                group = await self.price_group_repository.get_by_id(group_id)
                if group is None:
                    raise ClientError(f"Группа с ID '{group_id}' не найдена")

            await self.price_repository.set_price_groups(price.id, groups)

        return price

    async def update(self, slug_or_id: str, data: PriceUpdateDto) -> Price:
        """Обновить цену."""
        parsed = self._parse_slug_or_id(slug_or_id)
        price = await self.price_repository.get_by_slug_or_id(str(parsed))
        if price is None:
            raise ClientError("Цена не найдена")

        update_data = data.model_dump(exclude_none=True)
        groups = update_data.pop("groups", None)

        # Если обновляется name, проверяем уникальность
        if "name" in update_data:
            await self._ensure_unique_name(update_data["name"], exclude_id=price.id)

        # Если обновляется slug, проверяем уникальность
        if "slug" in update_data:
            update_data["slug"] = await self._ensure_unique_slug(
                update_data["slug"], exclude_id=price.id
            )

        # Если обновляется name и slug не задан, генерируем slug из name
        if "name" in update_data and "slug" not in update_data:
            from core.entities.base import _generate_slug

            new_slug = _generate_slug(update_data["name"])
            update_data["slug"] = await self._ensure_unique_slug(
                new_slug, exclude_id=price.id
            )

        for key, value in update_data.items():
            setattr(price, key, value)

        price = await self.price_repository.update(price)

        # Обновляем связи с группами, если переданы
        if groups is not None:
            # Проверяем, что все группы существуют
            for group_id in groups:
                group = await self.price_group_repository.get_by_id(group_id)
                if group is None:
                    raise ClientError(f"Группа с ID '{group_id}' не найдена")

            await self.price_repository.set_price_groups(price.id, groups)

        return price

    async def get_by_slug_or_id(self, slug_or_id: str) -> Price | None:
        """Получить цену по slug или UUID."""
        parsed = self._parse_slug_or_id(slug_or_id)
        return await self.price_repository.get_by_slug_or_id(str(parsed))

    async def delete(self, slug_or_id: str) -> None:
        """Удалить цену."""
        parsed = self._parse_slug_or_id(slug_or_id)
        price = await self.price_repository.get_by_slug_or_id(str(parsed))
        if price is None:
            raise ClientError("Цена не найдена")
        await self.price_repository.delete(price.id)

    async def get_filtered(
        self,
        *,
        name: str | list[str] | None = None,
        description: str | None = None,
        groups: str | list[str] | None = None,
        sort: list[Literal["name", "-name"]] | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[list[Price], int]:
        """Получить отфильтрованный список цен."""
        return await self.price_repository.get_filtered(
            name=name,
            description=description,
            groups=groups,
            sort=sort,
            limit=limit,
            offset=offset,
        )

    async def update_price_photos(
        self, slug_or_id: str, data: PricePhotosUpdateDto
    ) -> None:
        """Обновить фотографии цены."""
        parsed = self._parse_slug_or_id(slug_or_id)
        price = await self.price_repository.get_by_slug_or_id(str(parsed))
        if price is None:
            raise ClientError("Цена не найдена")

        photo_ids = data.photo_ids
        main_photo_id = data.main

        # Если передан main_photo_id, проверяем, что фотография существует
        if main_photo_id is not None:
            photo = await self.photo_repository.get_by_id(main_photo_id)
            if photo is None:
                raise ClientError(f"Фотография с ID '{main_photo_id}' не найдена")

            # Если передан photo_ids, проверяем, что main_photo_id входит в список
            if photo_ids is not None and main_photo_id not in photo_ids:
                raise ClientError(
                    "Главная фотография должна входить в список фотографий"
                )

        # Если передан photo_ids, проверяем, что все фотографии существуют
        if photo_ids is not None:
            for photo_id in photo_ids:
                photo = await self.photo_repository.get_by_id(photo_id)
                if photo is None:
                    raise ClientError(f"Фотография с ID '{photo_id}' не найдена")

        await self.price_repository.set_price_photos(
            price.id, photo_ids=photo_ids, main_photo_id=main_photo_id
        )
