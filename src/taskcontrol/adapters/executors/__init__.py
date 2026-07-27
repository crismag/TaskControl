"""Executor adapters.

Phase 1 runs work as operating-system processes. Shell, Python, and executable actions all
use the same supervision — they differ in how the command is assembled, not in how a
process is watched, timed out, or terminated.
"""

from __future__ import annotations

from taskcontrol.adapters.executors.registry import ExecutorRegistry, default_registry
from taskcontrol.adapters.executors.subprocess_executor import SubprocessExecutor

__all__ = ["ExecutorRegistry", "SubprocessExecutor", "default_registry"]
