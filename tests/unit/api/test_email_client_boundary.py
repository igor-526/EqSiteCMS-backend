from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from clients.email_service.client import EmailServiceClient


def _find_workspace_root(start: Path) -> Path | None:
    """Find optional orchestration root without assuming checkout depth or name."""
    for candidate in (start, *start.parents):
        if (candidate / ".docker-compose").is_dir():
            return candidate
    return None


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

    async def get(self, url: str, **kwargs):
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
    root = _find_workspace_root(Path(__file__).resolve())
    if root is None:
        pytest.skip(
            "orchestration compose files are not part of standalone backend checkout"
        )
    for name in ("docker-compose.email.yml", "docker-compose.notification.yml"):
        compose = (root / ".docker-compose" / name).read_text()
        assert "    ports:" not in compose
        assert '      - "8000"' in compose
        assert "      - eqsitecms_network" in compose
        assert "external: true" in compose


def test_workspace_discovery_supports_nested_checkout_and_ignores_cwd(
    tmp_path: Path, monkeypatch
) -> None:
    workspace = tmp_path / "checkout-with-arbitrary-name"
    test_file = workspace / "services" / "backend" / "tests" / "unit" / "test_file.py"
    (workspace / ".docker-compose").mkdir(parents=True)
    test_file.parent.mkdir(parents=True)
    test_file.touch()
    monkeypatch.chdir(tmp_path)

    assert _find_workspace_root(test_file) == workspace


def test_workspace_discovery_allows_standalone_service_checkout(tmp_path: Path) -> None:
    test_file = tmp_path / "backend-checkout" / "tests" / "unit" / "test_file.py"
    test_file.parent.mkdir(parents=True)
    test_file.touch()

    assert _find_workspace_root(test_file) is None


@pytest.mark.asyncio
async def test_read_owner_uses_existing_filtered_list_contract(monkeypatch) -> None:
    user_id = uuid4()
    response = httpx.Response(
        200,
        json=[
            {
                "id": str(uuid4()),
                "user_id": str(user_id),
                "email": "owner@example.com",
                "approved": True,
            }
        ],
        request=httpx.Request("GET", "http://email/emails"),
    )
    recording = RecordingClient(response)
    monkeypatch.setattr(httpx, "AsyncClient", lambda: recording)

    result = await EmailServiceClient(base_url="http://email").get_email(
        user_id=user_id
    )

    assert result is not None and result.user_id == user_id
    assert recording.requests == [
        {
            "url": "http://email/emails",
            "params": {"user_ids": str(user_id)},
        }
    ]


@pytest.mark.asyncio
async def test_read_owner_empty_list_means_missing(monkeypatch) -> None:
    response = httpx.Response(
        200, json=[], request=httpx.Request("GET", "http://email/emails")
    )
    monkeypatch.setattr(httpx, "AsyncClient", lambda: RecordingClient(response))

    assert (
        await EmailServiceClient(base_url="http://email").get_email(user_id=uuid4())
        is None
    )


@pytest.mark.asyncio
async def test_read_owner_rejects_foreign_response(monkeypatch) -> None:
    response = httpx.Response(
        200,
        json=[
            {
                "id": str(uuid4()),
                "user_id": str(uuid4()),
                "email": "foreign@example.com",
                "approved": True,
            }
        ],
        request=httpx.Request("GET", "http://email/emails"),
    )
    monkeypatch.setattr(httpx, "AsyncClient", lambda: RecordingClient(response))

    with pytest.raises(ValueError, match="ambiguous owner"):
        await EmailServiceClient(base_url="http://email").get_email(user_id=uuid4())
