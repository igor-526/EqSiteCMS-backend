"""Границы клиента vk-service: URL, отсутствие peer credential, строгий разбор."""

from uuid import uuid4

import httpx
import pytest

from clients.vk_service.client import VkServiceClient

BASE_URL = "http://vk-service"


class RecordingClient:
    def __init__(self, *responses: httpx.Response) -> None:
        self.responses = list(responses)
        self.requests: list[dict] = []

    async def __aenter__(self) -> "RecordingClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    def _next(self) -> httpx.Response:
        return self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]

    async def get(self, url: str, **kwargs: object) -> httpx.Response:
        self.requests.append({"method": "GET", "url": url, **kwargs})
        return self._next()

    async def post(self, url: str, **kwargs: object) -> httpx.Response:
        self.requests.append({"method": "POST", "url": url, **kwargs})
        return self._next()

    async def delete(self, url: str, **kwargs: object) -> httpx.Response:
        self.requests.append({"method": "DELETE", "url": url, **kwargs})
        return self._next()


def _response(
    status: int, payload: object, method: str = "GET", path: str = "/vks"
) -> httpx.Response:
    return httpx.Response(
        status, json=payload, request=httpx.Request(method, BASE_URL + path)
    )


def _binding(user_id: str) -> dict:
    return {
        "id": str(uuid4()),
        "user_id": user_id,
        "vk_peer_id": 42,
        "state": "ACTIVE",
        "vk_screen_name": "durov",
        "vk_display_name": "Pavel",
    }


@pytest.fixture
def recorder(monkeypatch: pytest.MonkeyPatch):
    def _install(*responses: httpx.Response) -> RecordingClient:
        recording = RecordingClient(*responses)
        monkeypatch.setattr(httpx, "AsyncClient", lambda: recording)
        return recording

    return _install


async def test_binding_lookup_uses_the_owner_filter(recorder) -> None:
    user_id = uuid4()
    recording = recorder(_response(200, [_binding(str(user_id))]))

    binding = await VkServiceClient(base_url=BASE_URL).get_binding(user_id=user_id)

    assert binding is not None and binding.user_id == user_id
    assert recording.requests[0]["url"] == f"{BASE_URL}/vks"
    assert recording.requests[0]["params"] == {"user_ids": str(user_id)}


async def test_missing_binding_returns_none(recorder) -> None:
    recorder(_response(200, []))

    assert await VkServiceClient(base_url=BASE_URL).get_binding(user_id=uuid4()) is None


async def test_a_foreign_owner_in_the_response_is_rejected(recorder) -> None:
    recorder(_response(200, [_binding(str(uuid4()))]))

    with pytest.raises(ValueError, match="ambiguous"):
        await VkServiceClient(base_url=BASE_URL).get_binding(user_id=uuid4())


async def test_multiple_bindings_in_the_response_are_rejected(recorder) -> None:
    user_id = uuid4()
    recorder(_response(200, [_binding(str(user_id)), _binding(str(user_id))]))

    with pytest.raises(ValueError, match="ambiguous"):
        await VkServiceClient(base_url=BASE_URL).get_binding(user_id=user_id)


async def test_bot_info_url_and_parsing(recorder) -> None:
    recording = recorder(
        _response(
            200,
            {
                "group_id": 1,
                "group_screen_name": "eqsitecms_bot",
                "link_command": "/link",
                "group_url": "https://vk.com/eqsitecms_bot",
                "dialog_url": "https://vk.me/eqsitecms_bot",
            },
            path="/vks/bot-info",
        )
    )

    info = await VkServiceClient(base_url=BASE_URL).get_bot_info()

    assert info.dialog_url == "https://vk.me/eqsitecms_bot"
    assert recording.requests[0]["url"] == f"{BASE_URL}/vks/bot-info"


async def test_issue_confirmation_url_and_body(recorder) -> None:
    user_id = uuid4()
    recording = recorder(
        _response(
            201,
            {
                "code": "ABC23XYZ",
                "expires_at": "2026-08-27T12:00:00+00:00",
                "state": "PENDING",
                "link_command": "/link",
                "dialog_url": "https://vk.me/eqsitecms_bot",
            },
            method="POST",
            path="/vks/issue-confirmation",
        )
    )

    issued = await VkServiceClient(base_url=BASE_URL).issue_confirmation(
        user_id=user_id
    )

    assert issued.code == "ABC23XYZ"
    assert recording.requests[0]["url"] == f"{BASE_URL}/vks/issue-confirmation"
    assert recording.requests[0]["json"] == {"user_id": str(user_id)}


async def test_delete_url_targets_the_owner(recorder) -> None:
    user_id = uuid4()
    recording = recorder(_response(204, None, method="DELETE", path=f"/vks/{user_id}"))

    await VkServiceClient(base_url=BASE_URL).delete_binding(user_id=user_id)

    assert recording.requests[0]["url"] == f"{BASE_URL}/vks/{user_id}"


async def test_no_request_carries_a_peer_service_credential(recorder) -> None:
    user_id = uuid4()
    recording = recorder(_response(200, [_binding(str(user_id))]))

    await VkServiceClient(base_url=BASE_URL).get_binding(user_id=user_id)

    for request in recording.requests:
        headers = request.get("headers") or {}
        assert not [key for key in headers if key.lower() == "x-service-key"]


def test_the_client_source_declares_no_peer_credential() -> None:
    import inspect

    source = inspect.getsource(VkServiceClient)

    assert "X-Service-Key" not in source
    assert "service_key" not in source


async def test_a_downstream_error_status_is_raised(recorder) -> None:
    recorder(_response(503, {"detail": "not configured"}, path="/vks/bot-info"))

    with pytest.raises(httpx.HTTPStatusError) as exc:
        await VkServiceClient(base_url=BASE_URL).get_bot_info()

    assert exc.value.response.status_code == 503


def test_the_base_url_trailing_slash_is_normalised() -> None:
    assert (
        VkServiceClient(base_url="http://vk-service/")._base_url == "http://vk-service"
    )
