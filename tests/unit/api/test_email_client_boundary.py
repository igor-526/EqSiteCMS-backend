from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from clients.email_service.client import EmailServiceClient
from core.exceptions.email_proxy import EmailServiceResponseError


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
    user_id = uuid4()
    response = httpx.Response(
        201,
        json={
            "id": str(uuid4()),
            "user_id": str(user_id),
            "email": "a@example.com",
            "approved": False,
        },
        request=httpx.Request("POST", "http://email/emails"),
    )
    recording = RecordingClient(response)
    monkeypatch.setattr(httpx, "AsyncClient", lambda: recording)

    await EmailServiceClient(base_url="http://email").create_email(
        user_id=user_id, email="a@example.com"
    )

    request = recording.requests[0]
    headers = {key.lower(): value for key, value in request.get("headers", {}).items()}
    assert "authorization" not in headers
    assert "x-service-key" not in headers
    assert request["json"] == {"user_id": str(user_id), "email": "a@example.com"}


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


# UT-EM-07: producer response validation and privacy at the real client boundary.
@pytest.mark.parametrize(
    "variant", ["missing", "foreign", "mismatch", "bad-id", "list", "json"]
)
async def test_create_rejects_untrusted_response(monkeypatch, variant):
    user_id = uuid4()
    payload = {
        "id": str(uuid4()),
        "user_id": str(user_id),
        "email": "unit@example.invalid",
        "approved": False,
        "private": "private-response-marker",
    }
    if variant == "missing":
        del payload["approved"]
    elif variant == "foreign":
        payload["user_id"] = str(uuid4())
    elif variant == "mismatch":
        payload["email"] = "other@example.invalid"
    elif variant == "bad-id":
        payload["id"] = "bad"
    body = (
        {"content": b"not-json"}
        if variant == "json"
        else {"json": [payload] if variant == "list" else payload}
    )
    response = httpx.Response(
        201, **body, request=httpx.Request("POST", "http://email/emails")
    )
    monkeypatch.setattr(httpx, "AsyncClient", lambda: RecordingClient(response))
    with pytest.raises(EmailServiceResponseError) as raised:
        await EmailServiceClient(base_url="http://email").create_email(
            user_id=user_id, email="unit@example.invalid"
        )
    assert str(raised.value) == "Email service returned an invalid response"


async def test_create_normalizes_comparison_and_filters_private_response(monkeypatch):
    user_id = uuid4()
    expected = {
        "id": str(uuid4()),
        "user_id": str(user_id),
        "email": "unit@example.invalid",
        "approved": True,
    }
    response = httpx.Response(
        201,
        json={**expected, "code": "private-response-marker"},
        request=httpx.Request("POST", "http://email/emails"),
    )
    recording = RecordingClient(response)
    monkeypatch.setattr(httpx, "AsyncClient", lambda: recording)
    result = await EmailServiceClient(base_url="http://email").create_email(
        user_id=user_id, email=" Unit@EXAMPLE.INVALID "
    )
    assert result == expected
    assert recording.requests == [
        {
            "url": "http://email/emails",
            "json": {"user_id": str(user_id), "email": " Unit@EXAMPLE.INVALID "},
        }
    ]


# UT-EM-05/09: only 202 with JSON object establishes acceptance, not delivery.
@pytest.mark.parametrize("status", [200, 201, 204, 202, 400, 404, 503])
@pytest.mark.parametrize("body", ["queued", "invalid-json", "list"])
async def test_send_requires_202_and_json_object(monkeypatch, status, body):
    user_id = uuid4()
    kwargs = (
        {"content": b"not-json"}
        if body == "invalid-json"
        else {"json": [] if body == "list" else {"detail": "queued"}}
    )
    response = httpx.Response(
        status,
        **kwargs,
        request=httpx.Request("POST", "http://email/emails/send-confirmation"),
    )
    recording = RecordingClient(response)
    monkeypatch.setattr(httpx, "AsyncClient", lambda: recording)
    client = EmailServiceClient(base_url="http://email")
    if status == 202 and body == "queued":
        assert await client.send_confirmation(user_id=user_id) == {"detail": "queued"}
    else:
        error = httpx.HTTPStatusError if status >= 400 else EmailServiceResponseError
        with pytest.raises(error):
            await client.send_confirmation(user_id=user_id)
    assert recording.requests == [
        {
            "url": "http://email/emails/send-confirmation",
            "json": {"user_id": str(user_id)},
        }
    ]
