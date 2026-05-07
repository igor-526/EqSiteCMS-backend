from uuid import UUID

from core.schemas.baseschema import BaseSchema


class EquestrianOutDto(BaseSchema):
    id: UUID
    name: str
    service_key: str
