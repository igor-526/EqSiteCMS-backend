from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from clients.email_service.client import EmailServiceClient


class RecordingClient:
    def __init__(self, response: httpx.Response) -> None:
        self.response = response
        self.requests: list[dict] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, url: str, **kwargs):
        self.requests.append({"url": url, **kwargs})
        return self.response


@pytest.mark.asyncio
async def test_downstream_request_contains_no_peer_credential(monkeypatch) -> None:
    response = httpx.Response(
        201,
        json={"id": str(uuid4())},
        request=httpx.Request("POST", "http://email/emails"),
    )
    recording = RecordingClient(response)
    monkeypatch.setattr(httpx, "AsyncClient", lambda: recording)

    await EmailServiceClient(base_url="http://email").create_email(
        user_id=uuid4(), email="a@example.com"
    )

    request = recording.requests[0]
    headers = {key.lower(): value for key, value in request.get("headers", {}).items()}
    assert "authorization" not in headers
    assert "x-service-key" not in headers


def test_peer_compose_services_have_no_host_port_and_share_private_network() -> None:
    root = Path(__file__).resolve().parents[5]
    for name in ("docker-compose.email.yml", "docker-compose.notification.yml"):
        compose = (root / ".docker-compose" / name).read_text()
        assert "    ports:" not in compose
        assert '      - "8000"' in compose
        assert "      - eqsitecms_network" in compose
        assert "external: true" in compose
