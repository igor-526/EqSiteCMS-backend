from typing import Protocol
from uuid import UUID

from core.schemas import CallbackRequestedData


class CallbackRequestEventPublisherProtocol(Protocol):
    async def publish(
        self, *, payload: CallbackRequestedData, equestrian_id: UUID
    ) -> UUID: ...
