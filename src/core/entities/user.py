from uuid import UUID

from pydantic import Field

from .base import Entity, TimeStampMixin


class User(Entity, TimeStampMixin):
    """Пользователь системы."""

    username: str = Field(
        default=...,
        description="Уникальное имя пользователя",
        examples=["user123"],
    )
    password: str = Field(
        default=..., description="Хэш пароля пользователя", examples=["$2b$12$..."]
    )
    first_name: str | None = Field(
        default=None,
        description="Имя пользователя",
        examples=["Иван"],
    )
    last_name: str | None = Field(
        default=None,
        description="Фамилия пользователя",
        examples=["Иванов"],
    )
    middle_name: str | None = Field(
        default=None,
        description="Отчество пользователя",
        examples=["Иванович"],
    )


class UserScope(Entity):
    """Область доступа пользователя."""

    scope_name: str = Field(
        default=...,
        description="Уникальное название области доступа",
        examples=["ADMIN_USERS"],
    )
    scope_description: str = Field(
        default=...,
        description="Описание области доступа",
        examples=["Администрирование пользователей"],
    )


class UserScopeRelation(Entity):
    """Связь между пользователем и областью доступа."""

    user_id: UUID = Field(
        default=...,
        description="Идентификатор пользователя",
        examples=["123e4567-e89b-12d3-a456-426614174000"],
    )
    scope_id: UUID = Field(
        default=...,
        description="Идентификатор области доступа",
        examples=["123e4567-e89b-12d3-a456-426614174000"],
    )
