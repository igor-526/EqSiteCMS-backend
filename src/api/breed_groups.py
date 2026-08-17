from typing import Annotated

from fastapi import APIRouter, Depends, Query

from core.entities.base import PaginatedEntities
from core.entities.equestrian import EquestrianContext
from core.protocols.repositories.breed_group_repository import BreedGroupSort
from core.schemas.breed_groups import (
    BreedGroupCreateDto,
    BreedGroupOutDto,
    BreedGroupOutWithPageDataDto,
    BreedGroupUpdateDto,
)
from core.schemas.users import UserOutDto
from core.services.breed_groups import BreedGroupService
from depends.services import (
    get_breed_group_service,
    get_current_user,
    get_protected_equestrian_context,
    get_read_equestrian_context,
)

router = APIRouter(prefix="/horses/breed-groups", tags=["Horse Breed Groups"])


@router.get("", response_model=PaginatedEntities[BreedGroupOutDto])
async def list_breed_groups(
    service: Annotated[BreedGroupService, Depends(get_breed_group_service)],
    context: Annotated[EquestrianContext, Depends(get_read_equestrian_context)],
    name: str | None = None,
    slug: str | None = None,
    page_data: str | None = None,
    sort: list[BreedGroupSort] | None = Query(None),
    limit: int | None = None,
    offset: int | None = None,
) -> PaginatedEntities[BreedGroupOutDto]:
    entities, total = await service.list(
        equestrian_context=context,
        name=name,
        slug=slug,
        page_data=page_data,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    return PaginatedEntities(
        items=[BreedGroupOutDto.model_validate(item) for item in entities], total=total
    )


@router.get(
    "/{slug_or_id}", response_model=BreedGroupOutDto | BreedGroupOutWithPageDataDto
)
async def get_breed_group(
    slug_or_id: str,
    service: Annotated[BreedGroupService, Depends(get_breed_group_service)],
    context: Annotated[EquestrianContext, Depends(get_read_equestrian_context)],
    page_data: bool = False,
) -> BreedGroupOutDto | BreedGroupOutWithPageDataDto:
    entity = await service.get(slug_or_id, equestrian_context=context)
    dto = BreedGroupOutWithPageDataDto if page_data else BreedGroupOutDto
    return dto.model_validate(entity)


@router.post("", response_model=BreedGroupOutDto)
async def create_breed_group(
    data: BreedGroupCreateDto,
    service: Annotated[BreedGroupService, Depends(get_breed_group_service)],
    user: Annotated[UserOutDto, Depends(get_current_user)],
    context: Annotated[EquestrianContext, Depends(get_protected_equestrian_context)],
) -> BreedGroupOutDto:
    return BreedGroupOutDto.model_validate(
        await service.create(data, equestrian_context=context, user=user)
    )


@router.patch("/{slug_or_id}", response_model=BreedGroupOutDto)
async def update_breed_group(
    slug_or_id: str,
    data: BreedGroupUpdateDto,
    service: Annotated[BreedGroupService, Depends(get_breed_group_service)],
    user: Annotated[UserOutDto, Depends(get_current_user)],
    context: Annotated[EquestrianContext, Depends(get_protected_equestrian_context)],
) -> BreedGroupOutDto:
    return BreedGroupOutDto.model_validate(
        await service.update(slug_or_id, data, equestrian_context=context, user=user)
    )


@router.delete("/{slug_or_id}", status_code=204)
async def delete_breed_group(
    slug_or_id: str,
    service: Annotated[BreedGroupService, Depends(get_breed_group_service)],
    user: Annotated[UserOutDto, Depends(get_current_user)],
    context: Annotated[EquestrianContext, Depends(get_protected_equestrian_context)],
) -> None:
    await service.delete(slug_or_id, equestrian_context=context, user=user)
