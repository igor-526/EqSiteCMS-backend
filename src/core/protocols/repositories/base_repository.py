from __future__ import annotations

from typing import Protocol, Sequence
from uuid import UUID

from core.entities.base import Entity


class BaseRepositoryProtocol[E: Entity](Protocol):
    """Protocol for non-tenant repositories (no equestrian_id filtering)."""

    async def get_all(
        self,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[E]: ...

    async def get_by_id(self, id: UUID) -> E | None: ...

    async def get_by_ids(self, ids: Sequence[UUID]) -> dict[UUID, E]: ...

    async def update(self, entity: E) -> E: ...

    async def create(self, entity: E) -> E: ...

    async def bulk_create(self, entities: list[E]) -> list[E]: ...

    async def delete(self, id: UUID) -> None: ...

    async def bulk_delete(self, ids: Sequence[UUID]) -> None: ...


class TenantBaseRepositoryProtocol[E: Entity](Protocol):
    """Protocol for tenant-scoped repositories (equestrian_id required)."""

    async def get_all(
        self,
        *,
        equestrian_id: UUID,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[E]: ...

    async def get_by_id(self, id: UUID, *, equestrian_id: UUID) -> E | None: ...

    async def get_by_ids(
        self, ids: Sequence[UUID], *, equestrian_id: UUID
    ) -> dict[UUID, E]: ...

    async def update(self, entity: E) -> E: ...

    async def create(self, entity: E) -> E: ...

    async def bulk_create(self, entities: list[E]) -> list[E]: ...

    async def delete(self, id: UUID, *, equestrian_id: UUID) -> None: ...

    async def bulk_delete(
        self, ids: Sequence[UUID], *, equestrian_id: UUID
    ) -> None: ...
