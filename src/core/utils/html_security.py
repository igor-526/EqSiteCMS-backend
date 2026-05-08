import re

from core.exceptions.base import ClientError

_INLINE_HANDLER_RE = re.compile(r"\bon\w+\s*=", re.IGNORECASE)


def validate_no_js_in_html(field: str, value: str) -> None:
    """Validate that *value* contains no JavaScript.

    Raises :class:`ClientError` when any of the following are detected:

    * ``<script`` tag (case-insensitive)
    * ``javascript:`` URI scheme (case-insensitive)
    * Inline event-handler attributes such as ``onclick=``, ``onerror=``, etc.
    """
    lower = value.lower()

    if "<script" in lower:
        raise ClientError(f"{field}: HTML-содержимое не должно содержать <script> теги")

    if "javascript:" in lower:
        raise ClientError(
            f"{field}: HTML-содержимое не должно содержать javascript: URI"
        )

    if _INLINE_HANDLER_RE.search(value):
        raise ClientError(
            f"{field}: HTML-содержимое не должно содержать inline JS-обработчики (onclick=, onerror= и т.д.)"
        )
