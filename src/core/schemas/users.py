from datetime import datetime
from uuid import UUID

from pydantic import Field, model_validator

from core.entities.user import UserScope
from core.schemas.baseschema import BaseSchema


class UserOutDto(BaseSchema):
    id: UUID
    equestrian_id: UUID
    username: str
    first_name: str | None = None
    last_name: str | None = None
    middle_name: str | None = None
    created_at: datetime
    updated_at: datetime | None = None
    is_deleted: bool = False
    deleted_at: datetime | None = None
    is_blocked: bool = False
    scopes: list[UserScope] = Field(
        default_factory=list, description="Группы доступа пользователя"
    )


class UserProfileDto(BaseSchema):
    id: UUID
    equestrian_id: UUID
    equestrian_name: str | None = None
    username: str
    first_name: str | None = None
    last_name: str | None = None
    middle_name: str | None = None
    created_at: datetime
    updated_at: datetime | None = None
    is_blocked: bool = False
    scopes: list[UserScope] = Field(default_factory=list)


class UpdateProfileIn(BaseSchema):
    first_name: str | None = Field(default=None, max_length=63)
    last_name: str | None = Field(default=None, max_length=63)
    middle_name: str | None = Field(default=None, max_length=63)


class ChangePasswordIn(BaseSchema):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)
    confirm_new_password: str

    @model_validator(mode="after")
    def passwords_match(self) -> "ChangePasswordIn":
        if self.new_password != self.confirm_new_password:
            raise ValueError("Пароли не совпадают")
        return self
