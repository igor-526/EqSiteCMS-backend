from core.protocols.repositories.user_repository import UserRepositoryProtocol
from core.schemas.users import UserOutDto


class UserService:
    def __init__(self, repository: UserRepositoryProtocol) -> None:
        self.repository = repository

    async def get_users(
        self, *, limit: int | None = None, offset: int | None = None
    ) -> list[UserOutDto]:
        users = await self.repository.get_all(limit=limit, offset=offset)
        return [UserOutDto.model_validate(user.model_dump()) for user in users]
