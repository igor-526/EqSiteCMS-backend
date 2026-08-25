from datetime import datetime
from typing import Protocol
from uuid import UUID

from core.entities.callback_request import CallbackRequest, CallbackRequestStatus


class CallbackRequestRepositoryProtocol(Protocol):
    async def create_and_commit(self, entity: CallbackRequest) -> CallbackRequest: ...

    async def get_statuses(self) -> list[CallbackRequestStatus]: ...

    async def status_exists(self, status: int) -> bool: ...

    async def get_by_id(
        self, id: UUID, *, equestrian_id: UUID
    ) -> CallbackRequest | None: ...

    async def list_page(
        self,
        *,
        equestrian_id: UUID,
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
    ) -> tuple[list[CallbackRequest], int]: ...

    async def set_status(
        self, *, id: UUID, equestrian_id: UUID | None, status: int
    ) -> CallbackRequest | None: ...

    async def set_spam(
        self, *, id: UUID, equestrian_id: UUID | None, is_spam: bool
    ) -> CallbackRequest | None: ...

    async def set_delivery(
        self, *, id: UUID, notifications_delivered: bool
    ) -> CallbackRequest | None: ...
