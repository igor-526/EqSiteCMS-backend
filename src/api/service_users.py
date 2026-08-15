from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from core.entities.base import PaginatedEntities
from core.schemas.users import UserOutDto
from core.services.users import UserService
from depends.services import (
    get_service_context,
    get_service_pagination_params,
    get_user_service,
)

router = APIRouter()


@router.get("/", response_model=PaginatedEntities[UserOutDto])
async def get_service_users(
    _service_context: Annotated[None, Depends(get_service_context)],
    pagination: Annotated[dict, Depends(get_service_pagination_params)],
    user_service: Annotated[UserService, Depends(get_user_service)],
    equestrian_ids: Annotated[list[UUID] | None, Query()] = None,
    equestrian_service_keys: Annotated[list[str] | None, Query()] = None,
    role: Annotated[list[str] | None, Query()] = None,
) -> PaginatedEntities[UserOutDto]:
    """
    Get paginated users for microservices.

    Requires X-Service-Key header for authentication.

    Filters (OR within each filter, AND between filters):
    - equestrian_ids: Filter by equestrian IDs
    - equestrian_service_keys: Filter by equestrian service keys
    - role: Filter by user scope names

    Note: Automatically excludes deleted (is_deleted=true) and blocked (is_blocked=true) users.
    """
    return await user_service.get_users_paginated(
        equestrian_ids=equestrian_ids,
        equestrian_service_keys=equestrian_service_keys,
        roles=role,
        limit=pagination["limit"],
        offset=pagination["offset"],
        exclude_deleted=True,
        exclude_blocked=True,
    )
