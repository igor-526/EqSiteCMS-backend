from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass

MAX_PHOTO_NAME_LENGTH = 63
MAX_EXTENSION_LENGTH = 10
MAX_NAME_ATTEMPTS = 100


@dataclass(frozen=True)
class NormalizedPhotoName:
    full_name: str
    stem: str
    extension: str


def normalize_photo_name(value: str | None) -> NormalizedPhotoName:
    normalized = unicodedata.normalize("NFC", value or "")
    basename = normalized.replace("\\", "/").rsplit("/", maxsplit=1)[-1]
    basename = "".join(
        char for char in basename if not unicodedata.category(char).startswith("C")
    ).strip()
    if not basename:
        basename = "photo"

    dot_index = basename.rfind(".")
    extension = ""
    stem = basename
    if 0 < dot_index < len(basename) - 1:
        candidate = basename[dot_index:]
        if not any(char in "/\\" for char in candidate):
            extension = candidate[:MAX_EXTENSION_LENGTH]
            stem = basename[:dot_index].strip() or "photo"

    return NormalizedPhotoName(
        full_name=f"{stem}{extension}", stem=stem, extension=extension
    )


def build_bounded_photo_name(value: str | None, *, identity: bytes) -> str:
    normalized = normalize_photo_name(value)
    if len(normalized.full_name) <= MAX_PHOTO_NAME_LENGTH:
        return normalized.full_name

    encoded = normalized.full_name.encode("utf-8")
    digest = hashlib.sha256(
        b"N" + len(encoded).to_bytes(8, "big") + encoded + identity
    ).hexdigest()[:12]
    tail = f"-{digest}{normalized.extension}"
    prefix_budget = MAX_PHOTO_NAME_LENGTH - len(tail)
    prefix = normalized.stem[:prefix_budget] or "photo"[:prefix_budget]
    return f"{prefix}{tail}"


def add_name_discriminator(base_name: str, attempt: int) -> str:
    if not 1 <= attempt <= MAX_NAME_ATTEMPTS:
        raise ValueError("attempt must be between 1 and 100")
    if attempt == 1:
        return base_name[:MAX_PHOTO_NAME_LENGTH]

    normalized = normalize_photo_name(base_name)
    discriminator = f"-{attempt}"
    digest_match = re.search(r"-[0-9a-f]{12}$", normalized.stem)
    preserved_tail = digest_match.group(0) if digest_match else ""
    readable_stem = (
        normalized.stem[: digest_match.start()] if digest_match else normalized.stem
    )
    stem_budget = MAX_PHOTO_NAME_LENGTH - len(
        normalized.extension + preserved_tail + discriminator
    )
    stem = readable_stem[:stem_budget] or "photo"[:stem_budget]
    return f"{stem}{preserved_tail}{discriminator}{normalized.extension}"
