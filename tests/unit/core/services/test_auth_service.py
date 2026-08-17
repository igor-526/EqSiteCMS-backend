from uuid import UUID

import pytest

from core.entities.user import User, UserScope
from core.exceptions.auth import InvalidCredentials
from core.exceptions.base import ClientError
from core.schemas.auth import LoginData, RegisterData
from core.services.auth import AuthService


class FakeUserRepository:
    def __init__(self, users: dict[str, User] | None = None) -> None:
        self.users = users or {}
        self.scopes: dict[object, list[UserScope]] = {}
        self.calls: list[tuple[str, object]] = []
        self.fail_get_by_username = False
        self.created_user: User | None = None

    async def get_by_username(self, username: str) -> User | None:
        self.calls.append(("get_by_username", username))
        if self.fail_get_by_username:
            raise RuntimeError("repository failure")
        return self.users.get(username)

    async def create(self, entity: User) -> User:
        self.calls.append(("create", entity))
        self.created_user = entity
        self.users[entity.username] = entity
        return entity

    async def get_user_scopes(self, user_id) -> list[UserScope]:
        self.calls.append(("get_user_scopes", user_id))
        return self.scopes.get(user_id, [])


class FakeSecurity:
    def __init__(self, payloads: dict[str, dict | None] | None = None) -> None:
        self.payloads = payloads or {}
        self.calls: list[tuple[str, object]] = []
        self.valid_password = True

    def decode_token(self, token: str) -> dict | None:
        self.calls.append(("decode_token", token))
        payload = self.payloads.get(token)
        if isinstance(payload, Exception):
            raise payload
        return payload

    def hash_password(self, password: str) -> str:
        self.calls.append(("hash_password", password))
        return f"hashed:{password}"

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        self.calls.append(("verify_password", (plain_password, hashed_password)))
        return self.valid_password

    def create_access_token(self, sub: str) -> str:
        self.calls.append(("create_access_token", sub))
        return f"access:{sub}"

    def create_refresh_token(self, sub: str) -> str:
        self.calls.append(("create_refresh_token", sub))
        return f"refresh:{sub}"


def make_user(username: str = "demo", password: str = "hashed-password") -> User:
    return User(
        equestrian_id=UUID("11111111-1111-4111-8111-111111111111"),
        username=username,
        password=password,
        first_name="Demo",
        last_name="User",
        middle_name=None,
    )


def make_scope(scope_name: str = "ADMIN_USERS") -> UserScope:
    return UserScope(scope_name=scope_name, scope_description="Admin users")


@pytest.mark.asyncio
async def test_get_current_user_validates_access_payload_maps_scopes_and_hides_password():
    user = make_user()
    scope = make_scope()
    repository = FakeUserRepository({user.username: user})
    repository.scopes[user.id] = [scope]
    security = FakeSecurity(
        {"token": {"sub": user.username, "token_type": "access", "exp": 1}}
    )
    service = AuthService(user_repository=repository, security=security)

    result = await service.get_current_user("token")

    assert result.username == user.username
    assert result.scopes == [scope]
    assert "password" not in result.model_dump()
    assert security.calls == [("decode_token", "token")]
    assert repository.calls == [
        ("get_by_username", user.username),
        ("get_user_scopes", user.id),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"token_type": "access"},
        {"sub": "", "token_type": "access"},
        {"sub": "   ", "token_type": "access"},
        {"sub": 123, "token_type": "access"},
        {"sub": "demo"},
        {"sub": "demo", "token_type": "refresh"},
        {"sub": "demo", "token_type": "access"},
    ],
)
async def test_get_current_user_rejects_invalid_access_payload(payload):
    repository = FakeUserRepository({"demo": make_user()})
    security = FakeSecurity({"token": payload})
    service = AuthService(user_repository=repository, security=security)

    with pytest.raises(InvalidCredentials):
        await service.get_current_user("token")

    assert repository.calls == []


@pytest.mark.asyncio
async def test_get_current_user_repository_lookup_failure_is_invalid_credentials():
    repository = FakeUserRepository({"demo": make_user()})
    repository.fail_get_by_username = True
    security = FakeSecurity(
        {"token": {"sub": "demo", "token_type": "access", "exp": 1}}
    )
    service = AuthService(user_repository=repository, security=security)

    with pytest.raises(InvalidCredentials):
        await service.get_current_user("token")


