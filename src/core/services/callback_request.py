import uuid
from core.entities.equestrian import EquestrianContext

from core.protocols import CallbackRequestEventPublisherProtocol
from core.schemas import (
    CallbackRequestedData,
    CallbackRequestCreateDto,
    CallbackRequestOutDto,
)


class CallbackRequestService:
    def __init__(
        self, callback_request_event_publisher: CallbackRequestEventPublisherProtocol
    ):
        self.callback_request_event_publisher = callback_request_event_publisher

    async def create(
        self,
        *,
        data: CallbackRequestCreateDto,
        equestrian_context: EquestrianContext,
    ) -> CallbackRequestOutDto:
        """Создать заявку на обратный звонок."""
        event = CallbackRequestedData(
            callback_request_id=uuid.uuid4(),
            name=data.name,
            comment=data.comment,
            phone=data.phone,
        )
        event_id = await self.callback_request_event_publisher.publish(
            payload=event, equestrian_id=equestrian_context.id
        )
        return CallbackRequestOutDto(
            id=event_id,
            name=data.name,
            comment=data.comment,
            phone=data.phone,
        )
