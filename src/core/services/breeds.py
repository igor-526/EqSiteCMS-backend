from typing import Literal
from uuid import UUID

from core.entities.base import _generate_slug
from core.entities.breeds import Breed
from core.exceptions.base import ClientError
from core.protocols.repositories.breed_repository import BreedRepositoryProtocol
from core.schemas.breeds import BreedCreateDto, BreedUpdateDto


class BreedService:
    def __init__(self, breed_repository: BreedRepositoryProtocol):
        self.breed_repository = breed_repository

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
            existing = await self.breed_repository.find_by_slug(current_slug)
            if existing is None or (
                exclude_id is not None and existing.id == exclude_id
            ):
                return current_slug
            current_slug = f"{base_slug}-{counter}"
            counter += 1

    async def create(self, data: BreedCreateDto) -> Breed:
        """Создать новую породу."""

        breed_data = data.model_dump(exclude_none=True)

        existing = await self.breed_repository.find_by_name(breed_data["name"])
        if existing is not None:
            raise ClientError(
                f"Порода с названием '{breed_data['name']}' уже существует"
            )

        if "slug" not in breed_data or breed_data["slug"] is None:
            from core.entities.base import _generate_slug

            breed_data["slug"] = _generate_slug(breed_data["name"])

        breed_data["slug"] = await self._ensure_unique_slug(breed_data["slug"])

        if "page_data" not in breed_data or breed_data["page_data"] is None:
            breed_data["page_data"] = "<div></div>"

        breed = Breed(**breed_data)
        return await self.breed_repository.create(breed)

    async def update(self, slug_or_id: str, data: BreedUpdateDto) -> Breed:
        """Обновить породу."""

        parsed = self._parse_slug_or_id(slug_or_id)
        breed = await self.breed_repository.get_by_slug_or_id(parsed)
        if breed is None:
            raise ClientError("Порода не найдена")

        update_data = data.model_dump(exclude_none=True)

        if "name" in update_data:
            existing = await self.breed_repository.find_by_name(update_data["name"])
            if existing is not None and existing.id != breed.id:
                raise ClientError(
                    f"Порода с названием '{update_data['name']}' уже существует"
                )

        if "slug" in update_data:
            update_data["slug"] = await self._ensure_unique_slug(
                update_data["slug"], exclude_id=breed.id
            )

        if "name" in update_data and "slug" not in update_data:

            new_slug = _generate_slug(update_data["name"])
            update_data["slug"] = await self._ensure_unique_slug(
                new_slug, exclude_id=breed.id
            )

        for key, value in update_data.items():
            setattr(breed, key, value)

        return await self.breed_repository.update(breed)

    async def get_by_slug_or_id(self, slug_or_id: str) -> Breed | None:
        """Получить породу по slug или UUID."""

        parsed = self._parse_slug_or_id(slug_or_id)
        return await self.breed_repository.get_by_slug_or_id(parsed)

    async def delete(self, slug_or_id: str) -> None:
        """Удалить породу."""

        parsed = self._parse_slug_or_id(slug_or_id)
        breed = await self.breed_repository.get_by_slug_or_id(parsed)
        if breed is None:
            raise ClientError("Порода не найдена")
        await self.breed_repository.delete(breed.id)

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
    ) -> tuple[list[Breed], int]:
        """Получить отфильтрованный список пород."""
        return await self.breed_repository.get_filtered(
            name=name,
            slug=slug,
            description=description,
            page_data=page_data,
            sort=sort,
            limit=limit,
            offset=offset,
        )
