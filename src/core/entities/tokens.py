from uuid import UUID

from pydantic import Field

from .base import Entity, TimeStampMixin


class Token(Entity, TimeStampMixin):
    """Токен доступа пользователя."""

    value: str = Field(
        default=...,
        description="Значение токена",
        examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."],
    )
    user_id: UUID = Field(
        default=...,
        description="Идентификатор пользователя",
        examples=["123e4567-e89b-12d3-a456-426614174000"],
    )