@pytest.mark.asyncio
async def test_register_is_disabled_without_mutating_input_or_writing_user():
    repository = FakeUserRepository()
    security = FakeSecurity()
    service = AuthService(user_repository=repository, security=security)
    data = RegisterData(
        username="new-user",
        first_name="New",
        last_name="User",
        middle_name=None,
        password="plain-password",
    )

    with pytest.raises(ClientError):
        await service.register(data=data)

    assert data.password == "plain-password"
    assert repository.created_user is None
    assert repository.calls == []
    assert security.calls == []


@pytest.mark.asyncio
async def test_register_duplicate_username_raises_user_already_exists():
    repository = FakeUserRepository({"demo": make_user("demo")})
    security = FakeSecurity()
    service = AuthService(user_repository=repository, security=security)
    data = RegisterData(
        username="demo",
        first_name="Demo",
        last_name="User",
        middle_name=None,
        password="plain-password",
    )

    with pytest.raises(ClientError):
        await service.register(data=data)

    assert security.calls == []
    assert repository.calls == []


@pytest.mark.asyncio
async def test_login_verifies_password_and_creates_token_pair():
    user = make_user(password="hashed-password")
    repository = FakeUserRepository({user.username: user})
    security = FakeSecurity()
    service = AuthService(user_repository=repository, security=security)

    result = await service.login(LoginData(username=user.username, password="plain"))

    assert result.access_token == f"access:{user.username}"
    assert result.refresh_token == f"refresh:{user.username}"
    assert repository.calls == [("get_by_username", user.username)]
    assert security.calls == [
        ("verify_password", ("plain", "hashed-password")),
        ("create_access_token", user.username),
        ("create_refresh_token", user.username),
    ]


@pytest.mark.asyncio
async def test_login_accepts_smoke_skill_login_alias():
    user = make_user(username="su", password="hashed-password")
    repository = FakeUserRepository({user.username: user})
    security = FakeSecurity()
    service = AuthService(user_repository=repository, security=security)
    data = LoginData.model_validate({"login": "su", "password": "plain"})

    result = await service.login(data)

    assert data.username == "su"
    assert result.access_token == "access:su"
    assert repository.calls == [("get_by_username", "su")]


@pytest.mark.asyncio
async def test_login_invalid_credentials_do_not_create_tokens():
    user = make_user(password="hashed-password")
    repository = FakeUserRepository({user.username: user})
    security = FakeSecurity()
    security.valid_password = False
    service = AuthService(user_repository=repository, security=security)

    with pytest.raises(InvalidCredentials):
        await service.login(LoginData(username=user.username, password="wrong"))

    assert security.calls == [("verify_password", ("wrong", "hashed-password"))]


@pytest.mark.asyncio
async def test_login_unknown_user_does_not_verify_password():
    repository = FakeUserRepository()
    security = FakeSecurity()
    service = AuthService(user_repository=repository, security=security)

    with pytest.raises(InvalidCredentials):
        await service.login(LoginData(username="missing", password="plain"))

    assert security.calls == []


@pytest.mark.asyncio
async def test_refresh_validates_refresh_payload_and_creates_new_token_pair():
    user = make_user()
    repository = FakeUserRepository({user.username: user})
    security = FakeSecurity(
        {"refresh": {"sub": user.username, "token_type": "refresh", "exp": 1}}
    )
    service = AuthService(user_repository=repository, security=security)

    result = await service.refresh("refresh")

    assert result.access_token == f"access:{user.username}"
    assert result.refresh_token == f"refresh:{user.username}"
    assert security.calls == [
        ("decode_token", "refresh"),
        ("create_access_token", user.username),
        ("create_refresh_token", user.username),
    ]
    assert repository.calls == [("get_by_username", user.username)]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"token_type": "refresh"},
        {"sub": "", "token_type": "refresh"},
        {"sub": "demo", "token_type": "access"},
        {"sub": "demo"},
        {"sub": "demo", "token_type": "refresh"},
    ],
)
async def test_refresh_rejects_invalid_refresh_payload(payload):
    repository = FakeUserRepository({"demo": make_user()})
    security = FakeSecurity({"refresh": payload})
    service = AuthService(user_repository=repository, security=security)

    with pytest.raises(InvalidCredentials):
        await service.refresh("refresh")

    assert repository.calls == []


@pytest.mark.asyncio
async def test_refresh_missing_user_raises_invalid_credentials_without_tokens():
    repository = FakeUserRepository()
    security = FakeSecurity(
        {"refresh": {"sub": "missing", "token_type": "refresh", "exp": 1}}
    )
    service = AuthService(user_repository=repository, security=security)

    with pytest.raises(InvalidCredentials):
        await service.refresh("refresh")

    assert security.calls == [("decode_token", "refresh")]
