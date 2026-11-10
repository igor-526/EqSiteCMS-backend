import logging
from contextvars import ContextVar
from uuid import UUID

import httpx

from clients.ya_metrica_service.schemas import MetricaTaskListOutDto
from core.protocols.ya_metrica_service import YaMetricaServiceUnavailableError

_metrica_request_active: ContextVar[bool] = ContextVar(
    "metrica_request_active", default=False
)


class _MetricaRequestLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return not _metrica_request_active.get()


logging.getLogger("httpx").addFilter(_MetricaRequestLogFilter())


class YaMetricaServiceClient:
    """Только selector actor и pagination, без credentials/retry/redirects."""

    def __init__(
        self, *, base_url: str, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._transport = transport

    @staticmethod
    def parse_response(response: httpx.Response) -> MetricaTaskListOutDto:
        if response.status_code != 200:
            raise YaMetricaServiceUnavailableError()
        try:
            return MetricaTaskListOutDto.model_validate(response.json())
        except ValueError:
            raise YaMetricaServiceUnavailableError() from None

    async def list_tasks(
        self, *, equestrian_id: UUID, limit: int, offset: int
    ) -> MetricaTaskListOutDto:
        token = _metrica_request_active.set(True)
        try:
            async with httpx.AsyncClient(
                timeout=4.0,
                transport=self._transport,
                trust_env=False,
                follow_redirects=False,
            ) as client:
                response = await client.get(
                    f"{self._base_url}/api/metrica/tasks",
                    headers={"X-Equestrian-Id": str(equestrian_id)},
                    params={"limit": limit, "offset": offset},
                )
            return self.parse_response(response)
        except httpx.RequestError:
            raise YaMetricaServiceUnavailableError() from None
        finally:
            _metrica_request_active.reset(token)
