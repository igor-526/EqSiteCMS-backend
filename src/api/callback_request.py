from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from core.entities.equestrian import EquestrianContext
from core.schemas.callbackrequest import (
    CallbackRequestCreateDto,
    CallbackRequestDeliveryInDto,
    CallbackRequestOutDto,
    CallbackRequestPageOutDto,
    CallbackRequestSortField,
    CallbackRequestSpamInDto,
    CallbackRequestStatusInDto,
    CallbackRequestStatusOutDto,
    SortDirection,
)
from core.schemas.users import UserOutDto
from core.services.callback_request import CallbackRequestService
from depends.services import (
    get_callback_request_service,
    get_current_user,
    get_read_equestrian_context,
    get_service_context,
)

router = APIRouter()
service_router = APIRouter()


@router.post(
    "", response_model=CallbackRequestOutDto, status_code=status.HTTP_201_CREATED
)
async def create_callback_request(
    data: CallbackRequestCreateDto,
    equestrian_context: Annotated[
        EquestrianContext, Depends(get_read_equestrian_context)
    ],
    service: Annotated[CallbackRequestService, Depends(get_callback_request_service)],
) -> CallbackRequestOutDto:
    return await service.create(data=data, equestrian_context=equestrian_context)


@router.get("/statuses", response_model=list[CallbackRequestStatusOutDto])
async def get_callback_request_statuses(
    service: Annotated[CallbackRequestService, Depends(get_callback_request_service)],
) -> list[CallbackRequestStatusOutDto]:
    return await service.statuses()


@router.get("", response_model=CallbackRequestPageOutDto)
async def list_callback_requests(
    service: Annotated[CallbackRequestService, Depends(get_callback_request_service)],
    user: Annotated[UserOutDto, Depends(get_current_user)],
    statuses: Annotated[list[int] | None, Query(alias="status")] = None,
    spam: Annotated[list[bool] | None, Query(alias="is_spam")] = None,
    created_from: Annotated[datetime | None, Query(alias="created_at_from")] = None,
    created_to: Annotated[datetime | None, Query(alias="created_at_to")] = None,
    name: Annotated[str | None, Query(max_length=128)] = None,
    phone: Annotated[str | None, Query(max_length=128)] = None,
    comment: Annotated[str | None, Query(max_length=128)] = None,
    sort_by: CallbackRequestSortField = CallbackRequestSortField.STATUS,
    direction: SortDirection = SortDirection.ASC,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CallbackRequestPageOutDto:
    return await service.list(
        user=user,
        statuses=statuses,
        spam=spam,
        created_from=created_from,
        created_to=created_to,
        name=name,
        phone=phone,
        comment=comment,
        sort_by=sort_by.value,
        direction=direction.value,
        limit=limit,
        offset=offset,
    )


@router.get("/{id}", response_model=CallbackRequestOutDto)
async def get_callback_request(
    id: UUID,
    service: Annotated[CallbackRequestService, Depends(get_callback_request_service)],
    user: Annotated[UserOutDto, Depends(get_current_user)],
) -> CallbackRequestOutDto:
    return await service.detail(id=id, user=user)


@router.patch("/{id}/status", response_model=CallbackRequestOutDto)
async def update_callback_request_status(
    id: UUID,
    data: CallbackRequestStatusInDto,
    service: Annotated[CallbackRequestService, Depends(get_callback_request_service)],
    user: Annotated[UserOutDto, Depends(get_current_user)],
) -> CallbackRequestOutDto:
    return await service.set_status(id=id, status=data.status, user=user)


@router.patch("/{id}/spam", response_model=CallbackRequestOutDto)
async def update_callback_request_spam(
    id: UUID,
    data: CallbackRequestSpamInDto,
    service: Annotated[CallbackRequestService, Depends(get_callback_request_service)],
    user: Annotated[UserOutDto, Depends(get_current_user)],
) -> CallbackRequestOutDto:
    return await service.set_spam(id=id, is_spam=data.is_spam, user=user)


@service_router.patch(
    "/{id}/status",
    response_model=CallbackRequestOutDto,
    dependencies=[Depends(get_service_context)],
)
async def service_update_status(
    id: UUID,
    data: CallbackRequestStatusInDto,
    service: Annotated[CallbackRequestService, Depends(get_callback_request_service)],
) -> CallbackRequestOutDto:
    return await service.set_status(id=id, status=data.status)


@service_router.patch(
    "/{id}/spam",
    response_model=CallbackRequestOutDto,
    dependencies=[Depends(get_service_context)],
)
async def service_update_spam(
    id: UUID,
    data: CallbackRequestSpamInDto,
    service: Annotated[CallbackRequestService, Depends(get_callback_request_service)],
) -> CallbackRequestOutDto:
    return await service.set_spam(id=id, is_spam=data.is_spam)


@service_router.patch(
    "/{id}/notifications-delivered",
    response_model=CallbackRequestOutDto,
    dependencies=[Depends(get_service_context)],
)
async def service_confirm_delivery(
    id: UUID,
    data: CallbackRequestDeliveryInDto,
    service: Annotated[CallbackRequestService, Depends(get_callback_request_service)],
) -> CallbackRequestOutDto:
    return await service.confirm_delivery(id=id, delivered=data.notifications_delivered)
