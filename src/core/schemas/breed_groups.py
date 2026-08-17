from datetime import datetime
from uuid import UUID

from core.schemas.baseschema import BaseSchema


class BreedGroupOutDto(BaseSchema):
    id: UUID
    name: str
    slug: str
    created_at: datetime
    updated_at: datetime | None


class BreedGroupOutWithPageDataDto(BreedGroupOutDto):
    page_data: str


class BreedGroupCreateDto(BaseSchema):
    name: str
    slug: str | None = None
    page_data: str | None = None


class BreedGroupUpdateDto(BaseSchema):
    name: str | None = None
    slug: str | None = None
    page_data: str | None = None
