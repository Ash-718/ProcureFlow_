"""
Error handling, matching Spring's `ApiException` / `GlobalExceptionHandler`.

The frontend's `apiErrorMessage()` reads `error.response.data.message`, and
`types/index.ts` declares `ApiErrorBody` as::

    {timestamp, status, error, message, path, fieldErrors?}

so every error this backend emits has to carry that shape. A FastAPI default
`{"detail": ...}` body would leave the UI showing its generic
"Something went wrong" fallback instead of the real reason.

`error` is the HTTP reason phrase ("Not Found", "Bad Request"), because that is
what `HttpStatus.getReasonPhrase()` produced on the Java side.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("innovategov.errors")

#: HTTP reason phrases, matching Spring's `HttpStatus.getReasonPhrase()`.
REASON_PHRASES: dict[int, str] = {
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    409: "Conflict",
    413: "Payload Too Large",
    422: "Unprocessable Entity",
    429: "Too Many Requests",
    500: "Internal Server Error",
}


class ApiException(Exception):
    """
    Application error carrying an HTTP status, mirroring Java's `ApiException`.

    The named constructors match the Java helpers one-for-one so ported service
    code reads the same on both sides.
    """

    def __init__(self, status_code: int, message: str,
                 field_errors: dict[str, str] | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.field_errors = field_errors

    @classmethod
    def bad_request(cls, message: str, field_errors: dict[str, str] | None = None) -> "ApiException":
        return cls(status.HTTP_400_BAD_REQUEST, message, field_errors)

    @classmethod
    def unauthorized(cls, message: str = "Not authenticated") -> "ApiException":
        return cls(status.HTTP_401_UNAUTHORIZED, message)

    @classmethod
    def forbidden(cls, message: str) -> "ApiException":
        return cls(status.HTTP_403_FORBIDDEN, message)

    @classmethod
    def not_found(cls, message: str) -> "ApiException":
        return cls(status.HTTP_404_NOT_FOUND, message)

    @classmethod
    def conflict(cls, message: str) -> "ApiException":
        return cls(status.HTTP_409_CONFLICT, message)


def error_body(status_code: int, message: str, path: str,
               field_errors: dict[str, str] | None = None) -> dict[str, Any]:
    """
    Build the exact JSON body the frontend's `ApiErrorBody` describes.

    ``fieldErrors`` is always present — Spring's `ErrorResponse` is a record
    with six components and Jackson emits them all, so a captured 404 carries
    ``"fieldErrors": null``. The frontend declares the key optional, so either
    form works, but matching keeps the two backends diff-clean.
    """
    from app.schemas.base import format_instant

    return {
        # Java's Instant.toString(): UTC with a trailing 'Z'.
        "timestamp": format_instant(datetime.now(timezone.utc)),
        "status": status_code,
        "error": REASON_PHRASES.get(status_code, "Error"),
        "message": message,
        "path": path,
        "fieldErrors": field_errors,
    }


def register_exception_handlers(app: FastAPI) -> None:
    """Install handlers so *every* error path produces the contract shape."""

    @app.exception_handler(ApiException)
    async def _api_exception(request: Request, exc: ApiException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(exc.status_code, exc.message, request.url.path, exc.field_errors),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Spring returned 400 with a `fieldErrors` map; FastAPI's default is a
        # 422 with a differently-shaped `detail` list. Convert to Spring's form.
        field_errors: dict[str, str] = {}
        for error in exc.errors():
            location = [part for part in error.get("loc", ()) if part not in ("body", "query", "path")]
            field = ".".join(str(part) for part in location) or "request"
            field_errors[field] = error.get("msg", "Invalid value")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=error_body(400, "Validation failed", request.url.path, field_errors),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        message = exc.detail if isinstance(exc.detail, str) else "Request failed"
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            message = f"No such endpoint: {request.url.path}"
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(exc.status_code, message, request.url.path),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        # Detail goes to the log; the client gets a generic message, exactly as
        # the Java handler did. Never leak a traceback to an API consumer.
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_body(500, "An unexpected error occurred", request.url.path),
        )


__all__ = ["ApiException", "REASON_PHRASES", "error_body", "register_exception_handlers"]
