"""UT-YX-06..10: use cases с fake peer по Protocol, без HTTP/БД."""

from datetime import datetime, timezone
from unittest.mock import call, create_autospec
from uuid import uuid4

import pytest

from clients.yandex_service.schemas import (
    YandexAccountOutDto,
    YandexAccountsOutDto,
    YandexAuthCodeInDto,
    YandexAuthLinkOutDto,
    YandexMetricaConnectedCounterOutDto,
    YandexMetricaConnectionOutDto,
    YandexMetricaCountersOutDto,
    YandexMetricaSetConnectionInDto,
)
from core.exceptions.auth import ForbiddenError
from core.exceptions.base import ClientError, NotFoundError
from core.protocols.yandex_service import YandexServiceClientProtocol
from core.schemas.users import UserOutDto
from core.services.yandex_proxy import YandexProxyService


@pytest.fixture
def actor():
    return UserOutDto(
        id=uuid4(),
        equestrian_id=uuid4(),
        username="admin",
        created_at=datetime.now(timezone.utc),
    )


def account(account_id=None):
    return YandexAccountOutDto(
        id=account_id or uuid4(),
        yandex_id="123",
        yandex_login="test",
        display_name="Test",
    )


@pytest.fixture
def client():
    fake = create_autospec(YandexServiceClientProtocol, instance=True)
    fake.list_accounts.return_value = YandexAccountsOutDto(items=[], total=0)
    fake.get_connection.return_value = YandexMetricaConnectedCounterOutDto(counter=None)
    return fake


@pytest.mark.parametrize("operation", ["delete", "counters", "set"])
@pytest.mark.parametrize("owned", [False, True])
async def test_ut_yx_06_ownership(actor, client, operation, owned):
    target = account()
    client.list_accounts.return_value = YandexAccountsOutDto(
        items=[target] if owned else [account()], total=1
    )
    service = YandexProxyService(client)

    async def invoke():
        if operation == "delete":
            await service.delete_account(actor=actor, account_id=target.id)
        elif operation == "counters":
            await service.list_counters(actor=actor, account_id=target.id)
        else:
            await service.set_connection(
                actor=actor,
                data=YandexMetricaSetConnectionInDto(
                    yandex_account_id=target.id, counter_id="999"
                ),
            )

    if owned:
        await invoke()
    else:
        with pytest.raises(NotFoundError, match="Аккаунт Яндекс не найден"):
            await invoke()
        client.delete_account.assert_not_awaited()
        client.list_counters.assert_not_awaited()
        client.set_connection.assert_not_awaited()
    client.list_accounts.assert_awaited_once_with(
        equestrian_id=actor.equestrian_id, limit=100, offset=0
    )
    if owned and operation == "set":
        client.set_connection.assert_awaited_once_with(
            equestrian_id=actor.equestrian_id,
            yandex_account_id=target.id,
            counter_id="999",
        )
        client.list_counters.assert_not_awaited()


@pytest.mark.parametrize("found", [True, False])
async def test_ut_yx_07_second_page_and_total_bound(actor, client, found):
    target = account()
    client.list_accounts.side_effect = [
        YandexAccountsOutDto(items=[account() for _ in range(100)], total=101),
        YandexAccountsOutDto(items=[target if found else account()], total=101),
    ]
    service = YandexProxyService(client)
    if found:
        await service.delete_account(actor=actor, account_id=target.id)
        client.delete_account.assert_awaited_once_with(account_id=target.id)
    else:
        with pytest.raises(NotFoundError):
            await service.delete_account(actor=actor, account_id=target.id)
        client.delete_account.assert_not_awaited()
    assert client.list_accounts.await_args_list == [
        call(equestrian_id=actor.equestrian_id, limit=100, offset=0),
        call(equestrian_id=actor.equestrian_id, limit=100, offset=100),
    ]


@pytest.mark.parametrize("total", [0, 1000])
async def test_ut_yx_07_empty_page_stops(actor, client, total):
    client.list_accounts.return_value = YandexAccountsOutDto(items=[], total=total)
    with pytest.raises(NotFoundError):
        await YandexProxyService(client).delete_account(actor=actor, account_id=uuid4())
    assert client.list_accounts.await_count == 1
    client.delete_account.assert_not_awaited()


@pytest.mark.parametrize("state", ["foreign", "not-a-uuid", "own"])
async def test_ut_yx_08_state(actor, client, state):
    data = YandexAuthCodeInDto(
        code="code",
        state=(
            str(actor.equestrian_id)
            if state == "own"
            else (str(uuid4()) if state == "foreign" else state)
        ),
    )
    if state == "own":
        await YandexProxyService(client).exchange_code(actor=actor, data=data)
        client.exchange_code.assert_awaited_once_with(
            equestrian_id=actor.equestrian_id, code="code"
        )
    else:
        with pytest.raises(ForbiddenError):
            await YandexProxyService(client).exchange_code(actor=actor, data=data)
        client.exchange_code.assert_not_awaited()


