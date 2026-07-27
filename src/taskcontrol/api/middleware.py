"""HTTP middleware.

Correlation is established here, at the outermost boundary, so that every log record
produced while handling a request carries the same identifier — including records emitted
by code that knows nothing about HTTP.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

CORRELATION_HEADER = "X-Correlation-ID"


class CorrelationMiddleware(BaseHTTPMiddleware):
    """Bind a correlation identifier for the lifetime of each request.

    An identifier supplied by the client is honoured so that a trace can span systems; one
    is generated when absent. The value is echoed in the response header.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Bind correlation context, delegate, and echo the identifier.

        Args:
            request: The incoming request.
            call_next: The next handler in the chain.

        Returns:
            The downstream response, with the correlation header set.
        """
        # Imported here so the transport layer does not create an import-time dependency
        # on infrastructure at module load.
        from taskcontrol.infrastructure.logging import correlation_context

        correlation_id = request.headers.get(CORRELATION_HEADER) or str(uuid.uuid4())
        with correlation_context(correlation_id=correlation_id, path=request.url.path):
            response = await call_next(request)
        response.headers[CORRELATION_HEADER] = correlation_id
        return response
