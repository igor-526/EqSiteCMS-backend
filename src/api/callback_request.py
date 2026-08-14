import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from core.entities.equestrian import EquestrianContext
from core.protocols.publishers import CallbackRequestEventPublisherProtocol
from core.schemas import CallbackRequestedData
from depends.publishers import (
    get_callback_request_event_publisher,
)
from depends.services import (
    get_read_equestrian_context,
)

router = APIRouter()


@router.post(
    "",
    response_model=dict,
    description="Создать заявку на обратный звонок",
)
async def create_callback_request(
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_read_equestrian_context)
    ],
    callback_request_event_publisher: Annotated[
        CallbackRequestEventPublisherProtocol,
        Depends(get_callback_request_event_publisher),
    ],
) -> dict:
    event = CallbackRequestedData(
        callback_request_id=uuid.uuid4(),
        name="Игорь",
        comment="Прошу перезвонить",
        phone="+79117488008",
    )
    event_id = await callback_request_event_publisher.publish(
        payload=event, equestrian_id=equestrian_context.id
    )
    return {"status": "ok", "event_id": str(event_id)}
