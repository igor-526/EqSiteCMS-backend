from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import ValidationError
from sentry_sdk.types import Event

from settings import SentrySettings
from utils import configure_sentry as sentry_module
from utils import observability


def test_disabled_sentry_is_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    init = Mock()
    monkeypatch.setattr(sentry_module.sentry_sdk, "init", init)
    sentry_module.configure_sentry(SentrySettings(SENTRY_ENABLED=False))
    init.assert_not_called()


@pytest.mark.parametrize("rate", [0.0, 1.0])
def test_enabled_sentry_passes_metadata_once(
    monkeypatch: pytest.MonkeyPatch, rate: float
) -> None:
    init = Mock()
    monkeypatch.setattr(sentry_module.sentry_sdk, "init", init)
    config = SentrySettings(
        SENTRY_ENABLED=True,
        SENTRY_DSN="https://public@example.invalid/1",
        SENTRY_ENVIRONMENT="qa",
        SENTRY_TRACES_SAMPLE_RATE=rate,
        SENTRY_RELEASE=" release-1 ",
    )
    sentry_module.configure_sentry(config)
    init.assert_called_once()
    kwargs = init.call_args.kwargs
    assert kwargs["dsn"] == config.sentry_dsn
    assert kwargs["environment"] == "qa"
    assert kwargs["release"] == "release-1"
    assert kwargs["traces_sample_rate"] == rate
    assert kwargs["send_default_pii"] is False
    assert kwargs["max_request_body_size"] == "never"
    assert len(kwargs["integrations"]) == 2


@pytest.mark.parametrize("rate", [-0.01, 1.01])
def test_invalid_sample_rate_is_rejected(rate: float) -> None:
    with pytest.raises(ValidationError):
        SentrySettings(SENTRY_TRACES_SAMPLE_RATE=rate)


def test_enabled_sentry_requires_non_blank_dsn() -> None:
    with pytest.raises(ValidationError, match="SENTRY_DSN"):
        SentrySettings(SENTRY_ENABLED=True, SENTRY_DSN="  ")


def test_blank_release_is_normalized() -> None:
    assert SentrySettings(SENTRY_RELEASE="  ").sentry_release is None


def test_before_send_removes_credentials_and_body() -> None:
    event: Event = {
        "request": {
            "headers": {"Authorization": "secret", "Cookie": "session=secret"},
            "data": {"password": "secret"},
        },
        "extra": {"smtp_password": "secret", "safe": "value"},
    }
    sanitized = sentry_module.before_send(event, {})
    assert sanitized["request"]["headers"] == {
        "Authorization": "[Filtered]",
        "Cookie": "[Filtered]",
    }
    assert "data" not in sanitized["request"]
    assert sanitized["extra"] == {"smtp_password": "[Filtered]", "safe": "value"}


def test_metrics_runtime_uses_default_registry_and_closes_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server, thread = Mock(), Mock()
    starter = Mock(return_value=(server, thread))
    monkeypatch.setattr(observability, "start_http_server", starter)
    runtime = observability.start_metrics_runtime(environment="production")
    assert runtime is not None
    assert starter.call_args.kwargs == {
        "port": 9000,
        "addr": "0.0.0.0",
        "registry": observability.REGISTRY,
    }
    runtime.close()
    runtime.close()
    server.shutdown.assert_called_once_with()
    server.server_close.assert_called_once_with()
    thread.join.assert_called_once_with()


@pytest.mark.parametrize("environment", ["development", "test", "Production-ish"])
def test_metrics_listener_is_production_only(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    starter = Mock()
    monkeypatch.setattr(observability, "start_http_server", starter)
    assert observability.start_metrics_runtime(environment=environment) is None
    starter.assert_not_called()


async def test_lifespan_keeps_nats_failure_and_does_not_start_metrics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import main

    nats = Mock(connect=AsyncMock(side_effect=RuntimeError("nats unavailable")))
    monkeypatch.setattr(main, "init_registry", AsyncMock())
    monkeypatch.setattr(main.container, "nats_client", Mock(return_value=nats))
    start_metrics = Mock()
    monkeypatch.setattr(main, "start_metrics_runtime", start_metrics)
    with pytest.raises(RuntimeError, match="nats unavailable"):
        async with main.lifespan(main.app):
            pass
    start_metrics.assert_not_called()


async def test_lifespan_closes_metrics_and_nats_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import main

    nats = Mock(connect=AsyncMock(), setup=AsyncMock(), close=AsyncMock())
    runtime = Mock()
    monkeypatch.setattr(main, "init_registry", AsyncMock())
    monkeypatch.setattr(main.container, "nats_client", Mock(return_value=nats))
    monkeypatch.setattr(main, "start_metrics_runtime", Mock(return_value=runtime))
    async with main.lifespan(main.app):
        pass
    runtime.close.assert_called_once_with()
    nats.close.assert_awaited_once_with()
