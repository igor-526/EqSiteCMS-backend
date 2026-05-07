from uuid import UUID

from pydantic import Field

from .base import Entity, TimeStampMixin


class Equestrian(Entity, TimeStampMixin):
    """Root tenant entity for a stable/equestrian service."""

    name: str = Field(default=..., max_length=127)
    service_key: str = Field(default=..., max_length=127)


class EquestrianContext(Entity):
    """Resolved tenant context passed explicitly into tenant-scoped use cases."""

    id: UUID = Field(default=...)
    source: str = Field(default=...)
