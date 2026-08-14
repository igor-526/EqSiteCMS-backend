"""Tests for horse service permission checks."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from core.entities.horse_service import HorseServiceEntity
from core.entities.price import PriceFormatter
from core.entities.user import UserScope
from core.exceptions.base import ClientError
from core.schemas.horse_service import HorseServiceCreateDto, HorseServiceUpdateDto
from core.schemas.users import UserOutDto
from core.services.horse_service import HorseServiceService

pytestmark = pytest.mark.asyncio


class FakeHorseServiceRepository:
    def __init__(self) -> None:
        self.by_id: dict[UUID, HorseServiceEntity] = {}
        self.by_slug: dict[str, HorseServiceEntity] = {}
        self.by_name: dict[str, HorseServiceEntity] = {}
        self.calls: list[tuple[str, Any]] = []

    def add(self, entity: HorseServiceEntity) -> HorseServiceEntity:
        self.by_id[entity.id] = entity
        assert entity.slug is not None
        self.by_slug[entity.slug] = entity
        self.by_name[entity.name] = entity
        return entity

    async def get_by_slug_or_id(
        self, slug_or_id: str | UUID, *, equestrian_id: UUID
    ) -> HorseServiceEntity | None:
        self.calls.append(("get_by_slug_or_id", slug_or_id))
        if isinstance(slug_or_id, UUID):
            return self.by_id.get(slug_or_id)
        return self.by_slug.get(slug_or_id)

    async def find_by_name(
        self, name: str, *, equestrian_id: UUID
    ) -> HorseServiceEntity | None:
        self.calls.append(("find_by_name", name))
        return self.by_name.get(name)

    async def find_by_slug(
        self, slug: str, *, equestrian_id: UUID
    ) -> HorseServiceEntity | None:
        self.calls.append(("find_by_slug", slug))
        return self.by_slug.get(slug)

    async def create(self, entity: HorseServiceEntity) -> HorseServiceEntity:
        self.calls.append(("create", entity))
        self.add(entity)
        return entity

    async def update(self, entity: HorseServiceEntity) -> HorseServiceEntity:
        self.calls.append(("update", entity))
        self.add(entity)
        return entity

    async def delete(self, id: UUID, *, equestrian_id: UUID) -> None:
        self.calls.append(("delete", id))
        entity = self.by_id.pop(id, None)
        if entity is not None:
            assert entity.slug is not None
            self.by_slug.pop(entity.slug, None)
            self.by_name.pop(entity.name, None)


def make_horse_service_entity(**overrides: Any) -> HorseServiceEntity:
    data = {
        "id": uuid4(),
        "name": "Тестовая услуга",
        "slug": "testovaya-usluga",
        "description": "Описание",
        "price": 1000,
        "price_formatter": PriceFormatter.equal,
        "page_data": "<div></div>",
        "equestrian_id": uuid4(),
    }
    data.update(overrides)
    return HorseServiceEntity(**data)


def make_user(*, scope_name: str) -> UserOutDto:
    """Create a test user with the given scope."""
    return UserOutDto(
        id=uuid4(),
        equestrian_id=uuid4(),
        username="testuser",
        created_at=datetime.now(),
        scopes=[
            UserScope(scope_name=scope_name, scope_description=f"{scope_name} scope")
        ],
    )


@pytest.fixture
def repository() -> FakeHorseServiceRepository:
    return FakeHorseServiceRepository()


@pytest.fixture
def service(repository: FakeHorseServiceRepository) -> HorseServiceService:
    return HorseServiceService(horse_service_repository=repository)


@pytest.fixture
def equestrian_context():
    from core.entities.equestrian import EquestrianContext

    return EquestrianContext(id=uuid4(), source="test")


# Task 3.1: Создание услуги пользователем с DEVELOPER scope успешно
async def test_create_service_with_developer_scope(
    service: HorseServiceService,
    repository: FakeHorseServiceRepository,
    equestrian_context,
):
    user = make_user(scope_name="DEVELOPER")
    data = HorseServiceCreateDto(name="Новая услуга", price=1000)

    result = await service.create(
        data, equestrian_context=equestrian_context, user=user
    )

    assert result.name == "Новая услуга"
    assert len(repository.calls) > 0
    assert repository.calls[-1][0] == "create"


# Task 3.2: Создание услуги пользователем с SUPERUSER scope успешно
async def test_create_service_with_superuser_scope(
    service: HorseServiceService,
    repository: FakeHorseServiceRepository,
    equestrian_context,
):
    user = make_user(scope_name="SUPERUSER")
    data = HorseServiceCreateDto(name="Новая услуга", price=1000)

    result = await service.create(
        data, equestrian_context=equestrian_context, user=user
    )

    assert result.name == "Новая услуга"
    assert len(repository.calls) > 0
    assert repository.calls[-1][0] == "create"


# Task 3.3: Создание услуги пользователем с ADMIN scope возвращает 403
async def test_create_service_with_admin_scope_returns_403(
    service: HorseServiceService,
    repository: FakeHorseServiceRepository,
    equestrian_context,
):
    user = make_user(scope_name="ADMIN")
    data = HorseServiceCreateDto(name="Новая услуга", price=1000)

    with pytest.raises(ClientError, match="Недостаточно прав для выполнения операции"):
        await service.create(data, equestrian_context=equestrian_context, user=user)

    # Verify no repository calls were made
    assert len(repository.calls) == 0


# Task 3.4: Обновление услуги пользователем с DEVELOPER scope успешно
async def test_update_service_with_developer_scope(
    service: HorseServiceService,
    repository: FakeHorseServiceRepository,
    equestrian_context,
):
    user = make_user(scope_name="DEVELOPER")
    entity = make_horse_service_entity(equestrian_id=equestrian_context.id)
    repository.add(entity)

    data = HorseServiceUpdateDto(name="Обновленная услуга")
    result = await service.update(
        str(entity.id), data, equestrian_context=equestrian_context, user=user
    )

    assert result.name == "Обновленная услуга"


# Task 3.5: Обновление услуги пользователем с ADMIN scope возвращает 403
async def test_update_service_name_with_admin_scope_returns_403(
    service: HorseServiceService,
    repository: FakeHorseServiceRepository,
    equestrian_context,
):
    user = make_user(scope_name="ADMIN")
    entity = make_horse_service_entity(equestrian_id=equestrian_context.id)
    repository.add(entity)

    data = HorseServiceUpdateDto(name="Обновленная услуга")
    with pytest.raises(
        ClientError, match="Недостаточно прав для изменения наименования"
    ):
        await service.update(
            str(entity.id), data, equestrian_context=equestrian_context, user=user
        )

    # Verify the entity was not updated
    assert repository.by_id[entity.id].name == "Тестовая услуга"


# Task 3.5: Обновление услуги пользователем с ADMIN scope (кроме наименования) успешно
async def test_update_service_description_with_admin_scope(
    service: HorseServiceService,
    repository: FakeHorseServiceRepository,
    equestrian_context,
):
    user = make_user(scope_name="ADMIN")
    entity = make_horse_service_entity(equestrian_id=equestrian_context.id)
    repository.add(entity)

    data = HorseServiceUpdateDto(description="Новое описание")
    result = await service.update(
        str(entity.id), data, equestrian_context=equestrian_context, user=user
    )

    assert result.description == "Новое описание"
    assert result.name == "Тестовая услуга"  # Name should not change


# Task 3.6: Удаление услуги пользователем с DEVELOPER scope успешно
async def test_delete_service_with_developer_scope(
    service: HorseServiceService,
    repository: FakeHorseServiceRepository,
    equestrian_context,
):
    user = make_user(scope_name="DEVELOPER")
    entity = make_horse_service_entity(equestrian_id=equestrian_context.id)
    repository.add(entity)

    await service.delete(
        str(entity.id), equestrian_context=equestrian_context, user=user
    )

    assert entity.id not in repository.by_id


# Task 3.7: Удаление услуги пользователем с ADMIN scope возвращает 403
async def test_delete_service_with_admin_scope_returns_403(
    service: HorseServiceService,
    repository: FakeHorseServiceRepository,
    equestrian_context,
):
    user = make_user(scope_name="ADMIN")
    entity = make_horse_service_entity(equestrian_id=equestrian_context.id)
    repository.add(entity)

    with pytest.raises(ClientError, match="Недостаточно прав для выполнения операции"):
        await service.delete(
            str(entity.id), equestrian_context=equestrian_context, user=user
        )

    # Verify the entity was not deleted
    assert entity.id in repository.by_id


# Task 3.8: Чтение услуги пользователем с ADMIN scope успешно (без проверки прав)
async def test_read_service_with_admin_scope_succeeds(
    service: HorseServiceService,
    repository: FakeHorseServiceRepository,
    equestrian_context,
):
    entity = make_horse_service_entity(equestrian_id=equestrian_context.id)
    repository.add(entity)

    result = await service.get_by_slug_or_id(
        str(entity.id), equestrian_context=equestrian_context
    )

    assert result.id == entity.id


# Task 3.5.2: Обновление услуги пользователем с ADMIN scope с тем же наименованием успешно
async def test_update_service_same_name_with_admin_scope(
    service: HorseServiceService,
    repository: FakeHorseServiceRepository,
    equestrian_context,
):
    user = make_user(scope_name="ADMIN")
    entity = make_horse_service_entity(equestrian_id=equestrian_context.id)
    repository.add(entity)

    # Отправляем запрос с тем же наименованием - не должно быть ошибки
    data = HorseServiceUpdateDto(name="Тестовая услуга", description="Новое описание")
    result = await service.update(
        str(entity.id), data, equestrian_context=equestrian_context, user=user
    )

    assert result.description == "Новое описание"
    assert result.name == "Тестовая услуга"  # Name should remain the same
