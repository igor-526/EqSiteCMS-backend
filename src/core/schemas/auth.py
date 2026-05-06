from pydantic import AliasChoices, BaseModel, Field

from core.schemas.baseschema import BaseSchema


class RegisterData(BaseSchema):
    username: str
    first_name: str
    last_name: str
    middle_name: str | None
    password: str


class LoginData(BaseSchema):
    username: str = Field(validation_alias=AliasChoices("username", "login"))
    password: str


class AuthTokens(BaseModel):
    access_token: str
    refresh_token: str
