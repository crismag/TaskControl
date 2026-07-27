"""Request-scoped dependencies for the HTTP transport.

Dependencies are resolved from application state that the composition root populated, not
from module-level globals. That keeps the transport testable and keeps configuration out
of import time.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from taskcontrol.infrastructure.settings import Settings


@dataclass(frozen=True, slots=True)
class SettingsDependency:
    """Provides validated settings to a route handler.

    Attributes:
        value: The settings the composition root built at startup.
    """

    value: Settings

    def __init__(self, request: Request) -> None:
        """Resolve settings from application state.

        Args:
            request: The incoming request, carrying application state.
        """
        object.__setattr__(self, "value", request.app.state.settings)
