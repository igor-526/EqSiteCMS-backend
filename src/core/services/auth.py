from core.entities.user import User
from core.exceptions.auth import InvalidCredentials, UserAlreadyExists
from core.protocols.repositories.user_repository import UserRepositoryProtocol
from core.protocols.security import SecurityProtocol
from core.schemas.auth import AuthTokens, LoginData, RegisterData
from core.schemas.users import UserOutDto


class AuthService:
    def __init__(
        self, user_repository: UserRepositoryProtocol, security: SecurityProtocol
    ):
        self.user_repository = user_repository
        self.security = security

    async def get_current_user(self, token: str) -> UserOutDto:
        payload = self.security.decode_token(token)
        if not payload:
            raise InvalidCredentials("Недействительный или просроченный токен")

        username = payload["sub"]
        if not username:
            raise InvalidCredentials("Некорректное содержимое токена")

        user = await self.user_repository.get_by_username(username=username)
        if not user:
            raise InvalidCredentials("Пользователь не найден")

        # Получаем группы доступа
        scopes = await self.user_repository.get_user_scopes(user.id)

        user_dict = user.model_dump()
        user_dict["scopes"] = scopes

        return UserOutDto.model_validate(user_dict)

    async def register(self, data: RegisterData) -> UserOutDto:
        if await self.user_repository.get_by_username(username=data.username):
            raise UserAlreadyExists(
                f"Пользователь с именем {data.username} уже существует"
            )
        # Password validation here if needed
        data.password = self.security.hash_password(data.password)
        user = User(**data.model_dump())
        user = await self.user_repository.create(user)
        # Optionally, send a welcome email here
        return UserOutDto.model_validate(user)

    async def login(self, data: LoginData) -> AuthTokens:
        user = await self.user_repository.get_by_username(username=data.username)
        if not user or not self.security.verify_password(data.password, user.password):
            raise InvalidCredentials("Неверное имя пользователя или пароль")

        access_token = self.security.create_access_token(sub=user.username)
        refresh_token = self.security.create_refresh_token(sub=user.username)

        return AuthTokens(access_token=access_token, refresh_token=refresh_token)

    async def refresh(self, refresh_token: str) -> AuthTokens:
        payload = self.security.decode_token(refresh_token)
        if not payload:
            raise InvalidCredentials("Недействительный или просроченный refresh-токен")

        username = payload["sub"]
        user = await self.user_repository.get_by_username(username=username)
        if not user:
            raise InvalidCredentials("Пользователь не найден")

        new_access_token = self.security.create_access_token(sub=user.username)
        new_refresh_token = self.security.create_refresh_token(sub=user.username)

        return AuthTokens(
            access_token=new_access_token, refresh_token=new_refresh_token
        )
