from uuid import UUID

from pydantic import ValidationError

from core.entities.base import _generate_slug
from core.entities.breed_groups import BreedGroup
from core.entities.equestrian import EquestrianContext
from core.exceptions.auth import ForbiddenError
from core.exceptions.base import ClientError
from core.protocols.repositories.breed_group_repository import (
    BreedGroupRepositoryProtocol,
    BreedGroupSort,
)
from core.schemas.breed_groups import BreedGroupCreateDto, BreedGroupUpdateDto
from core.schemas.users import UserOutDto
from core.utils.html_security import validate_no_js_in_html

NAME_MAX = 63
SLUG_MAX = 63
DEFAULT_PAGE_DATA = "<div></div>"
ADMIN_SCOPES = frozenset({"SUPERUSER", "ADMIN", "DEVELOPER"})


class BreedGroupService:
    def __init__(self, repository: BreedGroupRepositoryProtocol):
        self.repository = repository

    @staticmethod
    def _parse(value: str) -> str | UUID:
        try:
            return UUID(value)
        except ValueError:
            return value

    @staticmethod
    def _permission(user: UserOutDto | None) -> None:
        if user is not None and not any(
            scope.scope_name in ADMIN_SCOPES for scope in user.scopes
        ):
            raise ForbiddenError("Недостаточно прав для выполнения операции")

    @staticmethod
    def _text(field: str, value: str | None, maximum: int) -> str:
        normalized = (value or "").strip()
        if not normalized:
            raise ClientError(f"{field} не может быть пустым")
        if len(normalized) > maximum:
            raise ClientError(f"{field} не может быть длиннее {maximum} символов")
        return normalized

    async def _slug(
        self, value: str, *, context: EquestrianContext, exclude: UUID | None = None
    ) -> str:
        base = value
        current = base
        counter = 1
        while True:
            entity = await self.repository.find_by_slug(
                current, equestrian_id=context.id
            )
            if entity is None or entity.id == exclude:
                return current
            current = f"{base}-{counter}"
            counter += 1

    async def create(
        self,
        data: BreedGroupCreateDto,
        *,
        equestrian_context: EquestrianContext,
        user: UserOutDto | None = None,
    ) -> BreedGroup:
        self._permission(user)
        name = self._text("Название группы", data.name, NAME_MAX)
        if await self.repository.find_by_name(
            name, equestrian_id=equestrian_context.id
        ):
            raise ClientError(f"Группа пород с названием '{name}' уже существует")
        slug = self._text("Slug", data.slug or _generate_slug(name), SLUG_MAX)
        slug = await self._slug(slug, context=equestrian_context)
        page_data = data.page_data if data.page_data is not None else DEFAULT_PAGE_DATA
        validate_no_js_in_html("Данные страницы группы пород", page_data)
        try:
            entity = BreedGroup(
                equestrian_id=equestrian_context.id,
                name=name,
                slug=slug,
                page_data=page_data,
            )
        except ValidationError as exc:
            raise ClientError(str(exc)) from exc
        return await self.repository.create(entity)

    async def get(
        self, slug_or_id: str, *, equestrian_context: EquestrianContext
    ) -> BreedGroup:
        entity = await self.repository.get_by_slug_or_id(
            self._parse(slug_or_id), equestrian_id=equestrian_context.id
        )
        if entity is None:
            raise ClientError("Группа пород не найдена")
        return entity

    async def list(
        self,
        *,
        equestrian_context: EquestrianContext,
        name: str | None = None,
        slug: str | None = None,
        page_data: str | None = None,
        sort: list[BreedGroupSort] | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[list[BreedGroup], int]:
        return await self.repository.get_filtered(
            equestrian_id=equestrian_context.id,
            name=name,
            slug=slug,
            page_data=page_data,
            sort=sort,
            limit=limit,
            offset=offset,
        )

    async def update(
        self,
        slug_or_id: str,
        data: BreedGroupUpdateDto,
        *,
        equestrian_context: EquestrianContext,
        user: UserOutDto | None = None,
    ) -> BreedGroup:
        self._permission(user)
        entity = await self.get(slug_or_id, equestrian_context=equestrian_context)
        values = data.model_dump(exclude_unset=True)
        if not values:
            raise ClientError("Нет данных для обновления")
        if "name" in values:
            values["name"] = self._text("Название группы", values["name"], NAME_MAX)
            existing = await self.repository.find_by_name(
                values["name"], equestrian_id=equestrian_context.id
            )
            if existing is not None and existing.id != entity.id:
                raise ClientError("Группа пород с таким названием уже существует")
        if "slug" in values:
            values["slug"] = self._text("Slug", values["slug"], SLUG_MAX)
        elif "name" in values:
            values["slug"] = _generate_slug(values["name"])
        if "slug" in values:
            values["slug"] = await self._slug(
                values["slug"], context=equestrian_context, exclude=entity.id
            )
        if "page_data" in values:
            if values["page_data"] is None:
                raise ClientError("Данные страницы не могут быть null")
            validate_no_js_in_html("Данные страницы группы пород", values["page_data"])
        for key, value in values.items():
            setattr(entity, key, value)
        return await self.repository.update(entity)

    async def delete(
        self,
        slug_or_id: str,
        *,
        equestrian_context: EquestrianContext,
        user: UserOutDto | None = None,
    ) -> None:
        self._permission(user)
        entity = await self.get(slug_or_id, equestrian_context=equestrian_context)
        await self.repository.delete(entity.id, equestrian_id=equestrian_context.id)
