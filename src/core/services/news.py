import re
from datetime import datetime, timezone
from typing import Sequence
from uuid import UUID

from core.entities.equestrian import EquestrianContext
from core.entities.news import News, NewsStatus
from core.exceptions.auth import ForbiddenError
from core.exceptions.base import ClientError, NotFoundError
from core.protocols.media import PhotoUrlBuilderProtocol
from core.protocols.repositories.news_repository import NewsRepositoryProtocol
from core.protocols.repositories.photo_repository import PhotoRepositoryProtocol
from core.schemas.news import (
    NewsCreateDto,
    NewsOutDto,
    NewsPhotosUpdateDto,
    NewsPublicOutDto,
    NewsUpdateDto,
)
from core.schemas.photos import PhotoOutShortDto
from core.schemas.users import UserOutDto
from core.utils.html_security import validate_no_js_in_html

NEWS_NAME_MAX_LENGTH = 63
NEWS_SNIPPET_MAX_LENGTH = 255


class NewsService:
    _ADMIN_SCOPE_NAMES: frozenset[str] = frozenset({"SUPERUSER", "ADMIN", "DEVELOPER"})

    def __init__(
        self,
        news_repository: NewsRepositoryProtocol,
        photo_repository: PhotoRepositoryProtocol,
        photo_url_builder: PhotoUrlBuilderProtocol,
    ):
        self.news_repository = news_repository
        self.photo_repository = photo_repository
        self.photo_url_builder = photo_url_builder

    async def _check_admin_permission(self, *, user: UserOutDto) -> None:
        has_scope = any(
            scope.scope_name in self._ADMIN_SCOPE_NAMES for scope in user.scopes
        )
        if not has_scope:
            raise ForbiddenError("Недостаточно прав для выполнения операции")

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

    @staticmethod
    def _strip_html_to_text(html: str) -> str:
        text = re.sub(r"<[^>]+>", " ", html)
        return re.sub(r"\s+", " ", text).strip()

    def _generate_snippet(self, content: str) -> str | None:
        if not content:
            return None
        plain = self._strip_html_to_text(content)
        return plain[:NEWS_SNIPPET_MAX_LENGTH] if plain else None

    def _validate_news_data(self, data: dict, *, partial: bool) -> None:
        if not partial or "name" in data:
            data["name"] = self._validate_required_text(
                field="Название",
                value=data.get("name"),
                max_length=NEWS_NAME_MAX_LENGTH,
            )
        if "snippet" in data:
            data["snippet"] = self._validate_optional_text(
                field="Сниппет",
                value=data["snippet"],
                max_length=NEWS_SNIPPET_MAX_LENGTH,
            )
        if "content" in data:
            content = data["content"]
            if content:
                validate_no_js_in_html("Содержимое", content)

    def _deduplicate_ids(self, ids: Sequence[UUID]) -> list[UUID]:
        return list(dict.fromkeys(ids))

    async def _ensure_photos_exist(
        self, photo_ids: Sequence[UUID], *, equestrian_context: EquestrianContext
    ) -> list[UUID]:
        unique = self._deduplicate_ids(photo_ids)
        if not unique:
            return []
        photos = await self.photo_repository.get_by_ids(
            unique, equestrian_id=equestrian_context.id
        )
        for photo_id in unique:
            if photo_id not in photos:
                raise ClientError(f"Фотография с ID '{photo_id}' не найдена")
        return unique

    async def create(
        self,
        data: NewsCreateDto,
        *,
        equestrian_context: EquestrianContext,
        user: UserOutDto,
    ) -> News:
        await self._check_admin_permission(user=user)

        news_data = data.model_dump()
        photo_ids = news_data.pop("photo_ids", [])
        main_photo_id = news_data.pop("main_photo_id", None)

        self._validate_news_data(news_data, partial=False)

        if news_data.get("snippet") is None:
            news_data["snippet"] = self._generate_snippet(news_data.get("content", ""))

        unique_photo_ids = await self._ensure_photos_exist(
            photo_ids, equestrian_context=equestrian_context
        )
        if main_photo_id is not None and unique_photo_ids:
            if main_photo_id not in unique_photo_ids:
                raise ClientError(
                    "Главная фотография должна входить в список фотографий"
                )

        news = News(**news_data, equestrian_id=equestrian_context.id)
        news = await self.news_repository.create(news)

        if unique_photo_ids:
            await self.news_repository.set_news_photos(
                news.id,
                photo_ids=unique_photo_ids,
                main_photo_id=main_photo_id,
                equestrian_id=equestrian_context.id,
            )

        return news

    async def update(
        self,
        news_id: UUID,
        data: NewsUpdateDto,
        *,
        equestrian_context: EquestrianContext,
        user: UserOutDto,
    ) -> News:
        await self._check_admin_permission(user=user)

        news = await self.news_repository.get_by_id(
            news_id, equestrian_id=equestrian_context.id
        )
        if news is None:
            raise ClientError("Новость не найдена")

        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            raise ClientError("Нет данных для обновления")

        self._validate_news_data(update_data, partial=True)

        snippet_explicitly_set = "snippet" in update_data

        for key, value in update_data.items():
            setattr(news, key, value)

        if snippet_explicitly_set and news.snippet is None:
            effective_content = update_data.get("content", news.content)
            news.snippet = self._generate_snippet(effective_content)

        return await self.news_repository.update(news)

    async def soft_delete(
        self, news_id: UUID, *, equestrian_context: EquestrianContext, user: UserOutDto
    ) -> None:
        await self._check_admin_permission(user=user)

        news = await self.news_repository.get_by_id(
            news_id, equestrian_id=equestrian_context.id
        )
        if news is None:
            raise ClientError("Новость не найдена")

        news.is_deleted = True
        news.deleted_at = datetime.now(timezone.utc)
        await self.news_repository.update(news)

    async def update_photos(
        self,
        news_id: UUID,
        data: NewsPhotosUpdateDto,
        *,
        equestrian_context: EquestrianContext,
    ) -> None:
        news = await self.news_repository.get_by_id(
            news_id, equestrian_id=equestrian_context.id
        )
        if news is None:
            raise ClientError("Новость не найдена")

        photo_ids = data.photo_ids
        main_photo_id = data.main
        if photo_ids is None and main_photo_id is None:
            raise ClientError("Нет данных для обновления")

        unique_photo_ids = None
        if photo_ids is not None:
            unique_photo_ids = await self._ensure_photos_exist(
                photo_ids, equestrian_context=equestrian_context
            )

        if main_photo_id is not None:
            if unique_photo_ids is not None:
                if main_photo_id not in unique_photo_ids:
                    raise ClientError(
                        "Главная фотография должна входить в список фотографий"
                    )
            else:
                photo = await self.photo_repository.get_by_id(
                    main_photo_id, equestrian_id=equestrian_context.id
                )
                if photo is None:
                    raise ClientError(f"Фотография с ID '{main_photo_id}' не найдена")
                relations = await self.news_repository.get_news_photos(
                    news.id, equestrian_id=equestrian_context.id
                )
                if main_photo_id not in {r.photo_id for r in relations}:
                    raise ClientError(
                        "Главная фотография должна входить в список фотографий"
                    )

        await self.news_repository.set_news_photos(
            news.id,
            photo_ids=unique_photo_ids,
            main_photo_id=main_photo_id,
            equestrian_id=equestrian_context.id,
        )

    async def get_cms_list(
        self,
        *,
        equestrian_context: EquestrianContext,
        user: UserOutDto,
        name: str | None = None,
        snippet: str | None = None,
        content: str | None = None,
        published_at_from: datetime | None = None,
        published_at_to: datetime | None = None,
        status: list[NewsStatus] | None = None,
        sort: str = "-published_at",
        limit: int = 25,
        offset: int = 0,
    ) -> tuple[list[News], int]:
        await self._check_admin_permission(user=user)
        return await self.news_repository.get_cms_filtered(
            equestrian_id=equestrian_context.id,
            name=name,
            snippet=snippet,
            content=content,
            published_at_from=published_at_from,
            published_at_to=published_at_to,
            status=status,
            sort=sort,
            limit=limit,
            offset=offset,
        )

    async def get_public_list(
        self,
        *,
        equestrian_context: EquestrianContext,
        limit: int = 25,
        offset: int = 0,
    ) -> tuple[list[News], int]:
        return await self.news_repository.get_public_filtered(
            equestrian_id=equestrian_context.id,
            limit=limit,
            offset=offset,
        )

    async def get_public_detail(
        self, news_id: UUID, *, equestrian_context: EquestrianContext
    ) -> News:
        news = await self.news_repository.get_public_by_id(
            news_id, equestrian_id=equestrian_context.id
        )
        if news is None:
            raise NotFoundError("Новость не найдена")
        return news

    async def _build_photos(
        self,
        news_item: News,
        *,
        equestrian_context: EquestrianContext,
    ) -> list[PhotoOutShortDto]:
        relations = await self.news_repository.get_news_photos(
            news_item.id, equestrian_id=equestrian_context.id
        )
        sorted_relations = sorted(relations, key=lambda r: not r.is_main)
        photo_ids = self._deduplicate_ids([r.photo_id for r in sorted_relations])
        photos_data = (
            await self.photo_repository.get_by_ids(
                photo_ids, equestrian_id=equestrian_context.id
            )
            if photo_ids
            else {}
        )
        return [
            PhotoOutShortDto(
                id=photo.id,
                is_main=relation.is_main,
                url=self.photo_url_builder.build(photo.path),
            )
            for relation in sorted_relations
            if (photo := photos_data.get(relation.photo_id)) is not None
        ]

    async def build_out_dto(
        self, news_item: News, *, equestrian_context: EquestrianContext
    ) -> NewsOutDto:
        photos = await self._build_photos(
            news_item, equestrian_context=equestrian_context
        )
        return NewsOutDto(
            id=news_item.id,
            name=news_item.name,
            snippet=news_item.snippet,
            content=news_item.content,
            published_at=news_item.published_at,
            is_deleted=news_item.is_deleted,
            deleted_at=news_item.deleted_at,
            photos=photos,
            created_at=news_item.created_at,
            updated_at=news_item.updated_at,
        )

    async def build_public_out_dto(
        self, news_item: News, *, equestrian_context: EquestrianContext
    ) -> NewsPublicOutDto:
        photos = await self._build_photos(
            news_item, equestrian_context=equestrian_context
        )
        return NewsPublicOutDto(
            id=news_item.id,
            name=news_item.name,
            snippet=news_item.snippet,
            published_at=news_item.published_at,
            photos=photos,
        )
