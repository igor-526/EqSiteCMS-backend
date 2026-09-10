"""Stable public news identifiers; keep parity with the frozen backfill."""

import re
from uuid import UUID

from core.entities.base import _generate_slug


def generate_news_slug(text: str, news_id: UUID) -> str:
    """Normalize the title and append the full identity, once before insert."""
    normalized = re.sub(r"[^a-z0-9-]", "", _generate_slug(text))
    normalized = re.sub(r"-+", "-", normalized).strip("-")
    base = normalized[:127].rstrip("-") or "news"
    return f"{base}-{news_id.hex}"
