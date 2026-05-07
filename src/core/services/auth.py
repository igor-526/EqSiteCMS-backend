from typing import Any

from core.entities.user import User
from core.exceptions.auth import InvalidCredentials, UserAlreadyExists
from core.exceptions.base import ClientError
from core.protocols.repositories.user_repository import UserRepositoryProtocol
from core.protocols.security import SecurityProtocol
from core.schemas.auth import AuthTokens, LoginData, RegisterData
from core.schemas.users import UserOutDto

TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"


class AuthService:
    def __init__(
        self, user_repository: UserRepositoryProtocol, security: SecurityProtocol
    ):
        self.user_repository = user_repository
        self.security = security

    def _get_token_subject(
        self, payload: dict[str, Any] | None, *, expected_token_type: str
    ) -> str:
        if not payload:
            raise InvalidCredentials("Недействительный или просроченный токен")

        token_type = payload.get("token_type")
        if token_type != expected_token_type:
            raise InvalidCredentials("Некорректный тип токена")

        if payload.get("exp") is None:
            raise InvalidCredentials("Некорректное содержимое токена")

        username = payload.get("sub")
        if not isinstance(username, str) or not username.strip():
            raise InvalidCredentials("Некорректное содержимое токена")

        return username

    def _map_user_out(self, user: User, scopes: list | None = None) -> UserOutDto:
        user_dict = user.model_dump()
        user_dict["scopes"] = scopes or []
        return UserOutDto.model_validate(user_dict)

    async def _get_user_by_token_subject(self, username: str) -> User:
        try:
            user = await self.user_repository.get_by_username(username=username)
        except Exception as exc:
            raise InvalidCredentials("Ошибка проверки пользователя") from exc

        if not user:
            raise InvalidCredentials("Пользователь не найден")

        return user

    async def get_current_user(self, token: str) -> UserOutDto:
        payload = self.security.decode_token(token)
        username = self._get_token_subject(
            payload, expected_token_type=TOKEN_TYPE_ACCESS
        )
        user = await self._get_user_by_token_subject(username)

        scopes = await self.user_repository.get_user_scopes(user.id)
        return self._map_user_out(user, scopes)

    async def register(self, data: RegisterData) -> UserOutDto:
        raise ClientError(
            "Публичная регистрация отключена: привязка пользователя к конюшне "
            "выполняется прямой операцией в БД"
        )
        if await self.user_repository.get_by_username(username=data.username):
            raise UserAlreadyExists(
                f"Пользователь с именем {data.username} уже существует"
            )

        user_data = data.model_dump()
        user_data["password"] = self.security.hash_password(data.password)
        user = User(**user_data)
        user = await self.user_repository.create(user)
        return self._map_user_out(user)

    async def login(self, data: LoginData) -> AuthTokens:
        user = await self.user_repository.get_by_username(username=data.username)
        if not user or not self.security.verify_password(data.password, user.password):
            raise InvalidCredentials("Неверное имя пользователя или пароль")

        access_token = self.security.create_access_token(sub=user.username)
        refresh_token = self.security.create_refresh_token(sub=user.username)

        return AuthTokens(access_token=access_token, refresh_token=refresh_token)

    async def refresh(self, refresh_token: str) -> AuthTokens:
        payload = self.security.decode_token(refresh_token)
        username = self._get_token_subject(
            payload, expected_token_type=TOKEN_TYPE_REFRESH
        )
        user = await self._get_user_by_token_subject(username)

        new_access_token = self.security.create_access_token(sub=user.username)
        new_refresh_token = self.security.create_refresh_token(sub=user.username)

        return AuthTokens(
            access_token=new_access_token, refresh_token=new_refresh_token
        )
