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


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[5]


def _load(service: str) -> dict[str, Any]:
    path = _workspace_root() / "services" / service / "docs" / "asyncapi.yaml"
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
    notification = _load("notification-service")
    email = _load("email-service")

    for document in (backend, notification, email):
        assert document["asyncapi"] == "2.6.0"
        assert document["info"]["title"]
        assert document["info"]["version"]
        assert document["servers"]["jetstream"]["protocol"] == "nats"
        assert document["channels"]
        _assert_refs_resolve(document)

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


@pytest.mark.asyncio
async def test_backend_callback_publisher_matches_subject_headers_and_payload() -> None:
    client = RecordingNatsClient()
    settings = NatsSettings()
    publisher = CallbackRequestEventPublisher(
        client=cast(NatsJetstreamClient, client), settings=settings
    )
    equestrian_id = uuid4()
    callback_id = uuid4()

    event_id = await publisher.publish(
        payload=CallbackRequestedData(
            callback_request_id=callback_id,
            name="Owner",
            comment=None,
            phone="+79990000000",
        ),
        equestrian_id=equestrian_id,
    )

    call = client.calls[0]
    payload = CallbackRequestedData.model_validate_json(call["payload"])
    assert call["subject"] == "events.site.callback.requested"
    assert call["headers"] == {
        "Nats-Msg-Id": str(event_id),
        "X-Equestrian-Id": str(equestrian_id),
    }
    assert payload.callback_request_id == callback_id
