from typing import Literal, Protocol
from uuid import UUID

from core.entities.site_settings import SiteSetting

from .base_repository import TenantBaseRepositoryProtocol


class SiteSettingsRepositoryProtocol(
    TenantBaseRepositoryProtocol[SiteSetting], Protocol
):
    async def find_by_key(
        self, key: str, *, equestrian_id: UUID
    ) -> SiteSetting | None: ...

    async def find_by_name(
        self, name: str, *, equestrian_id: UUID
    ) -> SiteSetting | None: ...

    async def get_filtered(
        self,
        *,
        equestrian_id: UUID,
        key: list[str] | None = None,
        name: str | None = None,
        value: str | None = None,
        description: str | None = None,
        type: (
            list[
                Literal[
                    "string",
                    "number",
                    "float",
                    "boolean",
                    "object",
                    "date",
                    "time",
                    "datetime",
                ]
            ]
            | None
        ) = None,
        sort: (
            list[Literal["key", "name", "type", "-key", "-name", "-type"]] | None
        ) = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[list[SiteSetting], int]: ...
