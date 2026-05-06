import pytest

from core.entities.user import User
from core.exceptions.auth import InvalidCredentials
from core.schemas.users import UserOutDto
from depends.services import get_current_user


class StubAuthService:
    def __init__(self) -> None:
        self.tokens: list[str] = []
        self.user = UserOutDto.model_validate(
            User(
                username="demo",
                password="hashed-password",
                first_name="Demo",
                last_name="User",
                middle_name=None,
            )
        )

    async def get_current_user(self, token: str) -> UserOutDto:
        self.tokens.append(token)
        return self.user


@pytest.mark.asyncio
async def test_get_current_user_without_cookie_raises_invalid_credentials():
    auth_service = StubAuthService()

    with pytest.raises(InvalidCredentials):
        await get_current_user(auth_service=auth_service, access_token=None)

    assert auth_service.tokens == []


@pytest.mark.asyncio
async def test_get_current_user_with_cookie_delegates_to_auth_service():
    auth_service = StubAuthService()

    result = await get_current_user(auth_service=auth_service, access_token="token")

    assert result == auth_service.user
    assert auth_service.tokens == ["token"]
