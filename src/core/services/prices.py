from typing import Literal, Sequence
from uuid import UUID

from pydantic import ValidationError

from core.entities.base import _generate_slug
from core.entities.prices import Price, PriceGroup
from core.exceptions.base import ClientError
from core.protocols.media import PhotoUrlBuilderProtocol
from core.protocols.repositories.photo_repository import PhotoRepositoryProtocol
from core.protocols.repositories.price_repository import (
    PriceGroupRepositoryProtocol,
    PriceRepositoryProtocol,
)
from core.schemas.photos import PhotoOutShortDto
from core.schemas.prices import (
    PriceCreateDto,
    PriceGroupCreateDto,
    PriceGroupSimpleDto,
    PriceGroupUpdateDto,
    PriceOutDto,
    PriceOutWithPageDataDto,
    PriceOutWithTablesDto,
    PricePhotosUpdateDto,
    PriceUpdateDto,
)

PRICE_NAME_MAX_LENGTH = 63
PRICE_SLUG_MAX_LENGTH = 63
PRICE_DESCRIPTION_MAX_LENGTH = 511
PRICE_GROUP_NAME_MAX_LENGTH = 63
PRICE_GROUP_DESCRIPTION_MAX_LENGTH = 511
DEFAULT_PAGE_DATA = "<div></div>"


