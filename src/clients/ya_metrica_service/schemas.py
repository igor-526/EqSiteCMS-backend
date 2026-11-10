import re
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator


class MetricaTaskOutDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(strict=True)
    type: Literal["parsing", "merge", "delete"]
    status: Literal["queued", "running", "succeeded", "failed", "cancelled"]
    is_active: bool = Field(strict=True)
    created_at: AwareDatetime

    @field_validator("created_at", mode="before")
    @classmethod
    def require_rfc3339_wire_string(cls, value: object) -> str:
        # AwareDatetime также принимает Unix timestamps; wire разрешает только RFC3339.
        if not isinstance(value, str) or not re.fullmatch(
            r"[0-9]{4}-[0-9]{2}-[0-9]{2}[Tt][0-9]{2}:[0-9]{2}:[0-9]{2}"
            r"(?:\.[0-9]+)?(?:[Zz]|[+-][0-9]{2}:[0-9]{2})",
            value,
        ):
            raise ValueError("created_at must be an RFC3339 string")
        return value


class MetricaTaskListOutDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MetricaTaskOutDto]
    total: int = Field(strict=True, ge=0)
