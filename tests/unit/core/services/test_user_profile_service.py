"""Unit-тесты для UserService: get_my_profile, update_my_profile, change_my_password.

Покрывает UT-01 — UT-35 из плана docs/plans/feature/current_user_management.md.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from core.entities.equestrian import Equestrian
from core.entities.user import User, UserScope
from core.exceptions.base import ClientError
from core.schemas.users import (
    ChangePasswordIn,
    UpdateProfileIn,
    UserOutDto,
    UserProfileDto,
)
from core.services.users import UserService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEST_EQUESTRIAN_ID = UUID("11111111-1111-4111-8111-111111111111")
TEST_USER_ID = UUID("22222222-2222-4222-8222-222222222222")

# ---------------------------------------------------------------------------
# Fake dependencies
# ---------------------------------------------------------------------------


class FakeUserRepository:
    def __init__(self, user: User | None = None) -> None:
        self._user = user
        self.calls: list[tuple[str, object]] = []
        self.updated_entity: User | None = None

    async def get_by_id(self, id: UUID) -> User | None:
        self.calls.append(("get_by_id", id))
        if self._user is not None and self._user.id == id:
            return self._user
        return None

    async def get_all(
        self, *, limit: int | None = None, offset: int | None = None
    ) -> list[User]:
        return []

    async def get_by_ids(self, ids: Sequence[UUID]) -> dict[UUID, User]:
        return {}

    async def update(self, entity: User) -> User:
        self.calls.append(("update", entity))
        self.updated_entity = entity
        self._user = entity
        return entity

    async def create(self, entity: User) -> User:
        return entity

    async def bulk_create(self, entities: list[User]) -> list[User]:
        return entities

    async def delete(self, id: UUID) -> None:
        return None

    async def bulk_delete(self, ids: Sequence[UUID]) -> None:
        return None

    async def get_by_username(self, username: str) -> User | None:
        return None

    async def get_user_scopes(self, user_id: UUID) -> list[UserScope]:
        return []

    async def get_users_paginated(
        self,
        *,
        equestrian_ids: list[UUID] | None = None,
        equestrian_service_keys: list[str] | None = None,
        roles: list[str] | None = None,
        exclude_deleted: bool = False,
        exclude_blocked: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[User], int]:
        return [], 0


class FakeEquestrianRepository:
    def __init__(
        self,
        equestrian: Equestrian | None = None,
        raise_exception: bool = False,
    ) -> None:
        self._equestrian = equestrian
        self._raise = raise_exception
        self.calls: list[tuple[str, object]] = []

    async def get_by_id(self, id: UUID) -> Equestrian | None:
        self.calls.append(("get_by_id", id))
        if self._raise:
            raise RuntimeError("equestrian repository failure")
        return self._equestrian

    async def get_by_service_key(self, service_key: str) -> Equestrian | None:
        return None

    async def get_all(
        self, *, limit: int | None = None, offset: int | None = None
    ) -> list[Equestrian]:
        return []

    async def get_by_ids(self, ids: Sequence[UUID]) -> dict[UUID, Equestrian]:
        return {}

    async def update(self, entity: Equestrian) -> Equestrian:
        return entity

    async def create(self, entity: Equestrian) -> Equestrian:
        return entity

    async def bulk_create(self, entities: list[Equestrian]) -> list[Equestrian]:
        return entities

    async def delete(self, id: UUID) -> None:
        return None

    async def bulk_delete(self, ids: Sequence[UUID]) -> None:
        return None


class FakeSecurity:
    def __init__(self, valid_password: bool = True) -> None:
        self.valid_password = valid_password
        self.calls: list[tuple[str, object]] = []
        self._raise_on_verify = False

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        self.calls.append(("verify_password", (plain_password, hashed_password)))
        if self._raise_on_verify:
            raise RuntimeError("verify_password failure")
        return self.valid_password

    def hash_password(self, password: str) -> str:
        self.calls.append(("hash_password", password))
        return f"hashed:{password}"

    def create_access_token(self, sub: str) -> str:
        return f"access:{sub}"

    def create_refresh_token(self, sub: str) -> str:
        return f"refresh:{sub}"

    def decode_token(self, token: str) -> dict:
        return {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_equestrian(name: str = "Конюшня Солнечная") -> Equestrian:
    return Equestrian(
        id=TEST_EQUESTRIAN_ID,
        name=name,
        service_key="test-key",
    )


def make_user(
    *,
    id: UUID | None = None,
    equestrian_id: UUID | None = None,
    username: str = "testuser",
    password: str = "hashed-password",
    first_name: str | None = "Иван",
    last_name: str | None = "Иванов",
    middle_name: str | None = "Иванович",
) -> User:
    return User(
        id=id or TEST_USER_ID,
        equestrian_id=equestrian_id or TEST_EQUESTRIAN_ID,
        username=username,
        password=password,
        first_name=first_name,
        last_name=last_name,
        middle_name=middle_name,
    )


def make_scope(scope_name: str = "ADMIN") -> UserScope:
    return UserScope(scope_name=scope_name, scope_description="Администратор")


def make_current_user(
    *,
    id: UUID | None = None,
    equestrian_id: UUID | None = None,
    username: str = "testuser",
    first_name: str | None = "Иван",
    last_name: str | None = "Иванов",
    middle_name: str | None = "Иванович",
    scopes: list[UserScope] | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> UserOutDto:
    return UserOutDto(
        id=id or TEST_USER_ID,
        equestrian_id=equestrian_id or TEST_EQUESTRIAN_ID,
        username=username,
        first_name=first_name,
        last_name=last_name,
        middle_name=middle_name,
        scopes=scopes or [],
        created_at=created_at or datetime.now(),
        updated_at=updated_at or datetime.now(),
    )


def make_service(
    *,
    user: User | None = None,
    equestrian: Equestrian | None = None,
    equestrian_raises: bool = False,
    valid_password: bool = True,
) -> tuple[UserService, FakeUserRepository, FakeEquestrianRepository, FakeSecurity]:
    user_repo = FakeUserRepository(user=user)
    eq_repo = FakeEquestrianRepository(
        equestrian=equestrian, raise_exception=equestrian_raises
    )
    security = FakeSecurity(valid_password=valid_password)
    service = UserService(
        repository=user_repo,
        equestrian_repository=eq_repo,
        security=security,
    )
    return service, user_repo, eq_repo, security


# ---------------------------------------------------------------------------
# UT-01 — UT-08: get_my_profile
# ---------------------------------------------------------------------------


async def test_ut01_get_my_profile_equestrian_exists_name_matches() -> None:
    """UT-01: equestrian found → equestrian_name совпадает с equestrian.name."""
    eq = make_equestrian("Конюшня Звёздная")
    service, _, _, _ = make_service(equestrian=eq)
    current_user = make_current_user()

    result = await service.get_my_profile(current_user)

    assert result.equestrian_name == "Конюшня Звёздная"


async def test_ut02_get_my_profile_equestrian_not_found_graceful_none() -> None:
    """UT-02: equestrian не найден (get_by_id → None) → equestrian_name = None."""
    service, _, _, _ = make_service(equestrian=None)
    current_user = make_current_user()

    result = await service.get_my_profile(current_user)

    assert result.equestrian_name is None


async def test_ut03_equestrian_repository_called_with_equestrian_id() -> None:
    """UT-03: equestrian_repository.get_by_id вызван с current_user.equestrian_id."""
    eq = make_equestrian()
    service, _, eq_repo, _ = make_service(equestrian=eq)
    current_user = make_current_user(equestrian_id=TEST_EQUESTRIAN_ID)

    await service.get_my_profile(current_user)

    assert ("get_by_id", TEST_EQUESTRIAN_ID) in eq_repo.calls


async def test_ut04_get_my_profile_scopes_present_in_result() -> None:
    """UT-04: scopes из current_user присутствуют в UserProfileDto."""
    scope = make_scope("SUPERUSER")
    service, _, _, _ = make_service()
    current_user = make_current_user(scopes=[scope])

    result = await service.get_my_profile(current_user)

    assert result.scopes == [scope]


async def test_ut05_equestrian_repository_exception_graceful_none() -> None:
    """UT-05: equestrian_repository выбрасывает исключение → equestrian_name = None."""
    service, _, _, _ = make_service(equestrian_raises=True)
    current_user = make_current_user()

    result = await service.get_my_profile(current_user)

    assert result.equestrian_name is None


async def test_ut06_get_my_profile_user_without_scopes_empty_list() -> None:
    """UT-06: пользователь без scopes (scopes=[]) → пустой список в ответе."""
    service, _, _, _ = make_service()
    current_user = make_current_user(scopes=[])

    result = await service.get_my_profile(current_user)

    assert result.scopes == []


async def test_ut07_get_my_profile_all_fields_mapped() -> None:
    """UT-07: все поля UserProfileDto корректно mapped из current_user."""
    eq = make_equestrian("Тест")
    scope = make_scope("ADMIN")
    now = datetime.now()
    service, _, _, _ = make_service(equestrian=eq)
    current_user = make_current_user(
        first_name="Антон",
        last_name="Петров",
        middle_name="Сергеевич",
        scopes=[scope],
        created_at=now,
    )

    result = await service.get_my_profile(current_user)

    assert result.first_name == "Антон"
    assert result.last_name == "Петров"
    assert result.middle_name == "Сергеевич"
    assert result.equestrian_name == "Тест"
    assert result.scopes == [scope]
    assert result.created_at == now


async def test_ut08_get_my_profile_id_username_equestrian_id_created_at_match() -> None:
    """UT-08: id, username, equestrian_id, created_at совпадают с current_user."""
    service, _, _, _ = make_service()
    uid = uuid4()
    eq_id = uuid4()
    now = datetime.now()
    current_user = make_current_user(
        id=uid, equestrian_id=eq_id, username="myuser", created_at=now
    )

    result = await service.get_my_profile(current_user)

    assert result.id == uid
    assert result.username == "myuser"
    assert result.equestrian_id == eq_id
    assert result.created_at == now


# ---------------------------------------------------------------------------
# UT-09 — UT-19: update_my_profile
# ---------------------------------------------------------------------------


async def test_ut09_update_my_profile_get_by_id_called() -> None:
    """UT-09: update_my_profile valid data → user_repo.get_by_id(current_user.id) вызван."""
    user = make_user()
    service, user_repo, _, _ = make_service(user=user)
    current_user = make_current_user(id=user.id)
    data = UpdateProfileIn(first_name="Новое", last_name="Имя", middle_name=None)

    await service.update_my_profile(current_user, data)

    assert ("get_by_id", user.id) in user_repo.calls


async def test_ut10_update_my_profile_update_called_with_entity() -> None:
    """UT-10: update_my_profile valid data → user_repo.update() вызван с обновлённой сущностью."""
    user = make_user()
    service, user_repo, _, _ = make_service(user=user)
    current_user = make_current_user(id=user.id)
    data = UpdateProfileIn(first_name="Анна", last_name="Кова", middle_name="Ивановна")

    await service.update_my_profile(current_user, data)

    update_calls = [(name, e) for name, e in user_repo.calls if name == "update"]
    assert len(update_calls) == 1
    updated = update_calls[0][1]
    assert isinstance(updated, User)
    assert updated.first_name == "Анна"


async def test_ut11_update_my_profile_only_first_name_others_unchanged() -> None:
    """UT-11: update только first_name → entity.first_name обновлена, остальные поля без изменений."""
    user = make_user(first_name="Старое", last_name="Фамилия", middle_name="Отчество")
    service, user_repo, _, _ = make_service(user=user)
    current_user = make_current_user(id=user.id)
    data = UpdateProfileIn(first_name="Новое", last_name=None, middle_name=None)

    await service.update_my_profile(current_user, data)

    updated = user_repo.updated_entity
    assert updated is not None
    assert updated.first_name == "Новое"
    # last_name и middle_name — что передано в data (None), а не сохранённые
    # По спецификации: все три поля применяются из data, даже если None
    assert updated.last_name is None
    assert updated.middle_name is None


async def test_ut12_update_my_profile_all_none_is_valid() -> None:
    """UT-12: все поля None → допустимо, entity обновляется."""
    user = make_user()
    service, user_repo, _, _ = make_service(user=user)
    current_user = make_current_user(id=user.id)
    data = UpdateProfileIn(first_name=None, last_name=None, middle_name=None)

    result = await service.update_my_profile(current_user, data)

    assert result.first_name is None
    assert result.last_name is None
    assert result.middle_name is None


async def test_ut13_update_my_profile_returns_updated_dto() -> None:
    """UT-13: update_my_profile возвращает UserProfileDto с новыми значениями."""
    user = make_user()
    service, _, _, _ = make_service(user=user)
    current_user = make_current_user(id=user.id)
    data = UpdateProfileIn(first_name="Новая", last_name="Фамилия", middle_name="Тест")

    result = await service.update_my_profile(current_user, data)

    assert isinstance(result, UserProfileDto)
    assert result.first_name == "Новая"
    assert result.last_name == "Фамилия"
    assert result.middle_name == "Тест"


async def test_ut14_update_my_profile_equestrian_name_present_in_result() -> None:
    """UT-14: equestrian_name присутствует в возвращённом UserProfileDto."""
    eq = make_equestrian("Конюшня Радуга")
    user = make_user()
    service, _, _, _ = make_service(user=user, equestrian=eq)
    current_user = make_current_user(id=user.id)
    data = UpdateProfileIn()

    result = await service.update_my_profile(current_user, data)

    assert result.equestrian_name == "Конюшня Радуга"


async def test_ut15_update_my_profile_password_not_changed() -> None:
    """UT-15: поле password не изменяется при update_my_profile."""
    original_password = "original-hashed-password"
    user = make_user(password=original_password)
    service, user_repo, _, _ = make_service(user=user)
    current_user = make_current_user(id=user.id)
    data = UpdateProfileIn(first_name="Тест")

    await service.update_my_profile(current_user, data)

    updated = user_repo.updated_entity
    assert updated is not None
    assert updated.password == original_password


async def test_ut16_update_my_profile_username_not_changed() -> None:
    """UT-16: поле username не изменяется при update_my_profile."""
    user = make_user(username="originaluser")
    service, user_repo, _, _ = make_service(user=user)
    current_user = make_current_user(id=user.id, username="originaluser")
    data = UpdateProfileIn(first_name="Тест")

    await service.update_my_profile(current_user, data)

    updated = user_repo.updated_entity
    assert updated is not None
    assert updated.username == "originaluser"


async def test_ut17_update_my_profile_equestrian_id_not_changed() -> None:
    """UT-17: equestrian_id не изменяется при update_my_profile."""
    original_eq_id = TEST_EQUESTRIAN_ID
    user = make_user(equestrian_id=original_eq_id)
    service, user_repo, _, _ = make_service(user=user)
    current_user = make_current_user(id=user.id, equestrian_id=original_eq_id)
    data = UpdateProfileIn(first_name="Тест")

    await service.update_my_profile(current_user, data)

    updated = user_repo.updated_entity
    assert updated is not None
    assert updated.equestrian_id == original_eq_id


async def test_ut18_update_my_profile_update_called_once() -> None:
    """UT-18: user_repo.update() вызван ровно один раз."""
    user = make_user()
    service, user_repo, _, _ = make_service(user=user)
    current_user = make_current_user(id=user.id)
    data = UpdateProfileIn()

    await service.update_my_profile(current_user, data)

    update_calls = [name for name, _ in user_repo.calls if name == "update"]
    assert len(update_calls) == 1


async def test_ut19_update_my_profile_user_not_found_raises_client_error() -> None:
    """UT-19: user не найден (get_by_id → None) → ClientError, update не вызывается."""
    service, user_repo, _, _ = make_service(user=None)
    current_user = make_current_user(id=TEST_USER_ID)
    data = UpdateProfileIn(first_name="Тест")

    with pytest.raises(ClientError):
        await service.update_my_profile(current_user, data)

    update_calls = [name for name, _ in user_repo.calls if name == "update"]
    assert len(update_calls) == 0


# ---------------------------------------------------------------------------
# UT-20 — UT-28: change_my_password
# ---------------------------------------------------------------------------


async def test_ut20_change_my_password_valid_flow_order() -> None:
    """UT-20: valid flow: verify_password → hash_password → update вызваны в правильном порядке."""
    user = make_user(password="hashed-old")
    service, user_repo, _, security = make_service(user=user, valid_password=True)
    current_user = make_current_user(id=user.id)
    data = ChangePasswordIn(
        current_password="old-plain",
        new_password="newpassword123",
        confirm_new_password="newpassword123",
    )

    await service.change_my_password(current_user, data)

    call_names = [name for name, _ in security.calls]
    assert call_names == ["verify_password", "hash_password"]
    update_calls = [name for name, _ in user_repo.calls if name == "update"]
    assert len(update_calls) == 1


async def test_ut21_change_my_password_wrong_password_raises_client_error() -> None:
    """UT-21: неверный current_password → verify_password возвращает False → ClientError (400)."""
    user = make_user(password="hashed-old")
    service, _, _, _ = make_service(user=user, valid_password=False)
    current_user = make_current_user(id=user.id)
    data = ChangePasswordIn(
        current_password="wrong-password",
        new_password="newpassword123",
        confirm_new_password="newpassword123",
    )

    with pytest.raises(ClientError):
        await service.change_my_password(current_user, data)


async def test_ut22_change_my_password_verify_raises_propagated() -> None:
    """UT-22: verify_password выбрасывает → ошибка propagated."""
    user = make_user()
    service, _, _, security = make_service(user=user)
    security._raise_on_verify = True
    current_user = make_current_user(id=user.id)
    data = ChangePasswordIn(
        current_password="old",
        new_password="newpassword123",
        confirm_new_password="newpassword123",
    )

    with pytest.raises(RuntimeError):
        await service.change_my_password(current_user, data)


async def test_ut23_change_my_password_entity_password_is_hash_not_plaintext() -> None:
    """UT-23: entity.password == hash(new_password), не plaintext."""
    user = make_user(password="hashed-old")
    service, user_repo, _, _ = make_service(user=user, valid_password=True)
    current_user = make_current_user(id=user.id)
    new_plain = "newpassword123"
    data = ChangePasswordIn(
        current_password="old-plain",
        new_password=new_plain,
        confirm_new_password=new_plain,
    )

    await service.change_my_password(current_user, data)

    updated = user_repo.updated_entity
    assert updated is not None
    assert updated.password == f"hashed:{new_plain}"
    assert updated.password != new_plain


async def test_ut24_change_my_password_update_called_once_on_success() -> None:
    """UT-24: user_repo.update() вызван ровно один раз при успехе."""
    user = make_user()
    service, user_repo, _, _ = make_service(user=user, valid_password=True)
    current_user = make_current_user(id=user.id)
    data = ChangePasswordIn(
        current_password="old",
        new_password="newpassword123",
        confirm_new_password="newpassword123",
    )

    await service.change_my_password(current_user, data)

    update_calls = [name for name, _ in user_repo.calls if name == "update"]
    assert len(update_calls) == 1


async def test_ut25_change_my_password_user_not_found_raises_no_update() -> None:
    """UT-25: user не найден (get_by_id → None) → ошибка, update не вызывается."""
    service, user_repo, _, _ = make_service(user=None, valid_password=True)
    current_user = make_current_user(id=TEST_USER_ID)
    data = ChangePasswordIn(
        current_password="old",
        new_password="newpassword123",
        confirm_new_password="newpassword123",
    )

    with pytest.raises(ClientError):
        await service.change_my_password(current_user, data)

    update_calls = [name for name, _ in user_repo.calls if name == "update"]
    assert len(update_calls) == 0


async def test_ut26_change_my_password_hash_called_with_new_password() -> None:
    """UT-26: security.hash_password вызван с new_password."""
    user = make_user()
    service, _, _, security = make_service(user=user, valid_password=True)
    current_user = make_current_user(id=user.id)
    new_pass = "mynewpassword"
    data = ChangePasswordIn(
        current_password="old",
        new_password=new_pass,
        confirm_new_password=new_pass,
    )

    await service.change_my_password(current_user, data)

    hash_calls = [
        (name, arg) for name, arg in security.calls if name == "hash_password"
    ]
    assert len(hash_calls) == 1
    assert hash_calls[0][1] == new_pass


async def test_ut27_change_my_password_new_equals_current_is_allowed() -> None:
    """UT-27: новый пароль == текущему → операция проходит (нет бизнес-запрета)."""
    same_pass = "samepassword123"
    user = make_user(password="hashed-old")
    service, _, _, _ = make_service(user=user, valid_password=True)
    current_user = make_current_user(id=user.id)
    data = ChangePasswordIn(
        current_password="old",
        new_password=same_pass,
        confirm_new_password=same_pass,
    )

    # Не должно выбрасывать исключение
    await service.change_my_password(current_user, data)


async def test_ut28_change_my_password_returns_none() -> None:
    """UT-28: при успехе метод возвращает None (не UserProfile)."""
    user = make_user()
    service, _, _, _ = make_service(user=user, valid_password=True)
    current_user = make_current_user(id=user.id)
    data = ChangePasswordIn(
        current_password="old",
        new_password="newpassword123",
        confirm_new_password="newpassword123",
    )

    await service.change_my_password(current_user, data)


# ---------------------------------------------------------------------------
# UT-29 — UT-30: UserProfileDto schema serialization
# ---------------------------------------------------------------------------


def test_ut29_user_profile_dto_equestrian_name_in_json() -> None:
    """UT-29: UserProfileDto equestrian_name = 'Конюшня' → поле присутствует в сериализованном JSON."""
    dto = UserProfileDto(
        id=TEST_USER_ID,
        equestrian_id=TEST_EQUESTRIAN_ID,
        equestrian_name="Конюшня",
        username="testuser",
        created_at=datetime.now(),
    )

    dumped = dto.model_dump()

    assert "equestrian_name" in dumped
    assert dumped["equestrian_name"] == "Конюшня"


def test_ut30_user_profile_dto_equestrian_name_none_in_json() -> None:
    """UT-30: UserProfileDto equestrian_name = None → поле присутствует как null в JSON."""
    dto = UserProfileDto(
        id=TEST_USER_ID,
        equestrian_id=TEST_EQUESTRIAN_ID,
        equestrian_name=None,
        username="testuser",
        created_at=datetime.now(),
    )

    dumped = dto.model_dump()

    assert "equestrian_name" in dumped
    assert dumped["equestrian_name"] is None


# ---------------------------------------------------------------------------
# UT-31 — UT-32: UpdateProfileIn schema validation
# ---------------------------------------------------------------------------


def test_ut31_update_profile_in_first_name_too_long_raises_validation_error() -> None:
    """UT-31: UpdateProfileIn first_name длиннее 63 символов → Pydantic ValidationError."""
    long_name = "А" * 64

    with pytest.raises(ValidationError):
        UpdateProfileIn(first_name=long_name)


def test_ut32_update_profile_in_all_none_is_valid() -> None:
    """UT-32: UpdateProfileIn all None → schema валидна (все поля optional)."""
    dto = UpdateProfileIn(first_name=None, last_name=None, middle_name=None)

    assert dto.first_name is None
    assert dto.last_name is None
    assert dto.middle_name is None


# ---------------------------------------------------------------------------
# UT-33 — UT-35: ChangePasswordIn schema validation
# ---------------------------------------------------------------------------


def test_ut33_change_password_in_new_password_too_short_raises_validation_error() -> (
    None
):
    """UT-33: ChangePasswordIn new_password короче 8 символов → Pydantic ValidationError."""
    with pytest.raises(ValidationError):
        ChangePasswordIn(
            current_password="old",
            new_password="short",
            confirm_new_password="short",
        )


def test_ut34_change_password_in_confirm_mismatch_raises_validation_error() -> None:
    """UT-34: ChangePasswordIn confirm_new_password != new_password → Pydantic ValidationError."""
    with pytest.raises(ValidationError):
        ChangePasswordIn(
            current_password="old",
            new_password="newpassword123",
            confirm_new_password="differentpassword",
        )


def test_ut35_change_password_in_empty_current_password_raises_validation_error() -> (
    None
):
    """UT-35: ChangePasswordIn пустой current_password → Pydantic ValidationError."""
    with pytest.raises(ValidationError):
        ChangePasswordIn(
            current_password="",
            new_password="newpassword123",
            confirm_new_password="newpassword123",
        )
