from core.exceptions.base import ClientError
from core.protocols.repositories.equestrian_repository import (
    EquestrianRepositoryProtocol,
)
from core.protocols.repositories.user_repository import UserRepositoryProtocol
from core.protocols.security import SecurityProtocol
from core.schemas.users import (
    ChangePasswordIn,
    UpdateProfileIn,
    UserOutDto,
    UserProfileDto,
)


class UserService:
    def __init__(
        self,
        repository: UserRepositoryProtocol,
        equestrian_repository: EquestrianRepositoryProtocol | None = None,
        security: SecurityProtocol | None = None,
    ) -> None:
        self.repository = repository
        self.equestrian_repository = equestrian_repository
        self.security = security

    async def get_users(
        self, *, limit: int | None = None, offset: int | None = None
    ) -> list[UserOutDto]:
        users = await self.repository.get_all(limit=limit, offset=offset)
        return [UserOutDto.model_validate(user.model_dump()) for user in users]

    async def get_my_profile(self, current_user: UserOutDto) -> UserProfileDto:
        equestrian_name: str | None = None
        if self.equestrian_repository is not None:
            try:
                equestrian = await self.equestrian_repository.get_by_id(
                    current_user.equestrian_id
                )
                if equestrian is not None:
                    equestrian_name = equestrian.name
            except Exception:
                equestrian_name = None

        return UserProfileDto(
            id=current_user.id,
            equestrian_id=current_user.equestrian_id,
            equestrian_name=equestrian_name,
            username=current_user.username,
            first_name=current_user.first_name,
            last_name=current_user.last_name,
            middle_name=current_user.middle_name,
            created_at=current_user.created_at,
            updated_at=current_user.updated_at,
            scopes=current_user.scopes,
        )

    async def update_my_profile(
        self, current_user: UserOutDto, data: UpdateProfileIn
    ) -> UserProfileDto:
        user = await self.repository.get_by_id(current_user.id)
        if user is None:
            raise ClientError("Пользователь не найден")

        user.first_name = data.first_name
        user.last_name = data.last_name
        user.middle_name = data.middle_name

        await self.repository.update(user)

        updated_user = UserOutDto(
            id=current_user.id,
            equestrian_id=current_user.equestrian_id,
            username=current_user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            middle_name=user.middle_name,
            created_at=current_user.created_at,
            updated_at=user.updated_at,
            scopes=current_user.scopes,
        )
        return await self.get_my_profile(updated_user)

    async def change_my_password(
        self, current_user: UserOutDto, data: ChangePasswordIn
    ) -> None:
        if self.security is None:
            raise ClientError("Сервис безопасности недоступен")

        user = await self.repository.get_by_id(current_user.id)
        if user is None:
            raise ClientError("Пользователь не найден")

        if not self.security.verify_password(data.current_password, user.password):
            raise ClientError("Неверный текущий пароль")

        user.password = self.security.hash_password(data.new_password)
        await self.repository.update(user)
