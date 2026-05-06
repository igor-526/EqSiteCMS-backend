from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from core.entities.user import User
from core.services.users import UserService

pytestmark = pytest.mark.asyncio


class RepositoryError(Exception):
    pass


class FakeUserRepository:
    def __init__(self) -> None:
        self.users: list[Any] = []
        self.calls: list[tuple[str, Any]] = []
        self.fail_on_get_all = False

    async def get_all(
        self, *, limit: int | None = None, offset: int | None = None
    ) -> list[Any]:
        self.calls.append(("get_all", {"limit": limit, "offset": offset}))
        if self.fail_on_get_all:
            raise RepositoryError("get_all")
        return list(self.users)

    async def get_by_id(self, id: UUID) -> User | None:
        return None

    async def get_by_ids(self, ids: Sequence[UUID]) -> dict[UUID, User]:
        return {}

    async def update(self, entity: User) -> User:
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

    async def get_user_scopes(self, user_id: UUID):
        return []


class FakeUserRow:
    def __init__(self, **data: Any) -> None:
        self._data = data

    def model_dump(self) -> dict[str, Any]:
        return dict(self._data)


def make_broken_user_row(**overrides: Any) -> FakeUserRow:
    data: dict[str, Any] = {
        "id": uuid4(),
        "username": "broken",
        "password": "hashed-password",
        "first_name": "Broken",
        "last_name": "User",
        "middle_name": None,
        "created_at": datetime.now(),
        "updated_at": datetime.now(),
    }
    data.update(overrides)
    return FakeUserRow(**data)


