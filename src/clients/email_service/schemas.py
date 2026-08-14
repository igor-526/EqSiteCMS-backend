from uuid import UUID

from pydantic import BaseModel


class EmailCreateRequest(BaseModel):
    user_id: UUID
    email: str


class EmailUpdateRequest(BaseModel):
    user_id: UUID
    email: str


class EmailConfirmRequest(BaseModel):
    code: str


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
