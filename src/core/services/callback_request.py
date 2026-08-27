import re
from datetime import datetime
from uuid import UUID

from core.entities.callback_request import CallbackRequest
from core.entities.equestrian import EquestrianContext
from core.exceptions.base import ClientError, NotFoundError, UnprocessableEntityError
from core.protocols import CallbackRequestEventPublisherProtocol
from core.protocols.repositories.callback_request_repository import (
    CallbackRequestRepositoryProtocol,
)
from core.schemas.callbackrequest import (
    CallbackRequestCreateDto,
    CallbackRequestOutDto,
    CallbackRequestPageOutDto,
    CallbackRequestStatusOutDto,
)
from core.schemas.messaging import CallbackRequestedData
from core.schemas.users import UserOutDto

ALLOWED_ADMIN_ROLES = {"ADMIN", "SUPERUSER"}
MAX_REGEX_LENGTH = 128


class CallbackRequestPublishError(ClientError):
    pass


def _dto(entity: CallbackRequest) -> CallbackRequestOutDto:
    return CallbackRequestOutDto.model_validate(
        entity.model_dump(exclude={"equestrian_id"})
    )


def _require_admin(user: UserOutDto) -> None:
    if not {scope.scope_name for scope in user.scopes}.intersection(
        ALLOWED_ADMIN_ROLES
    ):
        from core.exceptions.auth import ForbiddenError

        raise ForbiddenError("Недостаточно прав")


def _safe_pattern(value: str | None, *, phone: bool = False) -> str | None:
    if value is None or not value.strip():
        return None
    pattern = value.strip()
    if len(pattern) > MAX_REGEX_LENGTH:
        raise UnprocessableEntityError("Регулярное выражение слишком длинное")
    if phone and re.search(r"[A-Za-zА-Яа-яЁё]", pattern):
        raise UnprocessableEntityError("Фильтр телефона не может содержать буквы")
    if re.search(r"\(\?[=!<]|\\[1-9]|\{\d{4,}", pattern) or re.search(
        r"\((?:[^()]|\\.)*[*+](?:[^()]|\\.)*\)\s*(?:[*+]|\{)", pattern
    ):
        raise UnprocessableEntityError("Опасное регулярное выражение")
    try:
        re.compile(pattern)
    except re.error as exc:
        raise UnprocessableEntityError("Невалидное регулярное выражение") from exc
    return pattern


class CallbackRequestService:
    def __init__(
        self,
        callback_request_event_publisher: CallbackRequestEventPublisherProtocol,
        repository: CallbackRequestRepositoryProtocol,
    ):
        self.callback_request_event_publisher = callback_request_event_publisher
        self.repository = repository

    async def create(
        self, *, data: CallbackRequestCreateDto, equestrian_context: EquestrianContext
    ) -> CallbackRequestOutDto:
        entity = CallbackRequest(
            equestrian_id=equestrian_context.id,
            name=data.name,
            comment=data.comment,
            phone=data.phone,
        )
        await self.repository.create_and_commit(entity)
        event = CallbackRequestedData(
            equestrian_id=entity.equestrian_id,
            callback_request_id=entity.id,
            name=entity.name,
            comment=entity.comment,
            phone=entity.phone,
        )
        try:
            await self.callback_request_event_publisher.publish(payload=event)
        except Exception as exc:
            raise CallbackRequestPublishError(
                "Заявка сохранена, но уведомление временно недоступно"
            ) from exc
        return _dto(entity)

    async def statuses(self) -> list[CallbackRequestStatusOutDto]:
        return [
            CallbackRequestStatusOutDto.model_validate(item)
            for item in await self.repository.get_statuses()
        ]

    async def list(
        self,
        *,
        user: UserOutDto,
        statuses: list[int] | None,
        spam: list[bool] | None,
        created_from: datetime | None,
        created_to: datetime | None,
        name: str | None,
        phone: str | None,
        comment: str | None,
        sort_by: str,
        direction: str,
        limit: int,
        offset: int,
    ) -> CallbackRequestPageOutDto:
        _require_admin(user)
        if created_from and created_to and created_from > created_to:
            raise ClientError("Некорректный диапазон дат")
        items, total = await self.repository.list_page(
            equestrian_id=user.equestrian_id,
            statuses=statuses,
            spam=spam,
            created_from=created_from,
            created_to=created_to,
            name=_safe_pattern(name),
            phone=_safe_pattern(phone, phone=True),
            comment=_safe_pattern(comment),
            sort_by=sort_by,
            direction=direction,
            limit=limit,
            offset=offset,
        )
        return CallbackRequestPageOutDto(
            items=[_dto(item) for item in items],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def detail(self, *, id: UUID, user: UserOutDto) -> CallbackRequestOutDto:
        _require_admin(user)
        entity = await self.repository.get_by_id(id, equestrian_id=user.equestrian_id)
        if entity is None:
            raise NotFoundError("Заявка не найдена")
        return _dto(entity)

    async def set_status(
        self, *, id: UUID, status: int, user: UserOutDto | None = None
    ) -> CallbackRequestOutDto:
        if user is not None:
            _require_admin(user)
        if not await self.repository.status_exists(status):
            raise ClientError("Неизвестный статус")
        entity = await self.repository.set_status(
            id=id,
            equestrian_id=None if user is None else user.equestrian_id,
            status=status,
        )
        if entity is None:
            raise NotFoundError("Заявка не найдена")
        return _dto(entity)

    async def set_spam(
        self, *, id: UUID, is_spam: bool, user: UserOutDto | None = None
    ) -> CallbackRequestOutDto:
        if user is not None:
            _require_admin(user)
        entity = await self.repository.set_spam(
            id=id,
            equestrian_id=None if user is None else user.equestrian_id,
            is_spam=is_spam,
        )
        if entity is None:
            raise NotFoundError("Заявка не найдена")
        return _dto(entity)

    async def confirm_delivery(
        self, *, id: UUID, delivered: bool
    ) -> CallbackRequestOutDto:
        if delivered is not True:
            raise ClientError("Подтверждение доставки может быть только true")
        entity = await self.repository.set_delivery(id=id, notifications_delivered=True)
        if entity is None:
            raise NotFoundError("Заявка не найдена")
        return _dto(entity)
