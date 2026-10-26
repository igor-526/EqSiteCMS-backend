from datetime import datetime
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

EntityDto = TypeVar("EntityDto")


class SearchQueryOutDto(BaseModel):
    id: UUID
    query: str
    created_at: datetime


class PageOutDto(BaseModel):
    id: UUID
    page: str
    created_at: datetime


class BlacklistItemInDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str


class BlacklistItemOutDto(BaseModel):
    id: UUID
    value: str
    created_at: datetime


class PaginatedEntities(BaseModel, Generic[EntityDto]):
    items: list[EntityDto]
    total: int = Field(ge=0)
