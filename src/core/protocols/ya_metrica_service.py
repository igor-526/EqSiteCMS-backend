from typing import Protocol
from uuid import UUID

from clients.ya_metrica_service.schemas import MetricaTaskListOutDto


class YaMetricaServiceUnavailableError(Exception):
    """Нейтральная ошибка транспорта или контракта peer."""

    def __init__(self) -> None:
        super().__init__("Metrica service unavailable")


class YaMetricaServiceClientProtocol(Protocol):
    async def list_tasks(
        self, *, equestrian_id: UUID, limit: int, offset: int
    ) -> MetricaTaskListOutDto: ...
