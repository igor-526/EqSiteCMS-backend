import re

from clients.ya_metrica_service.schemas import MetricaTaskListOutDto
from core.exceptions.base import ClientError
from core.protocols.ya_metrica_service import YaMetricaServiceClientProtocol
from core.schemas.users import UserOutDto


class MetricaTasksProxyService:
    def __init__(self, client: YaMetricaServiceClientProtocol) -> None:
        self._client = client

    async def list_tasks(
        self, *, actor: UserOutDto, limit: str = "20", offset: str = "0"
    ) -> MetricaTaskListOutDto:
        try:
            if not re.fullmatch(r"[0-9]+", limit) or not re.fullmatch(
                r"[0-9]+", offset
            ):
                raise ValueError
            parsed_limit, parsed_offset = int(limit), int(offset)
            if not 1 <= parsed_limit <= 100:
                raise ValueError
        except ValueError:
            raise ClientError("Некорректные limit/offset") from None
        return await self._client.list_tasks(
            equestrian_id=actor.equestrian_id, limit=parsed_limit, offset=parsed_offset
        )
