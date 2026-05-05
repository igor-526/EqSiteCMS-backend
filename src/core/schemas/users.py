from pydantic import Field

from core.entities import User as UserEntity
from core.entities.user import UserScope
from core.schemas.baseschema import BaseSchema


class UserOutDto(UserEntity, BaseSchema):
    password: str = Field(exclude=True)
    scopes: list[UserScope] = Field(
        default_factory=list, description="Группы доступа пользователя"
    )
