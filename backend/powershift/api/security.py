"""Per-launch token check.

The backend listens on 127.0.0.1 only, but any program on the same computer (or a
web page in the user's browser) could still try to call it. The desktop shell
generates a random token at every launch and gives it to both the backend and the
frontend; requests without it are rejected.
"""

from __future__ import annotations

import secrets
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from powershift.core.errors import error_body

TOKEN_HEADER = "X-PowerShift-Token"


def token_middleware(
    expected_token: str,
) -> Callable[[Request, Callable[[Request], Awaitable[Response]]], Awaitable[Response]]:
    async def check_token(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # CORS preflight requests never carry custom headers; let CORS handle them.
        if request.method == "OPTIONS" or not request.url.path.startswith("/api"):
            return await call_next(request)
        supplied = request.headers.get(TOKEN_HEADER, "")
        if not secrets.compare_digest(supplied, expected_token):
            return JSONResponse(
                error_body("unauthorized", "Missing or invalid application token."),
                status_code=401,
            )
        return await call_next(request)

    return check_token
