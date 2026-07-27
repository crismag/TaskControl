"""Choosing an executor for an action.

A registry rather than a conditional in the runtime: adding the Tcl or HTTP executor in a
later phase must be a registration, not an edit to orchestration logic (engineering law 9).
"""

from __future__ import annotations

from taskcontrol.adapters.executors.subprocess_executor import SubprocessExecutor
from taskcontrol.common.errors import ValidationError
from taskcontrol.domain.tasks.actions import ExecutorType
from taskcontrol.ports.executor import Executor


class ExecutorRegistry:
    """Maps executor types to the adapters that serve them."""

    def __init__(self, executors: dict[ExecutorType, Executor] | None = None) -> None:
        self._executors: dict[ExecutorType, Executor] = dict(executors or {})

    def register(self, executor_type: ExecutorType, executor: Executor) -> None:
        """Register an executor for a type.

        Args:
            executor_type: The action type it serves.
            executor: The adapter.
        """
        self._executors[executor_type] = executor

    def get(self, executor_type: ExecutorType) -> Executor:
        """Return the executor for a type.

        Args:
            executor_type: The action type.

        Returns:
            The registered executor.

        Raises:
            ValidationError: If no adapter serves that type. The message lists what is
                available, because "unsupported executor" without alternatives is a dead
                end for whoever hits it.
        """
        executor = self._executors.get(executor_type)
        if executor is None:
            raise ValidationError(
                "No executor adapter is registered for this action type.",
                details={
                    "executor_type": str(executor_type),
                    "available": sorted(str(key) for key in self._executors),
                },
            )
        return executor

    def supports(self, executor_type: ExecutorType) -> bool:
        """Whether an adapter serves a type."""
        return executor_type in self._executors

    @property
    def registered_types(self) -> tuple[ExecutorType, ...]:
        """Every type this registry can run."""
        return tuple(sorted(self._executors, key=str))


def default_registry() -> ExecutorRegistry:
    """Return the executors Phase 1 ships.

    Tcl, HTTP, and plugin executors are deliberately absent: a revision naming one is
    rejected at publication rather than failing mysteriously at run time.

    Returns:
        A registry with shell, Python, and executable adapters.
    """
    return ExecutorRegistry(
        {
            ExecutorType.SHELL: SubprocessExecutor(ExecutorType.SHELL),
            ExecutorType.PYTHON: SubprocessExecutor(ExecutorType.PYTHON),
            ExecutorType.EXECUTABLE: SubprocessExecutor(ExecutorType.EXECUTABLE),
        }
    )
