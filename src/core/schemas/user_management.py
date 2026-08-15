from datetime import datetime
from uuid import UUID

from pydantic import Field, model_validator

from core.entities.user import UserScope
from core.schemas.baseschema import BaseSchema


class UserManagementOutDto(BaseSchema):
    """DTO для отображения пользователя в списке управления."""

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


class CreateUserIn(BaseSchema):
    """Схема для создания пользователя."""

    equestrian_id: UUID = Field(description="Идентификатор конюшни")
    username: str = Field(min_length=3, max_length=63, description="Имя пользователя")
    password: str = Field(min_length=8, description="Пароль")
    confirm_password: str = Field(description="Подтверждение пароля")
    first_name: str | None = Field(default=None, max_length=63, description="Имя")
    last_name: str | None = Field(default=None, max_length=63, description="Фамилия")
    middle_name: str | None = Field(default=None, max_length=63, description="Отчество")
    scope_ids: list[UUID] = Field(
        default_factory=list, description="Идентификаторы ролей"
    )

    @model_validator(mode="after")
    def passwords_match(self) -> "CreateUserIn":
        if self.password != self.confirm_password:
            raise ValueError("Пароли не совпадают")
        return self

    @model_validator(mode="after")
    def validate_password_complexity(self) -> "CreateUserIn":
        password = self.password
        if len(password) < 8:
            raise ValueError("Пароль должен содержать минимум 8 символов")
        if not any(c.isupper() for c in password):
            raise ValueError("Пароль должен содержать хотя бы одну заглавную букву")
        if not any(c.isdigit() for c in password):
            raise ValueError("Пароль должен содержать хотя бы одну цифру")
        return self


class UpdateUserIn(BaseSchema):
    """Схема для обновления пользователя."""

    username: str | None = Field(
        default=None, min_length=3, max_length=63, description="Имя пользователя"
    )
    first_name: str | None = Field(default=None, max_length=63, description="Имя")
    last_name: str | None = Field(default=None, max_length=63, description="Фамилия")
    middle_name: str | None = Field(default=None, max_length=63, description="Отчество")
    scope_ids: list[UUID] | None = Field(
        default=None, description="Идентификаторы ролей"
    )


class ChangePasswordByAdminIn(BaseSchema):
    """Схема для смены пароля администратором."""

    new_password: str = Field(min_length=8, description="Новый пароль")
    confirm_password: str = Field(description="Подтверждение пароля")

    @model_validator(mode="after")
    def passwords_match(self) -> "ChangePasswordByAdminIn":
        if self.new_password != self.confirm_password:
            raise ValueError("Пароли не совпадают")
        return self

    @model_validator(mode="after")
    def validate_password_complexity(self) -> "ChangePasswordByAdminIn":
        password = self.new_password
        if len(password) < 8:
            raise ValueError("Пароль должен содержать минимум 8 символов")
        if not any(c.isupper() for c in password):
            raise ValueError("Пароль должен содержать хотя бы одну заглавную букву")
        if not any(c.isdigit() for c in password):
            raise ValueError("Пароль должен содержать хотя бы одну цифру")
        return self


class RoleOutDto(BaseSchema):
    """DTO для отображения роли."""

    id: UUID
    scope_name: str
    scope_description: str | None = None


class UserManagementFilters(BaseSchema):
    """Фильтры для списка пользователей."""

    username: str | None = Field(default=None, description="Фильтр по username (regex)")
    first_name: str | None = Field(default=None, description="Фильтр по имени (regex)")
    last_name: str | None = Field(default=None, description="Фильтр по фамилии (regex)")
    middle_name: str | None = Field(
        default=None, description="Фильтр по отчеству (regex)"
    )
    scope_ids: list[UUID] | None = Field(
        default=None, description="Фильтр по ролям (ИЛИ)"
    )
    search: str | None = Field(default=None, description="Поиск по ФИО (ИЛИ)")
    is_blocked: bool | None = Field(default=None, description="Фильтр по блокировке")
