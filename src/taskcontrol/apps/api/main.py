"""Composition root for the HTTP API process.

Builds settings, configures logging, mounts routers, and returns an application. It wires;
it does not define routes (ADR 0019).
"""

from __future__ import annotations

from fastapi import FastAPI

from taskcontrol import __version__
from taskcontrol.api.errors import register_error_handlers
from taskcontrol.api.middleware import CorrelationMiddleware
from taskcontrol.api.v1 import health
from taskcontrol.infrastructure.logging import configure_logging, get_logger
from taskcontrol.infrastructure.settings import Settings, get_settings

API_V1_PREFIX = "/api/v1"

logger = get_logger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the TaskControl ASGI application.

    Args:
        settings: Validated settings. Loaded from the environment when omitted, which is
            what the ``--factory`` entry point does.

    Returns:
        A configured application ready to serve.
    """
    resolved = settings or get_settings()
    configure_logging(resolved)

    app = FastAPI(
        title="TaskControl API",
        version=__version__,
        summary="Define, schedule, execute, observe, and govern automated work.",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.state.settings = resolved

    app.add_middleware(CorrelationMiddleware)
    register_error_handlers(app)
    app.include_router(health.router, prefix=API_V1_PREFIX)

    logger.info(
        "TaskControl API initialised",
        extra={"version": __version__, **resolved.describe()},
    )
    return app
