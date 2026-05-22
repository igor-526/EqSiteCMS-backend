from __future__ import annotations

import functools

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import PlainTextResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# GET-пути, требующие cookie-авторизации (CMS-only).
# При добавлении нового защищённого GET-эндпоинта — добавить путь сюда.
_PROTECTED_GET_PATH_PREFIXES: tuple[str, ...] = (
    "/api/auth/me",
    "/api/news-cms",
)

_MUTATING_METHODS: frozenset[str] = frozenset({"POST", "PATCH", "DELETE", "PUT"})


def _is_protected_request(
    method: str,
    path: str,
    preflight_request_method: str | None = None,
) -> bool:
    effective_method = (preflight_request_method or method).upper()

    if effective_method in _MUTATING_METHODS:
        return True

    if effective_method == "GET":
        return any(path.startswith(prefix) for prefix in _PROTECTED_GET_PATH_PREFIXES)

    return False


class SplitCORSMiddleware:
    """
    Два режима CORS:
    - PUBLIC: GET к публичным эндпоинтам → Access-Control-Allow-Origin: *
    - PROTECTED: мутирующие методы и CMS-only GET → строгий CORS, только cms_origins
    """

    def __init__(self, app: ASGIApp, cms_origins: list[str]) -> None:
        self.app = app
        self.cms_origins: frozenset[str] = frozenset(cms_origins)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method: str = scope["method"]
        path: str = scope["path"]
        headers = Headers(scope=scope)
        origin: str | None = headers.get("origin")

        if origin is None:
            await self.app(scope, receive, send)
            return

        if method == "OPTIONS" and "access-control-request-method" in headers:
            preflight_method = headers.get("access-control-request-method", "")
            protected = _is_protected_request("OPTIONS", path, preflight_method)
            response = self._preflight_response(origin, headers, protected=protected)
            await response(scope, receive, send)
            return

        protected = _is_protected_request(method, path)
        await self.app(
            scope,
            receive,
            functools.partial(
                self._send_with_cors,
                send=send,
                origin=origin,
                protected=protected,
            ),
        )

    def _preflight_response(
        self,
        origin: str,
        request_headers: Headers,
        protected: bool,
    ) -> Response:
        if protected:
            if origin not in self.cms_origins:
                return PlainTextResponse("Disallowed CORS origin", status_code=400)
            resp_headers = {
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Credentials": "true",
                "Access-Control-Allow-Methods": "GET, POST, PATCH, DELETE, PUT, OPTIONS",
                "Access-Control-Allow-Headers": request_headers.get(
                    "access-control-request-headers", "*"
                ),
                "Access-Control-Max-Age": "600",
                "Vary": "Origin",
            }
        else:
            resp_headers = {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": request_headers.get(
                    "access-control-request-headers", "*"
                ),
                "Access-Control-Max-Age": "600",
            }
        return PlainTextResponse("OK", status_code=200, headers=resp_headers)

    async def _send_with_cors(
        self,
        message: Message,
        send: Send,
        origin: str,
        protected: bool,
    ) -> None:
        if message["type"] != "http.response.start":
            await send(message)
            return

        message.setdefault("headers", [])
        headers = MutableHeaders(scope=message)

        if protected:
            if origin in self.cms_origins:
                headers["Access-Control-Allow-Origin"] = origin
                headers["Access-Control-Allow-Credentials"] = "true"
                headers.add_vary_header("Origin")
        else:
            headers["Access-Control-Allow-Origin"] = "*"

        await send(message)
