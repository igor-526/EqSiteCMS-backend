import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock

import nats.errors
import pytest

from clients.nats.client import NatsJetstreamClient
from clients.nats.lifecycle import NatsConnectionErrorPolicy
from settings import NatsSettings


def make_client(
    drain_error: BaseException | None = None,
) -> tuple[NatsJetstreamClient, MagicMock]:
    client = NatsJetstreamClient(NatsSettings())
    connection = MagicMock()
    connection.is_closed = False
    connection.drain = AsyncMock(side_effect=drain_error)
    connection.close = AsyncMock()
    client._connection = connection
    client._jetstream = MagicMock()
    return client, connection


@pytest.mark.asyncio
async def test_close_drains_and_clears_state_on_healthy_connection() -> None:
    client, connection = make_client()

    await client.close()

    connection.drain.assert_awaited_once_with()
    connection.close.assert_not_awaited()
    assert client._connection is None
    assert client._jetstream is None


@pytest.mark.asyncio
async def test_close_survives_drain_while_reconnecting(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client, connection = make_client(nats.errors.ConnectionReconnectingError())

    with caplog.at_level(logging.WARNING):
        await client.close()

    connection.close.assert_awaited_once_with()
    assert client._connection is None
    assert client._jetstream is None
    assert not [record for record in caplog.records if record.levelno >= logging.ERROR]


@pytest.mark.asyncio
async def test_close_survives_drain_timeout() -> None:
    client, connection = make_client(asyncio.TimeoutError())

    await client.close()

    connection.close.assert_awaited_once_with()
    assert client._connection is None


@pytest.mark.asyncio
async def test_close_does_not_swallow_unrelated_errors() -> None:
    client, _ = make_client(RuntimeError("boom"))

    with pytest.raises(RuntimeError):
        await client.close()

    assert client._connection is None
    assert client._jetstream is None


@pytest.mark.asyncio
async def test_transient_failures_stay_below_error_level(
    caplog: pytest.LogCaptureFixture,
) -> None:
    policy = NatsConnectionErrorPolicy(service_name="test", report_after_attempts=3)

    with caplog.at_level(logging.WARNING):
        for _ in range(3):
            await policy.on_error(ConnectionRefusedError(111, "Connection refused"))

    assert not [record for record in caplog.records if record.levelno >= logging.ERROR]
    assert policy.escalated is False


@pytest.mark.asyncio
async def test_prolonged_outage_escalates_exactly_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    policy = NatsConnectionErrorPolicy(service_name="test", report_after_attempts=3)

    with caplog.at_level(logging.WARNING):
        for _ in range(10):
            await policy.on_error(ConnectionRefusedError(111, "Connection refused"))

    errors = [record for record in caplog.records if record.levelno >= logging.ERROR]
    assert len(errors) == 1
    assert errors[0].exc_info is not None
    assert policy.escalated is True


@pytest.mark.asyncio
async def test_reconnect_resets_incident_state(
    caplog: pytest.LogCaptureFixture,
) -> None:
    policy = NatsConnectionErrorPolicy(service_name="test", report_after_attempts=2)

    for _ in range(5):
        await policy.on_error(ConnectionRefusedError(111, "Connection refused"))
    await policy.on_reconnected()

    assert policy.consecutive_failures == 0
    assert policy.escalated is False

    caplog.clear()
    with caplog.at_level(logging.WARNING):
        for _ in range(2):
            await policy.on_error(ConnectionRefusedError(111, "Connection refused"))

    assert not [record for record in caplog.records if record.levelno >= logging.ERROR]


@pytest.mark.asyncio
async def test_disconnect_and_close_callbacks_do_not_escalate(
    caplog: pytest.LogCaptureFixture,
) -> None:
    policy = NatsConnectionErrorPolicy(service_name="test", report_after_attempts=1)

    with caplog.at_level(logging.INFO):
        await policy.on_disconnected()
        await policy.on_closed()

    assert not [record for record in caplog.records if record.levelno >= logging.ERROR]
    assert policy.consecutive_failures == 0
