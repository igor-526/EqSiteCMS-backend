from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import Field

from .base import Entity, SoftDeleteMixin, TimeStampMixin


class NewsStatus(str, Enum):
    PUBLISHED = "published"
    SCHEDULED = "scheduled"
    DELETED = "deleted"


class NewsSortField(str, Enum):
    NAME_ASC = "name"
    NAME_DESC = "-name"
    PUBLISHED_AT_ASC = "published_at"
    PUBLISHED_AT_DESC = "-published_at"
    STATUS_ASC = "status"
    STATUS_DESC = "-status"
    CREATED_AT_ASC = "created_at"
    CREATED_AT_DESC = "-created_at"


class News(Entity, TimeStampMixin, SoftDeleteMixin):
    equestrian_id: UUID = Field(default=...)
    name: str = Field(default=...)
    snippet: str | None = Field(default=None)
    content: str = Field(default="")
    published_at: datetime = Field(default=...)


class NewsPhoto(Entity):
    news_id: UUID = Field(default=...)
    photo_id: UUID = Field(default=...)
    is_main: bool = Field(default=False)