class PriceGroupService:
    def __init__(self, price_group_repository: PriceGroupRepositoryProtocol):
        self.price_group_repository = price_group_repository

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

    def _validate_group_data(
        self, data: dict[str, str | None], *, partial: bool
    ) -> None:
        if not partial or "name" in data:
            data["name"] = self._validate_required_text(
                field="Название группы",
                value=data.get("name"),
                max_length=PRICE_GROUP_NAME_MAX_LENGTH,
            )

        if "description" in data:
            data["description"] = self._validate_optional_text(
                field="Описание группы",
                value=data["description"],
                max_length=PRICE_GROUP_DESCRIPTION_MAX_LENGTH,
            )

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
        self._validate_group_data(group_data, partial=False)

        # Проверяем уникальность name
        await self._ensure_unique_name(group_data["name"])

        try:
            price_group = PriceGroup(**group_data)
        except ValidationError as ex:
            raise ClientError(str(ex)) from ex
        return await self.price_group_repository.create(price_group)

    async def update(self, id: UUID, data: PriceGroupUpdateDto) -> PriceGroup:
        """Обновить группу."""
        price_group = await self.price_group_repository.get_by_id(id)
        if price_group is None:
            raise ClientError("Группа не найдена")

        update_data = data.model_dump(exclude_none=True)
        if not update_data:
            raise ClientError("Нет данных для обновления")
        self._validate_group_data(update_data, partial=True)

        # Если обновляется name, проверяем уникальность
        if "name" in update_data:
            await self._ensure_unique_name(
                update_data["name"], exclude_id=price_group.id
            )

        for key, value in update_data.items():
            setattr(price_group, key, value)

        return await self.price_group_repository.update(price_group)

    async def get_by_id(self, id: UUID) -> PriceGroup:
        """Получить группу по UUID."""
        price_group = await self.price_group_repository.get_by_id(id)
        if price_group is None:
            raise ClientError("Группа не найдена")
        return price_group

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
        photo_url_builder: PhotoUrlBuilderProtocol,
    ):
        self.price_repository = price_repository
        self.price_group_repository = price_group_repository
        self.photo_repository = photo_repository
        self.photo_url_builder = photo_url_builder

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

    def _validate_price_data(self, data: dict, *, partial: bool) -> None:
        if not partial or "name" in data:
            data["name"] = self._validate_required_text(
                field="Название цены",
                value=data.get("name"),
                max_length=PRICE_NAME_MAX_LENGTH,
            )

        if "slug" in data:
            data["slug"] = self._validate_required_text(
                field="Slug",
                value=data["slug"],
                max_length=PRICE_SLUG_MAX_LENGTH,
            )
        if "description" in data:
            data["description"] = self._validate_optional_text(
                field="Описание цены",
                value=data["description"],
                max_length=PRICE_DESCRIPTION_MAX_LENGTH,
            )
        if "page_data" in data:
            data["page_data"] = self._validate_optional_text(
                field="Данные страницы цены",
                value=data["page_data"],
            )

    def _deduplicate_ids(self, ids: Sequence[UUID]) -> list[UUID]:
        return list(dict.fromkeys(ids))

    async def _ensure_groups_exist(self, group_ids: Sequence[UUID]) -> list[UUID]:
        unique_group_ids = self._deduplicate_ids(group_ids)
        if not unique_group_ids:
            return []

        groups = await self.price_group_repository.get_by_ids(unique_group_ids)
        for group_id in unique_group_ids:
            if group_id not in groups:
                raise ClientError(f"Группа с ID '{group_id}' не найдена")
        return unique_group_ids

    async def _ensure_photos_exist(self, photo_ids: Sequence[UUID]) -> list[UUID]:
        unique_photo_ids = self._deduplicate_ids(photo_ids)
        if not unique_photo_ids:
            return []

        photos = await self.photo_repository.get_by_ids(unique_photo_ids)
        for photo_id in unique_photo_ids:
            if photo_id not in photos:
                raise ClientError(f"Фотография с ID '{photo_id}' не найдена")
        return unique_photo_ids

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
        slug = self._validate_required_text(
            field="Slug",
            value=slug,
            max_length=PRICE_SLUG_MAX_LENGTH,
        )
        base_slug = slug
        counter = 1
        current_slug = base_slug

        while True:
            existing = await self.price_repository.get_by_slug_or_id(current_slug)
            if existing is None or (
                exclude_id is not None and existing.id == exclude_id
            ):
                return current_slug
            suffix = f"-{counter}"
            max_base_length = PRICE_SLUG_MAX_LENGTH - len(suffix)
            if max_base_length <= 0:
                raise ClientError("Не удалось сформировать уникальный slug")
            current_slug = f"{base_slug[:max_base_length]}{suffix}"
            counter += 1

    async def create(self, data: PriceCreateDto) -> Price:
        """Создать новую цену."""
        price_data = data.model_dump(exclude_none=True)
        groups = price_data.pop("groups", [])
        self._validate_price_data(price_data, partial=False)
        group_ids = await self._ensure_groups_exist(groups)

        # Проверяем уникальность name
        await self._ensure_unique_name(price_data["name"])

        # Если slug не задан, генерируем из name
        if "slug" not in price_data or price_data["slug"] is None:
            price_data["slug"] = _generate_slug(price_data["name"])

        # Обеспечиваем уникальность slug
        price_data["slug"] = await self._ensure_unique_slug(price_data["slug"])

        # Устанавливаем page_data по умолчанию, если не задан
        if "page_data" not in price_data or price_data["page_data"] is None:
            price_data["page_data"] = DEFAULT_PAGE_DATA

        try:
            price = Price(**price_data)
        except ValidationError as ex:
            raise ClientError(str(ex)) from ex

        # The request-scoped session commits after the endpoint returns; any failure
        # while creating relations propagates and rolls back the created price.
        price = await self.price_repository.create(price)
        if group_ids:
            await self.price_repository.set_price_groups(price.id, group_ids)

        return price

    async def update(self, slug_or_id: str, data: PriceUpdateDto) -> Price:
        """Обновить цену."""
        parsed = self._parse_slug_or_id(slug_or_id)
        price = await self.price_repository.get_by_slug_or_id(parsed)
        if price is None:
            raise ClientError("Цена не найдена")

        update_data = data.model_dump(exclude_none=True)
        groups = update_data.pop("groups", None)
        if not update_data and groups is None:
            raise ClientError("Нет данных для обновления")
        self._validate_price_data(update_data, partial=True)
        group_ids = None
        if groups is not None:
            group_ids = await self._ensure_groups_exist(groups)

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
            new_slug = _generate_slug(update_data["name"])
            update_data["slug"] = await self._ensure_unique_slug(
                new_slug, exclude_id=price.id
            )

        for key, value in update_data.items():
            setattr(price, key, value)

        if update_data:
            # Relation writes happen after entity update in the same request session;
            # exceptions bubble to the session dependency rollback path.
            price = await self.price_repository.update(price)

        if group_ids is not None:
            await self.price_repository.set_price_groups(price.id, group_ids)

        return price

    async def get_by_slug_or_id(self, slug_or_id: str) -> Price:
        """Получить цену по slug или UUID."""
        parsed = self._parse_slug_or_id(slug_or_id)
        price = await self.price_repository.get_by_slug_or_id(parsed)
        if price is None:
            raise ClientError("Цена не найдена")
        return price

    async def delete(self, slug_or_id: str) -> None:
        """Удалить цену."""
        parsed = self._parse_slug_or_id(slug_or_id)
        price = await self.price_repository.get_by_slug_or_id(parsed)
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
        price = await self.price_repository.get_by_slug_or_id(parsed)
        if price is None:
            raise ClientError("Цена не найдена")

        photo_ids = data.photo_ids
        main_photo_id = data.main
        if photo_ids is None and main_photo_id is None:
            raise ClientError("Нет данных для обновления")

        unique_photo_ids = None
        if photo_ids is not None:
            unique_photo_ids = await self._ensure_photos_exist(photo_ids)

        if main_photo_id is not None:
            if unique_photo_ids is not None:
                if main_photo_id not in unique_photo_ids:
                    raise ClientError(
                        "Главная фотография должна входить в список фотографий"
                    )
            else:
                photo = await self.photo_repository.get_by_id(main_photo_id)
                if photo is None:
                    raise ClientError(f"Фотография с ID '{main_photo_id}' не найдена")

                relations = await self.price_repository.get_price_photos(price.id)
                if main_photo_id not in {relation.photo_id for relation in relations}:
                    raise ClientError(
                        "Главная фотография должна входить в список фотографий"
                    )

        await self.price_repository.set_price_photos(
            price.id, photo_ids=unique_photo_ids, main_photo_id=main_photo_id
        )

    async def build_out_dto(
        self,
        price: Price,
        *,
        include_page_data: bool = False,
        include_tables: bool = False,
    ) -> PriceOutDto | PriceOutWithPageDataDto | PriceOutWithTablesDto:
        """Собрать DTO цены с группами, фотографиями и URL на service boundary."""
        groups_relations = await self.price_repository.get_price_groups(price.id)
        group_ids = self._deduplicate_ids(
            [relation.group_id for relation in groups_relations]
        )
        groups_data = (
            await self.price_group_repository.get_by_ids(group_ids) if group_ids else {}
        )
        groups = [
            PriceGroupSimpleDto(id=group.id, name=group.name)
            for group_id in group_ids
            if (group := groups_data.get(group_id)) is not None
        ]

        photos_relations = await self.price_repository.get_price_photos(price.id)
        sorted_photo_relations = sorted(
            photos_relations,
            key=lambda relation: not relation.is_main,
        )
        photo_ids = self._deduplicate_ids(
            [relation.photo_id for relation in sorted_photo_relations]
        )
        photos_data = (
            await self.photo_repository.get_by_ids(photo_ids) if photo_ids else {}
        )
        photos = [
            PhotoOutShortDto(
                id=photo.id,
                is_main=relation.is_main,
                url=self.photo_url_builder.build(photo.path),
            )
            for relation in sorted_photo_relations
            if (photo := photos_data.get(relation.photo_id)) is not None
        ]

        if include_tables:
            return PriceOutWithTablesDto(
                id=price.id,
                name=price.name,
                slug=price.slug,
                description=price.description,
                photos=photos,
                groups=groups,
                created_at=price.created_at,
                updated_at=price.updated_at,
                page_data=price.page_data or DEFAULT_PAGE_DATA,
                price_tables=price.price_tables or [],
            )
        if include_page_data:
            return PriceOutWithPageDataDto(
                id=price.id,
                name=price.name,
                slug=price.slug,
                description=price.description,
                photos=photos,
                groups=groups,
                created_at=price.created_at,
                updated_at=price.updated_at,
                page_data=price.page_data or DEFAULT_PAGE_DATA,
            )
        return PriceOutDto(
            id=price.id,
            name=price.name,
            slug=price.slug,
            description=price.description,
            photos=photos,
            groups=groups,
            created_at=price.created_at,
            updated_at=price.updated_at,
        )

    async def create_out(self, data: PriceCreateDto) -> PriceOutDto:
        price = await self.create(data)
        dto = await self.build_out_dto(price)
        if not isinstance(dto, PriceOutDto):
            raise RuntimeError("Unexpected price output DTO")
        return dto

    async def update_out(self, slug_or_id: str, data: PriceUpdateDto) -> PriceOutDto:
        price = await self.update(slug_or_id, data)
        dto = await self.build_out_dto(price)
        if not isinstance(dto, PriceOutDto):
            raise RuntimeError("Unexpected price output DTO")
        return dto

    async def get_by_slug_or_id_out(
        self,
        slug_or_id: str,
        *,
        include_page_data: bool = False,
        include_tables: bool = True,
    ) -> PriceOutDto | PriceOutWithPageDataDto | PriceOutWithTablesDto:
        price = await self.get_by_slug_or_id(slug_or_id)
        return await self.build_out_dto(
            price,
            include_page_data=include_page_data,
            include_tables=include_tables,
        )

    async def get_filtered_out(
        self,
        *,
        name: str | list[str] | None = None,
        description: str | None = None,
        groups: str | list[str] | None = None,
        sort: list[Literal["name", "-name"]] | None = None,
        limit: int | None = None,
        offset: int | None = None,
        include_tables: bool = True,
    ) -> tuple[
        list[PriceOutDto | PriceOutWithPageDataDto | PriceOutWithTablesDto], int
    ]:
        entities, total = await self.get_filtered(
            name=name,
            description=description,
            groups=groups,
            sort=sort,
            limit=limit,
            offset=offset,
        )
        items = [
            await self.build_out_dto(entity, include_tables=include_tables)
            for entity in entities
        ]
        return items, total
