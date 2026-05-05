from typing import Literal, Protocol

from core.entities.site_settings import SiteSetting

from .base_repository import BaseRepositoryProtocol


class SiteSettingsRepositoryProtocol(BaseRepositoryProtocol[SiteSetting], Protocol):
    async def find_by_key(self, key: str) -> SiteSetting | None: ...
    async def find_by_name(self, name: str) -> SiteSetting | None: ...
    async def get_filtered(
        self,
        *,
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
