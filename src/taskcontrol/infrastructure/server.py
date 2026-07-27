"""Starting the HTTP server process.

Binding the API is a process-level concern, so it lives in infrastructure rather than in
the CLI transport. This is what lets ``taskctl server`` honour ``TASKCONTROL_API_HOST``
and ``TASKCONTROL_API_PORT``: before this module existed those settings were validated,
displayed, and logged, but never used to bind — the server took its address from
uvicorn's own command line instead, so the reported configuration could disagree with
reality.

The ASGI application is referenced by import string rather than by importing it. That is
required for ``--reload`` to work, and it keeps this module free of a compile-time
dependency on the composition root it starts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from taskcontrol.common.errors import ConfigurationError
from taskcontrol.infrastructure.logging import get_logger, uvicorn_log_config

if TYPE_CHECKING:
    from taskcontrol.infrastructure.settings import Settings

ASGI_FACTORY = "taskcontrol.apps.api.main:create_app"
"""Import string for the ASGI application factory, resolved by the server at runtime."""

logger = get_logger(__name__)


def run_api(settings: Settings, *, reload: bool = False) -> None:
    """Start the HTTP API and block until the process is stopped.

    Args:
        settings: Validated settings. ``api_host`` and ``api_port`` determine the bind
            address, so what ``taskctl health`` reports is what the server actually uses.
        reload: Restart on source change. Development only; it spawns a supervisor
            process and must not be used in production.

    Raises:
        ConfigurationError: If the optional API dependencies are not installed.
    """
    try:
        import uvicorn
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised by the extras test
        raise ConfigurationError(
            "The API extra is not installed. Install it with: pip install 'taskcontrol[api]'",
            details={"missing_module": exc.name or "uvicorn"},
        ) from exc

    logger.info(
        "Starting TaskControl API",
        extra={"host": settings.api_host, "port": settings.api_port, "reload": reload},
    )

    uvicorn.run(
        ASGI_FACTORY,
        factory=True,
        host=settings.api_host,
        port=settings.api_port,
        reload=reload,
        # TaskControl emits its own structured access log from the request middleware,
        # where correlation context is bound. Uvicorn's plain-text access log would be
        # both duplicative and uncorrelated.
        access_log=False,
        log_config=uvicorn_log_config(settings),
    )
