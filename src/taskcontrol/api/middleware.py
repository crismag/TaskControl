"""HTTP middleware.

Correlation is established here, at the outermost boundary, so that every log record
produced while handling a request carries the same identifier — including records emitted
by code that knows nothing about HTTP.

The access log is emitted here too, rather than by the server. Uvicorn writes its access
log after the response has left the application, outside the correlation context, so it
cannot carry the identifier that makes a request followable. Emitting it inside the
middleware produces one structured, correlated record per request.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from taskcontrol.infrastructure.logging import correlation_context, get_logger

CORRELATION_HEADER = "X-Correlation-ID"

_SERVER_ERROR = 500
_CLIENT_ERROR = 400

logger = get_logger("taskcontrol.api.access")


class CorrelationMiddleware(BaseHTTPMiddleware):
    """Bind a correlation identifier for each request and emit its access log.

    An identifier supplied by the client is honoured so a trace can span systems; one is
    generated when absent. The value is echoed in the response header.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Bind correlation context, delegate, log the outcome, and echo the identifier.

        A failure downstream is logged and re-raised, so an exception that never becomes a
        response still leaves an access record.

        Args:
            request: The incoming request.
            call_next: The next handler in the chain.

        Returns:
            The downstream response, with the correlation header set.
        """
        correlation_id = request.headers.get(CORRELATION_HEADER) or str(uuid.uuid4())
        started = time.perf_counter()

        with correlation_context(correlation_id=correlation_id, path=request.url.path):
            try:
                response = await call_next(request)
            except Exception:
                self._log_access(request, None, started)
                raise
            self._log_access(request, response.status_code, started)

        response.headers[CORRELATION_HEADER] = correlation_id
        return response

    def _log_access(self, request: Request, status_code: int | None, started: float) -> None:
        """Emit one structured access record for a completed request.

        Args:
            request: The request being logged.
            status_code: The response status, or ``None`` when the request raised.
            started: The ``perf_counter`` value captured before dispatch.
        """
        # `path` reaches the record through the correlation context, so it is not
        # repeated here.
        extra = {
            "http_method": request.method,
            "http_status": status_code,
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            "client": request.client.host if request.client else None,
        }

        if status_code is None or status_code >= _SERVER_ERROR:
            logger.error("HTTP request failed", extra=extra)
        elif status_code >= _CLIENT_ERROR:
            logger.warning("HTTP request rejected", extra=extra)
        else:
            logger.info("HTTP request", extra=extra)
