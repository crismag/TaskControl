"""The execution runtime.

One entry point from activation to recorded outcome, used by cron wrappers, queue workers,
administrative run-now, and transport adapters alike. An execution that is created always
reaches a terminal persisted state.
"""

from __future__ import annotations

from taskcontrol.application.runtime.service import RunRequest, RunResult, RuntimeService

__all__ = ["RunRequest", "RunResult", "RuntimeService"]
