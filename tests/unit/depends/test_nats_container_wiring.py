from typing import cast
from unittest.mock import AsyncMock

import pytest
from dependency_injector import providers

import main
from clients.nats.publisher import CallbackRequestEventPublisher
from containers import container
from depends.publishers import get_callback_request_event_publisher
from depends.utils import get_nats_client


def test_main_and_dependencies_use_one_shared_application_container() -> None:
    assert main.container is container
    assert get_callback_request_event_publisher.__globals__["container"] is container
    assert get_nats_client.__globals__["container"] is container


@pytest.mark.asyncio
async def test_lifespan_connects_the_same_client_used_by_publisher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    nats_client = AsyncMock()
    monkeypatch.setattr(main, "init_registry", AsyncMock())

    container.reset_singletons()
    with container.nats_client.override(providers.Object(nats_client)):
        container.callback_request_event_publisher.reset()
        async with main.lifespan(main.app):
            dependency_client = await get_nats_client()
            publisher = cast(
                CallbackRequestEventPublisher,
                get_callback_request_event_publisher(),
            )

            assert dependency_client is nats_client
            assert publisher._client is nats_client
            nats_client.connect.assert_awaited_once_with()
            nats_client.setup.assert_awaited_once_with()
            nats_client.close.assert_not_awaited()

        nats_client.close.assert_awaited_once_with()

    container.reset_singletons()
