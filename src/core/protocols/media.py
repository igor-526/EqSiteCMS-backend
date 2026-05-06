from typing import Protocol


class MediaStorageProtocol(Protocol):
    async def save(self, file_content: bytes, filename: str) -> str: ...

    async def load(self, filename: str) -> bytes: ...

    async def delete(self, filename: str) -> None: ...


class PhotoUrlBuilderProtocol(Protocol):
    def build(self, filename: str) -> str: ...


class MediaTypeValidatorProtocol(Protocol):
    def validate(
        self, filename: str, content: bytes, content_type: str | None = None
    ) -> None: ...
