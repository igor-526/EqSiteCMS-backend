from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from core.entities.callback_request import CallbackRequest, CallbackRequestStatus
from core.entities.equestrian import EquestrianContext
from core.exceptions.auth import ForbiddenError
from core.exceptions.base import ClientError, NotFoundError, UnprocessableEntityError
from core.schemas.callbackrequest import CallbackRequestCreateDto
from core.schemas.users import UserOutDto
from core.entities.user import UserScope
from core.services.callback_request import (
    CallbackRequestPublishError,
    CallbackRequestService,
)


def _user(role: str = "ADMIN", tenant=None) -> UserOutDto:
    return UserOutDto(
        id=uuid4(),
        equestrian_id=tenant or uuid4(),
        username="u",
        created_at=datetime.now(timezone.utc),
        scopes=[UserScope(scope_name=role, scope_description=role)],
    )


def _entity(tenant=None, **values):
    data = {"equestrian_id": tenant or uuid4(), "phone": "+7 (999) 111-22-33"}
    data.update(values)
    return CallbackRequest(**data)


@pytest.fixture
def dependencies():
    repository = AsyncMock()
    publisher = AsyncMock()
    service = CallbackRequestService(
        callback_request_event_publisher=publisher, repository=repository
    )
    return service, repository, publisher


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name,comment",
    [(None, None), ("И", None), (None, "Комментарий"), ("И" * 127, "Я" * 2000)],
)
async def test_create_defaults_nullable_and_boundaries(dependencies, name, comment):
    service, repository, publisher = dependencies
    tenant_id = uuid4()
    result = await service.create(
        data=CallbackRequestCreateDto(name=name, phone="1" * 63, comment=comment),
        equestrian_context=EquestrianContext(id=tenant_id, source="public"),
    )
    assert (
        result.status == 1
        and result.is_spam is False
        and result.notifications_delivered is False
    )
    assert result.name == name and result.comment == comment
    repository.create_and_commit.assert_awaited_once()
    persisted = repository.create_and_commit.await_args.args[0]
    assert (
        publisher.publish.await_args.kwargs["payload"].callback_request_id
        == persisted.id
    )
    assert persisted.equestrian_id == tenant_id
    assert publisher.publish.await_args.kwargs["payload"].equestrian_id == tenant_id
    assert (
        publisher.publish.await_args.kwargs["payload"].equestrian_id
        == persisted.equestrian_id
    )
    assert list(publisher.publish.await_args.kwargs) == ["payload"]


@pytest.mark.parametrize(
    "field,value",
    [("phone", ""), ("phone", "1" * 64), ("name", "x" * 128), ("comment", "x" * 2001)],
)
def test_create_structural_limits(field, value):
    with pytest.raises(ValidationError):
        CallbackRequestCreateDto(**({"phone": "+7"} | {field: value}))


@pytest.mark.asyncio
async def test_database_failure_does_not_publish(dependencies):
    service, repository, publisher = dependencies
    repository.create_and_commit.side_effect = RuntimeError("db")
    with pytest.raises(RuntimeError):
        await service.create(
            data=CallbackRequestCreateDto(phone="123"),
            equestrian_context=EquestrianContext(id=uuid4(), source="public"),
        )
    publisher.publish.assert_not_awaited()


@pytest.mark.asyncio
async def test_publish_failure_is_controlled_after_persist(dependencies):
    service, repository, publisher = dependencies
    publisher.publish.side_effect = RuntimeError("nats")
    with pytest.raises(CallbackRequestPublishError):
        await service.create(
            data=CallbackRequestCreateDto(phone="123"),
            equestrian_context=EquestrianContext(id=uuid4(), source="public"),
        )
    repository.create_and_commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_status_registry(dependencies):
    service, repository, _ = dependencies
    repository.get_statuses.return_value = [
        CallbackRequestStatus(id=1, name="Новая", color="#1677FF"),
        CallbackRequestStatus(id=2, name="Обработана", color="#52C41A"),
    ]
    result = await service.statuses()
    assert [(x.id, x.name) for x in result] == [(1, "Новая"), (2, "Обработана")]


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["ADMIN", "SUPERUSER"])
async def test_admin_roles_can_list(dependencies, role):
    service, repository, _ = dependencies
    repository.list_page.return_value = ([], 0)
    user = _user(role)
    result = await service.list(
        user=user,
        statuses=[1, 2],
        spam=[True, False],
        created_from=None,
        created_to=None,
        name="иван",
        phone="[0-9]+",
        comment="звонок",
        sort_by="status",
        direction="asc",
        limit=50,
        offset=0,
    )
    assert result.total == 0 and result.limit == 50
    assert repository.list_page.await_args.kwargs["equestrian_id"] == user.equestrian_id


