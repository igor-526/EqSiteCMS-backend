from uuid import UUID

from clients.email_service.schemas import EmailResponse
from core.exceptions.auth import ForbiddenError
from core.exceptions.base import NotFoundError
from core.protocols.email_service import EmailServiceClientProtocol
from core.schemas.users import UserOutDto


class EmailProxyService:
    def __init__(self, client: EmailServiceClientProtocol) -> None:
        self._client = client

    @staticmethod
    def _require_owner(*, user_id: UUID, actor: UserOutDto) -> None:
        if actor.id != user_id:
            raise ForbiddenError("Управлять email может только его владелец")

    async def create(self, *, user_id: UUID, email: str, actor: UserOutDto) -> dict:
        self._require_owner(user_id=user_id, actor=actor)
        return await self._client.create_email(user_id=user_id, email=email)

    async def get_mine(self, *, actor: UserOutDto) -> EmailResponse:
        email = await self._client.get_email(user_id=actor.id)
        if email is None:
            raise NotFoundError("Email не найден")
        return email

    async def update(self, *, user_id: UUID, email: str, actor: UserOutDto) -> dict:
        self._require_owner(user_id=user_id, actor=actor)
        return await self._client.update_email(user_id=user_id, email=email)

    async def delete(self, *, user_id: UUID, actor: UserOutDto) -> None:
        self._require_owner(user_id=user_id, actor=actor)
        await self._client.delete_email(user_id=user_id)

    async def confirm(self, *, code: str) -> dict:
        return await self._client.confirm_email(code=code)

    async def send_confirmation(self, *, user_id: UUID) -> dict:
        return await self._client.send_confirmation(user_id=user_id)