@pytest.mark.parametrize("field", ["code", "state"])
@pytest.mark.parametrize("blank", ["", " ", "\t\n"])
async def test_empty_auth_fields_rejected_by_service(actor, client, field, blank):
    payload = {"code": "code", "state": str(actor.equestrian_id), field: blank}
    data = YandexAuthCodeInDto.model_validate(payload)
    with pytest.raises(ClientError) as exc:
        await YandexProxyService(client).exchange_code(actor=actor, data=data)
    assert type(exc.value) is ClientError
    assert not client.mock_calls


@pytest.mark.parametrize(
    "counter", ["", " ", "12a", "1" * 32, "123\n", "１２３", "-1", "1.2"]
)
async def test_invalid_counter_rejected_by_service_before_ownership(
    actor, client, counter
):
    data = YandexMetricaSetConnectionInDto(
        yandex_account_id=uuid4(), counter_id=counter
    )
    with pytest.raises(ClientError) as exc:
        await YandexProxyService(client).set_connection(actor=actor, data=data)
    assert type(exc.value) is ClientError
    assert not client.mock_calls


@pytest.mark.parametrize("counter", ["0", "9", "0" * 31, "9" * 31, 123])
async def test_valid_counter_boundaries_pass_ownership(actor, client, counter):
    target = account()
    client.list_accounts.return_value = YandexAccountsOutDto(items=[target], total=1)
    data = YandexMetricaSetConnectionInDto.model_validate(
        {"yandex_account_id": target.id, "counter_id": counter}
    )
    await YandexProxyService(client).set_connection(actor=actor, data=data)
    client.list_accounts.assert_awaited_once_with(
        equestrian_id=actor.equestrian_id, limit=100, offset=0
    )
    client.set_connection.assert_awaited_once_with(
        equestrian_id=actor.equestrian_id,
        yandex_account_id=target.id,
        counter_id=str(counter),
    )
    client.list_counters.assert_not_awaited()


@pytest.mark.parametrize("linked", [True, False])
async def test_ut_yx_09_idempotent_delete(actor, client, linked):
    connection = YandexMetricaConnectionOutDto(
        id=uuid4(), counter_id="123", yandex_account=account()
    )
    client.get_connection.return_value = YandexMetricaConnectedCounterOutDto(
        counter=connection if linked else None
    )
    service = YandexProxyService(client)
    await service.delete_connection(actor=actor)
    client.get_connection.assert_awaited_once_with(equestrian_id=actor.equestrian_id)
    if linked:
        client.delete_connection.assert_awaited_once_with(
            counter_record_id=connection.id
        )
    else:
        client.delete_connection.assert_not_awaited()
    client.get_connection.return_value = YandexMetricaConnectedCounterOutDto(
        counter=None
    )
    await service.delete_connection(actor=actor)
    assert client.delete_connection.await_count == int(linked)


async def test_ut_yx_10_all_use_cases_session_tenant(actor, client):
    target = account()
    connection = YandexMetricaConnectionOutDto(
        id=uuid4(), counter_id="123", yandex_account=target
    )
    client.get_auth_link.return_value = YandexAuthLinkOutDto(
        auth_link="https://oauth.yandex.ru/"
    )
    client.exchange_code.return_value = target
    client.list_accounts.return_value = YandexAccountsOutDto(items=[target], total=1)
    client.list_counters.return_value = YandexMetricaCountersOutDto(items=[], total=0)
    client.get_connection.return_value = YandexMetricaConnectedCounterOutDto(
        counter=connection
    )
    client.set_connection.return_value = connection
    service = YandexProxyService(client)
    foreign = str(uuid4())
    await service.get_auth_link(actor=actor)
    data = YandexAuthCodeInDto.model_validate(
        {"code": "code", "state": str(actor.equestrian_id), "equestrian_id": foreign}
    )
    assert await service.exchange_code(actor=actor, data=data) == target
    assert (
        await service.list_accounts(actor=actor, search="name", limit=1000, offset=-1)
        == client.list_accounts.return_value
    )
    await service.delete_account(actor=actor, account_id=target.id)
    await service.list_counters(
        actor=actor, account_id=target.id, search="site", limit=0, offset=-1
    )
    assert (
        await service.get_connection(actor=actor) == client.get_connection.return_value
    )
    assert (
        await service.set_connection(
            actor=actor,
            data=YandexMetricaSetConnectionInDto.model_validate(
                {
                    "yandex_account_id": target.id,
                    "counter_id": 123,
                    "equestrian_id": foreign,
                }
            ),
        )
        == connection
    )
    await service.delete_connection(actor=actor)
    for name in (
        "get_auth_link",
        "exchange_code",
        "list_accounts",
        "get_connection",
        "set_connection",
    ):
        for invocation in getattr(client, name).await_args_list:
            assert invocation.kwargs["equestrian_id"] == actor.equestrian_id
    client.list_accounts.assert_any_await(
        equestrian_id=actor.equestrian_id, search="name", limit=100, offset=0
    )
    client.list_counters.assert_awaited_once_with(
        account_id=target.id, search="site", limit=1, offset=0
    )
    client.delete_connection.assert_awaited_once_with(counter_record_id=connection.id)
    client.delete_account.assert_awaited_once_with(account_id=target.id)
