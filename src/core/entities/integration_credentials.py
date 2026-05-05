from uuid import UUID

from pydantic import Field

from .base import Entity, TimeStampMixin


class IntegrationCredentials(Entity, TimeStampMixin):
    """Доступы для интеграции пользователя."""

    # TODO: Потом заменить на более безопасное хранение чем значением в бд.
    value: str = Field(
        default=...,
        description="Уникальное значение токена или ключа",
    )
    user_id: UUID = Field(
        default=..., description="Идентификатор пользователя (User.id)"
    )
