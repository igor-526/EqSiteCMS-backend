from typing import Protocol
from uuid import UUID

from core.entities.equestrian import Equestrian

from .base_repository import BaseRepositoryProtocol


class EquestrianRepositoryProtocol(BaseRepositoryProtocol[Equestrian], Protocol):
    async def get_by_id(self, id: UUID) -> Equestrian | None: ...
    async def get_by_service_key(self, service_key: str) -> Equestrian | None: ...
