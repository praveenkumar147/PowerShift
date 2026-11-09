"""Consistent JSON error responses.

Every error sent to the frontend has the same shape:

    {"error": {"code": "not_found", "message": "...", "fields": {...}}}

Internal details (stack traces, SQL) are written to the local log file only.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base class for expected, user-facing errors raised by services."""

    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, fields: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.fields = fields or {}


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class ValidationFailedError(AppError):
    """Input is well-formed but breaks a rule involving several fields."""

    status_code = 422
    code = "validation_error"


def error_body(code: str, message: str, fields: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "fields": fields or {}}}


def _validation_fields(exc: RequestValidationError) -> dict[str, str]:
    fields: dict[str, str] = {}
    for err in exc.errors():
        # loc looks like ("body", "rated_power_w"); drop the "body"/"query" prefix.
        location = [str(part) for part in err.get("loc", ())[1:]] or ["request"]
        message = str(err.get("msg", "Invalid value")).removeprefix("Value error, ")
        fields[".".join(location)] = message
    return fields


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            error_body(exc.code, exc.message, exc.fields), status_code=exc.status_code
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            error_body("validation_error", "Some values are invalid.", _validation_fields(exc)),
            status_code=422,
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {401: "unauthorized", 404: "not_found", 405: "method_not_allowed"}.get(
            exc.status_code, "http_error"
        )
        return JSONResponse(error_body(code, str(exc.detail)), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            error_body("internal_error", "Something went wrong. Details were saved to the log."),
            status_code=500,
        )