def make_user(
    *,
    id: UUID | None = None,
    username: str = "demo",
    password: str = "hashed-password",
    first_name: str | None = "Demo",
    last_name: str | None = "User",
    middle_name: str | None = None,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> User:
    return User(
        id=id or uuid4(),
        username=username,
        password=password,
        first_name=first_name,
        last_name=last_name,
        middle_name=middle_name,
        created_at=created_at or datetime.now(),
        updated_at=updated_at or datetime.now(),
    )


def make_service() -> tuple[UserService, FakeUserRepository]:
    repo = FakeUserRepository()
    return UserService(repository=repo), repo


async def test_get_users_uc01_happy_path_maps_entities_to_public_dto() -> None:
    service, repo = make_service()
    repo.users = [make_user(username="u1"), make_user(username="u2")]

    result = await service.get_users()

    assert [dto.username for dto in result] == ["u1", "u2"]
    assert "password" not in result[0].model_dump()


async def test_get_users_uc02_minimal_input_uses_default_pagination() -> None:
    service, repo = make_service()

    await service.get_users()

    assert repo.calls == [("get_all", {"limit": None, "offset": None})]


async def test_get_users_uc03_full_input_forwards_limit_and_offset() -> None:
    service, repo = make_service()

    await service.get_users(limit=50, offset=10)

    assert repo.calls == [("get_all", {"limit": 50, "offset": 10})]


async def test_get_users_uc04_omitted_optional_offset_is_none() -> None:
    service, repo = make_service()

    await service.get_users(limit=20)

    assert repo.calls == [("get_all", {"limit": 20, "offset": None})]


async def test_get_users_uc05_empty_values_zero_limit_offset_are_forwarded() -> None:
    service, repo = make_service()

    await service.get_users(limit=0, offset=0)

    assert repo.calls == [("get_all", {"limit": 0, "offset": 0})]


async def test_get_users_uc06_whitespace_username_is_not_trimmed_by_service() -> None:
    service, repo = make_service()
    repo.users = [make_user(username="  user  ")]

    result = await service.get_users()

    assert result[0].username == "  user  "


async def test_get_users_uc07_unicode_and_case_values_are_preserved() -> None:
    service, repo = make_service()
    repo.users = [make_user(username="ИгорьAdmin")]

    result = await service.get_users()

    assert result[0].username == "ИгорьAdmin"


async def test_get_users_uc08_boundary_min_limit_one_is_forwarded() -> None:
    service, repo = make_service()

    await service.get_users(limit=1, offset=0)

    assert repo.calls == [("get_all", {"limit": 1, "offset": 0})]


async def test_get_users_uc09_below_min_limit_negative_is_not_rewritten() -> None:
    service, repo = make_service()

    await service.get_users(limit=-1, offset=0)

    assert repo.calls == [("get_all", {"limit": -1, "offset": 0})]


async def test_get_users_uc10_boundary_max_limit_is_forwarded() -> None:
    service, repo = make_service()

    await service.get_users(limit=1000, offset=0)

    assert repo.calls == [("get_all", {"limit": 1000, "offset": 0})]


async def test_get_users_uc11_above_max_limit_is_forwarded_unchanged() -> None:
    service, repo = make_service()

    await service.get_users(limit=1000000, offset=0)

    assert repo.calls == [("get_all", {"limit": 1000000, "offset": 0})]


async def test_get_users_uc12_malformed_identifier_fails_structural_mapping() -> None:
    service, repo = make_service()
    repo.users = [make_broken_user_row(id="not-a-uuid")]

    with pytest.raises(ValidationError):
        await service.get_users()


async def test_get_users_uc13_not_found_returns_empty_list() -> None:
    service, repo = make_service()
    repo.users = []

    result = await service.get_users()

    assert result == []


async def test_get_users_uc14_duplicate_usernames_are_not_collapsed() -> None:
    service, repo = make_service()
    repo.users = [make_user(username="dup"), make_user(username="dup")]

    result = await service.get_users()

    assert [dto.username for dto in result] == ["dup", "dup"]


async def test_get_users_uc15_self_exclusion_is_not_applied_to_list_result() -> None:
    service, repo = make_service()
    same_id = uuid4()
    repo.users = [
        make_user(id=same_id, username="me"),
        make_user(id=same_id, username="me"),
    ]

    result = await service.get_users()

    assert len(result) == 2


async def test_get_users_uc16_reference_validation_is_outside_service_scope() -> None:
    service, repo = make_service()
    repo.users = [
        User.model_construct(
            id=uuid4(),
            username="broken-scope",
            password="hashed-password",
            first_name="Broken",
            last_name="Scope",
            middle_name=None,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            scopes=["not-a-scope-object"],
        )
    ]

    result = await service.get_users()

    assert result[0].username == "broken-scope"


async def test_get_users_uc17_permission_allowed_no_permission_checks_in_service() -> (
    None
):
    service, repo = make_service()
    repo.users = [make_user(username="allowed")]

    result = await service.get_users()

    assert result[0].username == "allowed"


async def test_get_users_uc18_permission_denied_not_handled_on_service_layer() -> None:
    service, repo = make_service()
    repo.users = [make_user(username="denied")]

    result = await service.get_users()

    assert result[0].username == "denied"


async def test_get_users_uc19_partial_profile_fields_are_supported() -> None:
    service, repo = make_service()
    repo.users = [make_user(first_name=None, last_name=None, middle_name=None)]

    result = await service.get_users()

    assert result[0].first_name is None
    assert result[0].last_name is None
    assert result[0].middle_name is None


async def test_get_users_uc20_empty_collection_is_stable_across_calls() -> None:
    service, repo = make_service()
    repo.users = []

    first = await service.get_users()
    second = await service.get_users()

    assert first == []
    assert second == []


async def test_get_users_uc21_repository_failure_is_propagated() -> None:
    service, repo = make_service()
    repo.fail_on_get_all = True

    with pytest.raises(RepositoryError):
        await service.get_users()


async def test_get_users_uc22_dependency_order_calls_repository_once() -> None:
    service, repo = make_service()
    repo.users = [make_user()]

    await service.get_users()

    assert [name for name, _ in repo.calls] == ["get_all"]


async def test_get_users_uc23_no_retry_or_rollback_on_mapping_error() -> None:
    service, repo = make_service()
    repo.users = [make_broken_user_row(id="invalid", username="invalid")]

    with pytest.raises(ValidationError):
        await service.get_users()

    assert [name for name, _ in repo.calls] == ["get_all"]


async def test_get_users_uc24_idempotency_same_request_same_result() -> None:
    service, repo = make_service()
    repo.users = [make_user(username="repeat")]

    first = await service.get_users(limit=10, offset=0)
    second = await service.get_users(limit=10, offset=0)

    assert [dto.username for dto in first] == [dto.username for dto in second]
    assert len(repo.calls) == 2


async def test_get_users_uc25_sorting_stability_keeps_repository_order() -> None:
    service, repo = make_service()
    repo.users = [
        make_user(username="z-last"),
        make_user(username="a-first"),
        make_user(username="m-middle"),
    ]

    result = await service.get_users()

    assert [dto.username for dto in result] == ["z-last", "a-first", "m-middle"]


async def test_get_users_uc26_filtering_semantics_service_does_not_filter() -> None:
    service, repo = make_service()
    repo.users = [make_user(username="active"), make_user(username="inactive")]

    result = await service.get_users()

    assert {dto.username for dto in result} == {"active", "inactive"}


async def test_get_users_uc27_pagination_semantics_forwarding_is_explicit() -> None:
    service, repo = make_service()

    await service.get_users(limit=5, offset=15)

    assert repo.calls[-1] == ("get_all", {"limit": 5, "offset": 15})


async def test_get_users_uc28_serialization_mapping_hides_private_fields() -> None:
    service, repo = make_service()
    repo.users = [make_user()]

    result = await service.get_users()
    dumped = result[0].model_dump()

    assert "password" not in dumped
    assert dumped["username"] == "demo"


async def test_get_users_uc29_structural_validation_precedes_business_rules() -> None:
    service, repo = make_service()
    repo.users = [
        make_broken_user_row(username=None, first_name="Bad", last_name="Type")
    ]

    with pytest.raises(ValidationError):
        await service.get_users()


async def test_get_users_uc30_architecture_boundary_uses_repository_protocol_only() -> (
    None
):
    service, repo = make_service()
    repo.users = [make_user()]

    result = await service.get_users()

    assert len(result) == 1
    assert repo.calls == [("get_all", {"limit": None, "offset": None})]
