from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pytest
import yaml

from clients.nats.client import NatsJetstreamClient
from clients.nats.publisher import CallbackRequestEventPublisher
from core.schemas.messaging import CallbackRequestedData
from settings import NatsSettings


class RecordingNatsClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def publish(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


def _find_backend_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "pyproject.toml").is_file() and (
            candidate / "docs" / "asyncapi.yaml"
        ).is_file():
            return candidate
    raise FileNotFoundError(f"backend root not found from {start}")


def _find_workspace_root(start: Path) -> Path | None:
    for candidate in (start, *start.parents):
        if (candidate / "services" / "backend" / "docs" / "asyncapi.yaml").is_file():
            return candidate
    return None


def _load(service: str) -> dict[str, Any]:
    source = Path(__file__).resolve()
    if service == "backend":
        path = _find_backend_root(source) / "docs" / "asyncapi.yaml"
    else:
        workspace = _find_workspace_root(source)
        if workspace is None:
            raise FileNotFoundError(
                f"{service} AsyncAPI is unavailable in standalone backend checkout"
            )
        path = workspace / "services" / service / "docs" / "asyncapi.yaml"
    return cast(dict[str, Any], yaml.safe_load(path.read_text()))


def _resolve(document: dict[str, Any], reference: str) -> Any:
    current: Any = document
    for part in reference.removeprefix("#/").split("/"):
        current = current[part]
    return current


def _message(document: dict[str, Any], channel: str, operation: str) -> dict[str, Any]:
    reference = document["channels"][channel][operation]["message"]["$ref"]
    return cast(dict[str, Any], _resolve(document, reference))


def _assert_refs_resolve(document: dict[str, Any], value: Any | None = None) -> None:
    current = document if value is None else value
    if isinstance(current, dict):
        reference = current.get("$ref")
        if isinstance(reference, str):
            _resolve(document, reference)
        for nested in current.values():
            _assert_refs_resolve(document, nested)
    elif isinstance(current, list):
        for nested in current:
            _assert_refs_resolve(document, nested)


def _payload(document: dict[str, Any], channel: str, operation: str) -> dict[str, Any]:
    message = _message(document, channel, operation)
    return cast(dict[str, Any], _resolve(document, message["payload"]["$ref"]))


def test_all_asyncapi_documents_are_structurally_valid_and_aggregate_matches() -> None:
    backend = _load("backend")
    workspace = _find_workspace_root(Path(__file__).resolve())
    notification = _load("notification-service") if workspace is not None else None
    email = _load("email-service") if workspace is not None else None

    for document in (backend, notification, email):
        if document is None:
            continue
        assert document["asyncapi"] == "2.6.0"
        assert document["info"]["title"]
        assert document["info"]["version"]
        assert document["servers"]["jetstream"]["protocol"] == "nats"
        assert document["channels"]
        _assert_refs_resolve(document)

    if notification is None or email is None:
        return

    callback = "events.site.callback.requested"
    command = "commands.notification.email.send"
    assert _payload(backend, callback, "publish") == _payload(
        notification, callback, "subscribe"
    )
    assert _payload(notification, command, "publish") == _payload(
        email, command, "subscribe"
    )
    assert backend["channels"][callback]["x-jetstream-stream"] == "SITE_EVENTS"
    assert notification["channels"][callback]["x-jetstream-consumer"]["durable"] == (
        "notification-service-callback-requested"
    )
    assert notification["channels"][command]["x-jetstream-stream"] == (
        "NOTIFICATION_COMMANDS"
    )
    assert email["channels"][command]["x-jetstream-consumer"]["durable"] == (
        "notification-service-commands-send-email"
    )


def test_root_discovery_supports_standalone_and_nested_checkout(
    tmp_path: Path, monkeypatch
) -> None:
    workspace = tmp_path / "arbitrary-workspace"
    backend = workspace / "services" / "backend"
    test_file = backend / "tests" / "unit" / "test_file.py"
    test_file.parent.mkdir(parents=True)
    (backend / "docs").mkdir()
    (backend / "docs" / "asyncapi.yaml").touch()
    (backend / "pyproject.toml").touch()
    monkeypatch.chdir(tmp_path)

    assert _find_backend_root(test_file) == backend
    assert _find_workspace_root(test_file) == workspace

    standalone = tmp_path / "standalone-backend"
    standalone_test = standalone / "tests" / "unit" / "test_file.py"
    standalone_test.parent.mkdir(parents=True)
    (standalone / "docs").mkdir()
    (standalone / "docs" / "asyncapi.yaml").touch()
    (standalone / "pyproject.toml").touch()

    assert _find_backend_root(standalone_test) == standalone
    assert _find_workspace_root(standalone_test) is None


@pytest.mark.asyncio
async def test_backend_callback_publisher_matches_subject_headers_and_payload() -> None:
    client = RecordingNatsClient()
    settings = NatsSettings()
    publisher = CallbackRequestEventPublisher(
        client=cast(NatsJetstreamClient, client), settings=settings
    )
    callback_id = uuid4()

    event_id = await publisher.publish(
        payload=CallbackRequestedData(
            callback_request_id=callback_id,
            name="Owner",
            comment=None,
            phone="+79990000000",
        ),
    )

    call = client.calls[0]
    payload = CallbackRequestedData.model_validate_json(call["payload"])
    assert call["subject"] == "events.site.callback.requested"
    assert call["headers"] == {"Nats-Msg-Id": str(event_id)}
    assert "equestrian_id" not in payload.model_dump()
    assert payload.callback_request_id == callback_id
