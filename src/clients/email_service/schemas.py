from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class EmailRequestBase(BaseModel):
    @field_validator("email", check_fields=False)
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip()
        local, separator, domain = normalized.rpartition("@")
        if not separator or not local or "." not in domain or domain.startswith("."):
            raise ValueError("Некорректный email")
        return normalized


class EmailCreateRequest(EmailRequestBase):
    user_id: UUID
    email: str


class EmailUpdateRequest(EmailRequestBase):
    user_id: UUID
    email: str


class EmailConfirmRequest(BaseModel):
    code: str = Field(min_length=1)


class EmailSendConfirmationRequest(BaseModel):
    user_id: UUID


class EmailResponse(BaseModel):
    id: UUID
    user_id: UUID
    email: str
    approved: bool


class ConfirmationResponse(BaseModel):
    status: str
    user_email_id: str
