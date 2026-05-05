from typing import Protocol

from core.entities.integration_credentials import IntegrationCredentials

from .base_repository import BaseRepositoryProtocol


class TokenRepositoryProtocol(
    BaseRepositoryProtocol[IntegrationCredentials], Protocol
): ...
