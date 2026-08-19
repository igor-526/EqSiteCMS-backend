from typing import Annotated

from fastapi import APIRouter, Depends

from core.entities.equestrian import EquestrianContext
from core.schemas import CallbackRequestOutDto, CallbackRequestCreateDto
from core.services.callback_request import CallbackRequestService
from depends.services import (
    get_callback_request_service,
    get_read_equestrian_context,
)

router = APIRouter()


@router.post(
    "",
    response_model=CallbackRequestOutDto,
    description="Создать заявку на обратный звонок",
)
async def create_callback_request(
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_read_equestrian_context)
    ],
    callback_request_service: Annotated[
        CallbackRequestService, Depends(get_callback_request_service)
    ],
    data: CallbackRequestCreateDto,
) -> CallbackRequestOutDto:
    return await callback_request_service.create(
        data=data,
        equestrian_context=equestrian_context,
    )
