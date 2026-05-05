from core.entities.user import User
from core.protocols.repositories.user_repository import UserRepositoryProtocol


class UserService:
    def __init__(self, repository: UserRepositoryProtocol) -> None:
        self.repository = repository

    async def get_users(self) -> list[User]:
        return await self.repository.get_all()
