"""The execution runtime.

One entry point from trigger to recorded outcome, used by the CLI, the API, and the
internal scheduler alike. An execution that is created always reaches a terminal persisted
state.
"""

from __future__ import annotations

from taskcontrol.application.runtime.service import RunRequest, RunResult, RuntimeService

__all__ = ["RunRequest", "RunResult", "RuntimeService"]
