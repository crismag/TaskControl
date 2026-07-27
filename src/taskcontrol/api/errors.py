"""Translation of the error taxonomy into HTTP responses.

A stable machine-readable code and a human message reach the client. A traceback, an
internal path, and a secret value never do.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from taskcontrol.common.errors import ErrorCode, TaskControlError
from taskcontrol.infrastructure.logging import get_correlation_context, get_logger

logger = get_logger(__name__)

# Literal codes rather than framework constants: the numbers are fixed by RFC 9110 and
# never deprecate, whereas the constant names have already been renamed once upstream.
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404
HTTP_CONFLICT = 409
HTTP_UNPROCESSABLE = 422
HTTP_INTERNAL_ERROR = 500
HTTP_SERVICE_UNAVAILABLE = 503

_STATUS_BY_CODE: dict[ErrorCode, int] = {
    ErrorCode.VALIDATION_FAILED: HTTP_UNPROCESSABLE,
    ErrorCode.DOMAIN_RULE_VIOLATION: HTTP_CONFLICT,
    ErrorCode.NOT_AUTHORISED: HTTP_FORBIDDEN,
    ErrorCode.NOT_FOUND: HTTP_NOT_FOUND,
    ErrorCode.CONFLICT: HTTP_CONFLICT,
    ErrorCode.CONFIGURATION_INVALID: HTTP_INTERNAL_ERROR,
    ErrorCode.TRANSIENT_INFRASTRUCTURE_FAILURE: HTTP_SERVICE_UNAVAILABLE,
    ErrorCode.PERMANENT_INFRASTRUCTURE_FAILURE: HTTP_INTERNAL_ERROR,
}


def http_status_for(code: ErrorCode) -> int:
    """Return the HTTP status that represents an error code.

    Args:
        code: The taxonomy code.

    Returns:
        The mapped HTTP status, defaulting to 500 for an unmapped code.
    """
    return _STATUS_BY_CODE.get(code, HTTP_INTERNAL_ERROR)


def _error_body(code: str, message: str, details: dict[str, Any]) -> dict[str, Any]:
    """Build the standard error envelope, including correlation identifiers."""
    body: dict[str, Any] = {"error": {"code": code, "message": message, "details": details}}
    correlation = get_correlation_context()
    if correlation:
        body["error"]["correlation"] = correlation
    return body


async def taskcontrol_error_handler(_: Request, exc: Exception) -> JSONResponse:
    """Render a TaskControlError as its mapped HTTP response.

    Args:
        _: The request, unused.
        exc: The raised error.

    Returns:
        A JSON response carrying the stable code and safe message.
    """
    assert isinstance(exc, TaskControlError)  # noqa: S101 — handler registered for this type
    status_code = http_status_for(exc.code)
    if status_code >= HTTP_INTERNAL_ERROR:
        logger.error("Request failed: %s", exc.message, extra={"error_code": str(exc.code)})
    return JSONResponse(
        status_code=status_code,
        content=_error_body(str(exc.code), exc.message, exc.details),
    )


async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    """Render an unexpected exception without leaking internals.

    The traceback is logged, never returned. The client receives a stable code and a
    generic message.

    Args:
        _: The request, unused.
        exc: The unexpected exception.

    Returns:
        A 500 JSON response.
    """
    logger.exception("Unhandled exception", exc_info=exc)
    return JSONResponse(
        status_code=HTTP_INTERNAL_ERROR,
        content=_error_body(
            str(ErrorCode.PERMANENT_INFRASTRUCTURE_FAILURE),
            "An internal error occurred.",
            {},
        ),
    )


def register_error_handlers(app: FastAPI) -> None:
    """Attach TaskControl's error handlers to an application.

    Args:
        app: The application to attach handlers to.
    """
    app.add_exception_handler(TaskControlError, taskcontrol_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
