"""The executor port.

An executor launches one process, waits for it, and reports what happened. It does not
decide what the result means: classification is a domain policy, and an adapter that
returned an outcome would be making a domain decision in the wrong layer.

Every executor takes an argument vector. There is no string-command entry point, because
the safe path must be the only path — a task that genuinely needs shell interpretation
opts in explicitly on its action specification, and the executor receives that decision
rather than inferring it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from taskcontrol.domain.common.values import Duration
from taskcontrol.domain.execution.results import ProcessResult, TerminationCause
from taskcontrol.domain.tasks.actions import ActionSpecification, ExecutorType


@dataclass(frozen=True, slots=True)
class ExecutorCapabilities:
    """What an executor can do, so a revision can be validated before it is deployed.

    Attributes:
        executor_type: Which executor type this adapter serves.
        supports_timeout: Whether it can enforce a run timeout.
        supports_cancellation: Whether a running process can be asked to stop.
        supports_working_directory: Whether it honours a working directory.
        supports_environment: Whether it honours environment bindings.
        supports_raw_shell: Whether it can run a raw shell string, for tasks that opt in.
    """

    executor_type: ExecutorType
    supports_timeout: bool = True
    supports_cancellation: bool = True
    supports_working_directory: bool = True
    supports_environment: bool = True
    supports_raw_shell: bool = False

    def unsupported_features(self, action: ActionSpecification) -> tuple[str, ...]:
        """Return the features an action needs that this executor does not offer.

        Checked before an execution starts, so an unsupported option is a clear validation
        error rather than a silently dropped setting.

        Args:
            action: The action to check.

        Returns:
            Names of unsupported features, empty when the action is fully supported.
        """
        missing: list[str] = []
        if action.use_raw_shell and not self.supports_raw_shell:
            missing.append("raw_shell")
        if action.working_directory and not self.supports_working_directory:
            missing.append("working_directory")
        if action.environment and not self.supports_environment:
            missing.append("environment")
        return tuple(missing)


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    """Everything an executor needs to launch one process.

    Attributes:
        action: What to run.
        environment: The fully resolved environment, secrets already materialised. This is
            the only place resolved secret values exist, and it never reaches storage,
            a log, or an audit record.
        timeout: Maximum runtime. Zero means no limit.
        termination_grace: Time between the polite signal and the forceful one.
        output_limit_bytes: Cap on captured output per stream.
        should_cancel: Polled while running; returning ``True`` requests cancellation.
    """

    action: ActionSpecification
    environment: dict[str, str] = field(default_factory=dict)
    timeout: Duration = field(default_factory=lambda: Duration(0))
    termination_grace: Duration = field(default_factory=lambda: Duration(30))
    output_limit_bytes: int = 1_048_576
    should_cancel: Callable[[], bool] | None = None


@dataclass(frozen=True, slots=True)
class ExecutionOutput:
    """What a process produced.

    stdout and stderr are captured separately and stay separate. Interleaving them loses
    the distinction between a program's result and its diagnostics, and that distinction is
    exactly what an operator needs at 3am.

    Attributes:
        stdout: Captured standard output, possibly truncated.
        stderr: Captured standard error, possibly truncated.
        stdout_truncated: Whether stdout hit the size limit.
        stderr_truncated: Whether stderr hit the size limit.
    """

    stdout: str = ""
    stderr: str = ""
    stdout_truncated: bool = False
    stderr_truncated: bool = False

    def combined(self) -> str:
        """Return a human-readable combined view.

        A convenience for display. The separate streams remain the stored truth.

        Returns:
            stdout followed by stderr, each labelled when both are present.
        """
        if self.stdout and self.stderr:
            return f"--- stdout ---\n{self.stdout}\n--- stderr ---\n{self.stderr}"
        return self.stdout or self.stderr


@dataclass(frozen=True, slots=True)
class ExecutionReport:
    """The complete result of running one process.

    Attributes:
        result: What the process did, including why it was terminated if it was.
        output: What it produced.
    """

    result: ProcessResult
    output: ExecutionOutput = field(default_factory=ExecutionOutput)

    @property
    def termination_cause(self) -> TerminationCause:
        """Why the process was terminated, when it was."""
        return self.result.termination_cause


@runtime_checkable
class Executor(Protocol):
    """Launches one process and reports what happened."""

    @property
    def capabilities(self) -> ExecutorCapabilities:
        """What this executor supports."""
        ...

    def run(self, request: ExecutionRequest) -> ExecutionReport:
        """Run a process to completion, termination, or timeout.

        Must always return a report. An executor that raises leaves the runtime unable to
        say what happened, which becomes an ``UNKNOWN`` execution — honest, but far less
        useful than a ``LAUNCH_FAILED`` with the reason.

        Args:
            request: What to run and under what limits.

        Returns:
            The report. A process that could not start is reported, not raised.
        """
        ...