@pytest.mark.asyncio
async def test_other_role_forbidden_before_query(dependencies):
    service, repository, _ = dependencies
    with pytest.raises(ForbiddenError):
        await service.list(
            user=_user("EDITOR"),
            statuses=None,
            spam=None,
            created_from=None,
            created_to=None,
            name=None,
            phone=None,
            comment=None,
            sort_by="status",
            direction="asc",
            limit=50,
            offset=0,
        )
    repository.list_page.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field,value",
    [
        ("name", "("),
        ("comment", "(?=x)"),
        ("phone", "abc"),
        ("name", "x" * 129),
        ("comment", r"(a)\1"),
        ("name", "(a+)+"),
        ("comment", "(.*)*"),
    ],
)
async def test_unsafe_regex_rejected_before_query(dependencies, field, value):
    service, repository, _ = dependencies
    args = {"name": None, "phone": None, "comment": None, field: value}
    with pytest.raises(UnprocessableEntityError):
        await service.list(
            user=_user(),
            statuses=None,
            spam=None,
            created_from=None,
            created_to=None,
            sort_by="status",
            direction="asc",
            limit=50,
            offset=0,
            **args,
        )
    repository.list_page.assert_not_awaited()


@pytest.mark.asyncio
async def test_empty_search_normalized(dependencies):
    service, repository, _ = dependencies
    repository.list_page.return_value = ([], 0)
    await service.list(
        user=_user(),
        statuses=None,
        spam=None,
        created_from=None,
        created_to=None,
        name=" ",
        phone="",
        comment=None,
        sort_by="created_at",
        direction="desc",
        limit=1,
        offset=2,
    )
    assert repository.list_page.await_args.kwargs["name"] is None


@pytest.mark.asyncio
async def test_invalid_date_range_rejected(dependencies):
    service, repository, _ = dependencies
    now = datetime.now(timezone.utc)
    with pytest.raises(ClientError):
        await service.list(
            user=_user(),
            statuses=None,
            spam=None,
            created_from=now,
            created_to=now.replace(year=now.year - 1),
            name=None,
            phone=None,
            comment=None,
            sort_by="status",
            direction="asc",
            limit=50,
            offset=0,
        )
    repository.list_page.assert_not_awaited()


@pytest.mark.asyncio
async def test_detail_tenant_scope_and_non_disclosure(dependencies):
    service, repository, _ = dependencies
    user = _user()
    repository.get_by_id.return_value = None
    with pytest.raises(NotFoundError):
        await service.detail(id=uuid4(), user=user)
    assert repository.get_by_id.await_args.kwargs["equestrian_id"] == user.equestrian_id


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["ADMIN", "SUPERUSER"])
async def test_seeded_status_update(dependencies, role):
    service, repository, _ = dependencies
    user = _user(role)
    repository.status_exists.return_value = True
    repository.set_status.return_value = _entity(user.equestrian_id, status=2)
    result = await service.set_status(id=uuid4(), status=2, user=user)
    assert result.status == 2


@pytest.mark.asyncio
async def test_unknown_status_does_not_mutate(dependencies):
    service, repository, _ = dependencies
    repository.status_exists.return_value = False
    with pytest.raises(ClientError):
        await service.set_status(id=uuid4(), status=3, user=_user())
    repository.set_status.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("is_spam,status", [(True, 2), (False, 2)])
async def test_spam_transitions(dependencies, is_spam, status):
    service, repository, _ = dependencies
    user = _user()
    repository.set_spam.return_value = _entity(
        user.equestrian_id, is_spam=is_spam, status=status
    )
    result = await service.set_spam(id=uuid4(), is_spam=is_spam, user=user)
    assert result.is_spam is is_spam and result.status == status


@pytest.mark.asyncio
async def test_service_mutation_is_not_tenant_scoped(dependencies):
    service, repository, _ = dependencies
    repository.set_spam.return_value = _entity(is_spam=True, status=2)
    await service.set_spam(id=uuid4(), is_spam=True)
    assert repository.set_spam.await_args.kwargs["equestrian_id"] is None


@pytest.mark.asyncio
async def test_delivery_true_is_idempotent_and_false_rejected(dependencies):
    service, repository, _ = dependencies
    repository.set_delivery.return_value = _entity(notifications_delivered=True)
    first = await service.confirm_delivery(id=uuid4(), delivered=True)
    assert first.notifications_delivered is True
    with pytest.raises(ClientError):
        await service.confirm_delivery(id=uuid4(), delivered=False)
    assert repository.set_delivery.await_count == 1
