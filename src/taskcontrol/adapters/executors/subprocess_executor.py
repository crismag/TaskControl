"""Running work as an operating-system process.

One implementation serves shell, Python, and executable actions: they differ in how the
command is assembled, not in how a process is supervised. Sharing the supervision means
timeout enforcement, termination, and output capture are written once and behave
identically for all three.

Three things here are security-relevant and deliberate:

* **Argument vectors, not strings.** ``shell=False`` is the default and the norm, so a
  value containing ``;`` or ``$(...)`` is an argument, not an instruction. Raw shell mode
  exists because real estates need it, but it must be opted into on the task definition.
* **The environment is replaced, not inherited.** A process gets exactly what the task
  resolved plus a minimal base. Inheriting the parent environment would leak whatever
  happened to be in the TaskControl process — including its own secrets.
* **Output is bounded.** A runaway process that prints forever must not exhaust memory. It
  is truncated and the truncation is recorded, never silently dropped.

Termination is two-stage: a polite signal, a grace period, then a forceful kill. A task
that ignores the first signal must still be stoppable, or a scheduled system accumulates
stuck processes until it stops scheduling anything.
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass

from taskcontrol.common.errors import ValidationError
from taskcontrol.domain.common.values import Duration
from taskcontrol.domain.execution.results import (
    ProcessResult,
    TerminationCause,
    TerminationMode,
)
from taskcontrol.domain.tasks.actions import ActionSpecification, ExecutorType
from taskcontrol.infrastructure.logging import get_logger
from taskcontrol.ports.executor import (
    ExecutionOutput,
    ExecutionReport,
    ExecutionRequest,
    ExecutorCapabilities,
)

logger = get_logger(__name__)

CANCELLATION_POLL_SECONDS = 0.05
"""How often cancellation is checked while a process runs."""

_BASE_ENVIRONMENT_KEYS = ("PATH", "LANG", "LC_ALL", "TZ")
"""Inherited from the parent because a process without them behaves surprisingly."""


@dataclass(frozen=True, slots=True)
class _Termination:
    """A decision to stop a running process."""

    cause: TerminationCause
    signal_number: int


class SubprocessExecutor:
    """Runs an action as an operating-system process.

    Args:
        executor_type: Which action type this instance serves.
        python_interpreter: Interpreter for Python actions. Defaults to the one running
            TaskControl, which is a convenience rather than a requirement — the domain does
            not insist a task share TaskControl's interpreter.
        shell_program: Shell used for raw-shell actions.
    """

    def __init__(
        self,
        executor_type: ExecutorType = ExecutorType.SHELL,
        *,
        python_interpreter: str | None = None,
        shell_program: str = "/bin/sh",
    ) -> None:
        self._executor_type = executor_type
        self._python_interpreter = python_interpreter or sys.executable
        self._shell_program = shell_program

    @property
    def capabilities(self) -> ExecutorCapabilities:
        """What this executor supports.

        Raw shell is advertised only for the shell executor, so a Python action that sets
        it is rejected before anything runs rather than quietly ignored.
        """
        return ExecutorCapabilities(
            executor_type=self._executor_type,
            supports_timeout=True,
            supports_cancellation=True,
            supports_working_directory=True,
            supports_environment=True,
            supports_raw_shell=self._executor_type is ExecutorType.SHELL,
        )

    def run(self, request: ExecutionRequest) -> ExecutionReport:
        """Run a process to completion, termination, or timeout.

        Always returns a report. A process that cannot start is reported as not started,
        with the reason — raising here would leave the runtime unable to explain what
        happened.

        Args:
            request: What to run and under what limits.

        Returns:
            The report.
        """
        unsupported = self.capabilities.unsupported_features(request.action)
        if unsupported:
            return _not_started(
                f"This executor does not support: {', '.join(unsupported)}.",
            )

        try:
            command = self._build_command(request.action)
        except ValidationError as exc:
            return _not_started(exc.message)

        environment = self._build_environment(request.environment)
        started_monotonic = time.monotonic()

        try:
            process = subprocess.Popen(  # noqa: S603 - vectors are validated; shell is opt-in
                command,
                cwd=request.action.working_directory,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                shell=request.action.use_raw_shell,
                text=True,
                errors="replace",
                # A new process group so termination reaches the whole tree. Without it a
                # shell script's children survive the kill and keep holding resources.
                start_new_session=True,
            )
        except (OSError, ValueError) as exc:
            return _not_started(
                f"{type(exc).__name__}: {exc}",
                duration=_elapsed(started_monotonic),
            )

        return self._supervise(process, request, started_monotonic)

    def _supervise(
        self,
        process: subprocess.Popen[str],
        request: ExecutionRequest,
        started_monotonic: float,
    ) -> ExecutionReport:
        """Wait for a process, enforcing timeout and cancellation.

        Output is drained on background threads. A process whose pipe buffer fills while
        nobody reads it blocks forever, so waiting without draining would deadlock exactly
        the chatty jobs most likely to time out.
        """
        streams = _StreamCollector(process, request.output_limit_bytes)
        try:
            termination = self._wait(process, request, started_monotonic)
            streams.join()
        finally:
            # Pipes are not closed by Popen on our behalf. Leaving them open leaks file
            # descriptors, and a long-running TaskControl process would eventually run out
            # — which is exactly the failure a scheduled system must not have.
            _close_pipes(process)

        duration = _elapsed(started_monotonic)
        output = streams.output()
        stdout_bytes = len(output.stdout.encode("utf-8"))
        stderr_bytes = len(output.stderr.encode("utf-8"))
        truncated = output.stdout_truncated or output.stderr_truncated

        if termination is not None:
            return ExecutionReport(
                result=ProcessResult(
                    termination=TerminationMode.SIGNALLED,
                    signal_number=termination.signal_number,
                    duration=duration,
                    termination_cause=termination.cause,
                    stdout_bytes=stdout_bytes,
                    stderr_bytes=stderr_bytes,
                    output_truncated=truncated,
                ),
                output=output,
            )

        return_code = process.returncode
        if return_code is not None and return_code < 0:
            # A negative return code means a signal TaskControl did not send.
            return ExecutionReport(
                result=ProcessResult(
                    termination=TerminationMode.SIGNALLED,
                    signal_number=-return_code,
                    duration=duration,
                    termination_cause=TerminationCause.EXTERNAL,
                    stdout_bytes=stdout_bytes,
                    stderr_bytes=stderr_bytes,
                    output_truncated=truncated,
                ),
                output=output,
            )

        return ExecutionReport(
            result=ProcessResult(
                termination=TerminationMode.EXITED,
                exit_code=return_code if return_code is not None else 0,
                duration=duration,
                stdout_bytes=stdout_bytes,
                stderr_bytes=stderr_bytes,
                output_truncated=truncated,
            ),
            output=output,
        )

    def _wait(
        self,
        process: subprocess.Popen[str],
        request: ExecutionRequest,
        started_monotonic: float,
    ) -> _Termination | None:
        """Wait for the process, terminating it on timeout or cancellation.

        Returns:
            The termination decision, or ``None`` when the process ended on its own.
        """
        timeout_seconds = request.timeout.seconds or None

        while True:
            if process.poll() is not None:
                return None

            elapsed = time.monotonic() - started_monotonic

            if timeout_seconds is not None and elapsed >= timeout_seconds:
                logger.warning(
                    "Terminating process: run timeout exceeded",
                    extra={"pid": process.pid, "elapsed_seconds": round(elapsed, 3)},
                )
                return self._terminate(process, TerminationCause.RUN_TIMEOUT, request)

            if request.should_cancel is not None and request.should_cancel():
                logger.info(
                    "Terminating process: cancellation requested",
                    extra={"pid": process.pid, "elapsed_seconds": round(elapsed, 3)},
                )
                return self._terminate(process, TerminationCause.CANCELLATION_REQUESTED, request)

            time.sleep(CANCELLATION_POLL_SECONDS)

    def _terminate(
        self,
        process: subprocess.Popen[str],
        cause: TerminationCause,
        request: ExecutionRequest,
    ) -> _Termination:
        """Stop a running process, escalating if it does not comply.

        SIGTERM lets a task clean up. After the grace period SIGKILL removes the choice,
        because an unstoppable task holds its overlap lock forever.

        Returns:
            The termination, carrying the signal that actually ended the process.
        """
        sent = signal.SIGTERM
        _signal_group(process, signal.SIGTERM)

        try:
            process.wait(timeout=max(request.termination_grace.seconds, 0) or None)
        except subprocess.TimeoutExpired:
            logger.warning(
                "Process ignored SIGTERM; escalating to SIGKILL",
                extra={"pid": process.pid, "grace_seconds": request.termination_grace.seconds},
            )
            _signal_group(process, signal.SIGKILL)
            sent = signal.SIGKILL
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:  # pragma: no cover - unreachable after SIGKILL
                logger.error("Process survived SIGKILL", extra={"pid": process.pid})

        return _Termination(cause=cause, signal_number=int(sent))

    def _build_command(self, action: ActionSpecification) -> list[str] | str:
        """Assemble the command for an action.

        Returns:
            An argument vector, or a single string when the task opted into raw shell.

        Raises:
            ValidationError: If the action does not suit this executor.
        """
        if action.use_raw_shell:
            return action.entrypoint

        match self._executor_type:
            case ExecutorType.PYTHON:
                return [self._python_interpreter, action.entrypoint, *action.arguments]
            case ExecutorType.SHELL | ExecutorType.EXECUTABLE:
                return list(action.command_vector())
            case _:
                raise ValidationError(
                    "This executor cannot run that action type.",
                    details={"executor_type": str(self._executor_type)},
                )

    def _build_environment(self, resolved: dict[str, str]) -> dict[str, str]:
        """Return the environment the process will see.

        Replaced rather than inherited. A task gets exactly what it resolved plus a minimal
        base; inheriting the parent environment would hand every task whatever secrets
        happened to be in the TaskControl process.
        """
        environment = {key: os.environ[key] for key in _BASE_ENVIRONMENT_KEYS if key in os.environ}
        environment.update(resolved)
        return environment


class _StreamCollector:
    """Drains stdout and stderr on background threads, bounded.

    Draining concurrently is not an optimisation: a process whose pipe buffer fills while
    nobody reads blocks forever, so a sequential read-then-wait would deadlock the chatty
    jobs most likely to need a timeout.
    """

    def __init__(self, process: subprocess.Popen[str], limit_bytes: int) -> None:
        self._limit = limit_bytes
        self._stdout: list[str] = []
        self._stderr: list[str] = []
        self._stdout_truncated = False
        self._stderr_truncated = False

        self._threads = [
            threading.Thread(
                target=self._drain, args=(process.stdout, self._stdout, "stdout"), daemon=True
            ),
            threading.Thread(
                target=self._drain, args=(process.stderr, self._stderr, "stderr"), daemon=True
            ),
        ]
        for thread in self._threads:
            thread.start()

    def _drain(self, stream: object, sink: list[str], name: str) -> None:
        """Read a stream until it closes, stopping at the size limit."""
        if stream is None:  # pragma: no cover - pipes are always requested
            return
        collected = 0
        try:
            for line in stream:  # type: ignore[attr-defined]
                if collected >= self._limit:
                    if name == "stdout":
                        self._stdout_truncated = True
                    else:
                        self._stderr_truncated = True
                    continue  # Keep draining so the process is never blocked on a full pipe.
                sink.append(line)
                collected += len(line.encode("utf-8"))
        except (OSError, ValueError):  # pragma: no cover - stream closed mid-read
            pass

    def join(self, timeout: float = 5.0) -> None:
        """Wait for both streams to finish draining."""
        for thread in self._threads:
            thread.join(timeout=timeout)

    def output(self) -> ExecutionOutput:
        """Return what was captured."""
        return ExecutionOutput(
            stdout="".join(self._stdout),
            stderr="".join(self._stderr),
            stdout_truncated=self._stdout_truncated,
            stderr_truncated=self._stderr_truncated,
        )


def _close_pipes(process: subprocess.Popen[str]) -> None:
    """Close a process's pipes and reap it.

    Args:
        process: The process to clean up after.
    """
    for stream in (process.stdout, process.stderr, process.stdin):
        if stream is not None:
            with contextlib.suppress(OSError, ValueError):
                stream.close()
    with contextlib.suppress(subprocess.TimeoutExpired, OSError):
        process.wait(timeout=1)


def _signal_group(process: subprocess.Popen[str], sig: signal.Signals) -> None:
    """Signal a process group, falling back to the process itself.

    The group is signalled so a shell script's children die with it. Without that, killing
    a wrapper leaves the real work running and holding its resources.
    """
    try:
        os.killpg(os.getpgid(process.pid), sig)
    except (ProcessLookupError, PermissionError, OSError):
        # No process group (or not permitted): fall back to the process itself. Already
        # gone is a success for our purposes.
        with contextlib.suppress(ProcessLookupError):
            process.send_signal(sig)


def _elapsed(started_monotonic: float) -> Duration:
    """Return elapsed time as a whole-second duration."""
    return Duration(max(int(time.monotonic() - started_monotonic), 0))


def _not_started(reason: str, duration: Duration | None = None) -> ExecutionReport:
    """Return a report for a process that never started."""
    return ExecutionReport(result=ProcessResult.not_started(reason, duration))
