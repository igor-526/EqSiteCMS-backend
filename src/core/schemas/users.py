from datetime import datetime
from uuid import UUID

from pydantic import Field

from core.entities.user import UserScope
from core.schemas.baseschema import BaseSchema


class UserOutDto(BaseSchema):
    id: UUID
    username: str
    first_name: str | None = None
    last_name: str | None = None
    middle_name: str | None = None
    created_at: datetime
    updated_at: datetime | None = None
    scopes: list[UserScope] = Field(
        default_factory=list, description="Группы доступа пользователя"
    )
