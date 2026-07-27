"""What a task actually does, described independently of any scheduler.

The safety rule of this module: **commands are argument vectors, not strings.** A vector is
passed to the operating system without a shell, so a value containing ``;`` or ``$(...)``
is an argument rather than an instruction. Raw shell strings remain possible, because real
estates need them, but only as a deliberate, recorded, elevated-risk choice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Self

from taskcontrol.common.errors import ValidationError
from taskcontrol.domain.common.values import SecretReference

MAX_ARGUMENTS = 1024
MAX_ARGUMENT_LENGTH = 32_768


class ExecutorType(StrEnum):
    """Which executor adapter runs the action.

    ``SHELL``, ``PYTHON``, and ``EXECUTABLE`` are implemented in Phase 1. The rest are
    declared so a revision can name them and validation can reject them with a clear
    message rather than a mysterious failure at run time.
    """

    SHELL = "shell"
    PYTHON = "python"
    EXECUTABLE = "executable"
    TCL = "tcl"
    HTTP = "http"
    PLUGIN = "plugin"

    @property
    def is_implemented(self) -> bool:
        """Whether an adapter for this executor exists in the current phase."""
        return self in _IMPLEMENTED_EXECUTORS


_IMPLEMENTED_EXECUTORS = frozenset(
    {ExecutorType.SHELL, ExecutorType.PYTHON, ExecutorType.EXECUTABLE}
)


class OutputCapturePolicy(StrEnum):
    """How much process output is retained."""

    CAPTURE_ALL = "capture_all"
    "Retain stdout and stderr up to the configured size limit."

    CAPTURE_TAIL = "capture_tail"
    "Retain only the final portion. For chatty jobs whose ending matters most."

    DISCARD = "discard"
    "Retain nothing. Appropriate when output may contain sensitive data."


class StdinPolicy(StrEnum):
    """What the process receives on standard input."""

    EMPTY = "empty"
    "Closed immediately. The safe default: a process waiting on stdin would hang."

    INHERIT = "inherit"
    "Inherit the runtime's stdin. Only meaningful for interactive local use."


@dataclass(frozen=True, slots=True)
class EnvironmentBinding:
    """One environment variable supplied to the process.

    A binding holds either a literal value or a secret reference, never both. The reference
    is resolved at the execution boundary by a secrets adapter, so the value never enters
    the domain, a stored revision, or a content digest.

    Attributes:
        name: The variable name.
        value: A literal value, when not secret.
        secret: A reference to resolve at execution time, when secret.
    """

    name: str
    value: str | None = None
    secret: SecretReference | None = None

    def __post_init__(self) -> None:
        """Validate the binding.

        Raises:
            ValidationError: If the name is unusable, or the binding is neither or both.
        """
        if not isinstance(self.name, str) or not self.name:
            raise ValidationError("An environment binding requires a name.")
        if not self.name.replace("_", "").isalnum() or self.name[0].isdigit():
            raise ValidationError(
                "Environment variable names must be alphanumeric with underscores "
                "and must not start with a digit.",
                details={"name": self.name},
            )
        if (self.value is None) == (self.secret is None):
            raise ValidationError(
                "An environment binding must hold exactly one of a literal value "
                "or a secret reference.",
                details={"name": self.name},
            )

    @property
    def is_secret(self) -> bool:
        """Whether this binding resolves a secret at execution time."""
        return self.secret is not None

    def to_primitive(self) -> dict[str, Any]:
        """Return a representation safe to store, digest, and display.

        Returns:
            A mapping containing the name and either the literal value or the reference.
            A secret *value* can never appear, because the domain never holds one.
        """
        if self.secret is not None:
            return {"name": self.name, "secret": self.secret.to_primitive()}
        return {"name": self.name, "value": self.value}

    @classmethod
    def from_primitive(cls, data: dict[str, Any]) -> Self:
        """Rebuild from a stored representation.

        Args:
            data: A mapping with ``name`` and one of ``value`` or ``secret``.

        Returns:
            The binding.

        Raises:
            ValidationError: If the mapping is malformed.
        """
        if not isinstance(data, dict):
            raise ValidationError("An environment binding must be a mapping.")
        secret = data.get("secret")
        return cls(
            name=data.get("name", ""),
            value=data.get("value"),
            secret=SecretReference.parse(secret) if secret is not None else None,
        )


@dataclass(frozen=True, slots=True)
class ActionSpecification:
    """What to execute, independent of scheduler and host.

    Attributes:
        executor_type: Which executor adapter runs this.
        entrypoint: The program, script, module, or URL.
        arguments: Ordered arguments, passed as a vector rather than interpolated.
        working_directory: Absolute directory to run in.
        environment: Environment bindings, literal or secret-referenced.
        stdin_policy: What the process receives on standard input.
        output_capture: How much output is retained.
        use_raw_shell: Run ``entrypoint`` through a shell, interpreting metacharacters.
            An elevated-risk option that must be chosen deliberately.
        required_capabilities: Capabilities a target must advertise to run this.
    """

    executor_type: ExecutorType
    entrypoint: str
    arguments: tuple[str, ...] = ()
    working_directory: str | None = None
    environment: tuple[EnvironmentBinding, ...] = ()
    stdin_policy: StdinPolicy = StdinPolicy.EMPTY
    output_capture: OutputCapturePolicy = OutputCapturePolicy.CAPTURE_ALL
    use_raw_shell: bool = False
    required_capabilities: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        """Validate the specification.

        Raises:
            ValidationError: If the action is unusable or unsafe as described.
        """
        if not isinstance(self.entrypoint, str) or not self.entrypoint.strip():
            raise ValidationError("An action requires an entrypoint.")

        if len(self.arguments) > MAX_ARGUMENTS:
            raise ValidationError(
                "Too many arguments.",
                details={"count": len(self.arguments), "maximum": MAX_ARGUMENTS},
            )
        for index, argument in enumerate(self.arguments):
            if not isinstance(argument, str):
                raise ValidationError(
                    "Arguments must be strings. Convert values before building the action.",
                    details={"index": index, "received_type": type(argument).__name__},
                )
            if len(argument) > MAX_ARGUMENT_LENGTH:
                raise ValidationError(
                    "Argument exceeds the maximum supported length.",
                    details={"index": index, "maximum": MAX_ARGUMENT_LENGTH},
                )
            if "\x00" in argument:
                raise ValidationError(
                    "Arguments must not contain a null byte.", details={"index": index}
                )

        if self.working_directory is not None:
            if not self.working_directory.startswith("/"):
                raise ValidationError(
                    "The working directory must be an absolute path. A relative path "
                    "depends on where the runtime happened to start.",
                    details={"working_directory": self.working_directory},
                )
            if ".." in self.working_directory.split("/"):
                raise ValidationError(
                    "The working directory must not contain a parent traversal.",
                    details={"working_directory": self.working_directory},
                )

        if self.use_raw_shell and self.executor_type is not ExecutorType.SHELL:
            raise ValidationError(
                "Raw shell interpretation is only meaningful for the shell executor.",
                details={"executor_type": str(self.executor_type)},
            )
        if self.use_raw_shell and self.arguments:
            raise ValidationError(
                "A raw shell command is a single string. Supplying separate arguments "
                "alongside it is ambiguous — put them in the command, or use an "
                "argument vector instead.",
            )

        names = [binding.name for binding in self.environment]
        if len(names) != len(set(names)):
            duplicates = sorted({name for name in names if names.count(name) > 1})
            raise ValidationError(
                "Environment variable names must be unique.",
                details={"duplicates": duplicates},
            )

    @property
    def is_elevated_risk(self) -> bool:
        """Whether this action needs the extra scrutiny raw shell use warrants."""
        return self.use_raw_shell

    @property
    def secret_references(self) -> tuple[SecretReference, ...]:
        """Every secret this action needs resolved at execution time."""
        return tuple(binding.secret for binding in self.environment if binding.secret is not None)

    def command_vector(self) -> tuple[str, ...]:
        """Return the argument vector to hand to the operating system.

        Returns:
            The entrypoint followed by its arguments.

        Raises:
            DomainRuleViolationError: If this action is a raw shell command, which has no
                argument vector. Asking for one indicates the caller is about to run it
                the wrong way.
        """
        if self.use_raw_shell:
            from taskcontrol.common.errors import DomainRuleViolationError

            raise DomainRuleViolationError(
                "A raw shell action has no argument vector; it is a shell string.",
            )
        return (self.entrypoint, *self.arguments)

    def to_primitive(self) -> dict[str, Any]:
        """Return a stable, digestible representation.

        Returns:
            A mapping with deterministic ordering, safe to store and digest.
        """
        return {
            "executor_type": str(self.executor_type),
            "entrypoint": self.entrypoint,
            "arguments": list(self.arguments),
            "working_directory": self.working_directory,
            "environment": [binding.to_primitive() for binding in self.environment],
            "stdin_policy": str(self.stdin_policy),
            "output_capture": str(self.output_capture),
            "use_raw_shell": self.use_raw_shell,
            "required_capabilities": sorted(self.required_capabilities),
        }

    @classmethod
    def from_primitive(cls, data: dict[str, Any]) -> Self:
        """Rebuild from a stored representation.

        Args:
            data: A previously produced mapping.

        Returns:
            The action specification.

        Raises:
            ValidationError: If the mapping is malformed or names an unknown executor.
        """
        if not isinstance(data, dict):
            raise ValidationError("An action specification must be a mapping.")
        try:
            executor = ExecutorType(data["executor_type"])
        except KeyError as exc:
            raise ValidationError("An action specification requires an executor type.") from exc
        except ValueError as exc:
            raise ValidationError(
                "Unknown executor type.",
                details={
                    "executor_type": data.get("executor_type"),
                    "supported": sorted(member.value for member in ExecutorType),
                },
            ) from exc

        return cls(
            executor_type=executor,
            entrypoint=data.get("entrypoint", ""),
            arguments=tuple(data.get("arguments") or ()),
            working_directory=data.get("working_directory"),
            environment=tuple(
                EnvironmentBinding.from_primitive(item) for item in data.get("environment") or ()
            ),
            stdin_policy=StdinPolicy(data.get("stdin_policy", StdinPolicy.EMPTY)),
            output_capture=OutputCapturePolicy(
                data.get("output_capture", OutputCapturePolicy.CAPTURE_ALL)
            ),
            use_raw_shell=bool(data.get("use_raw_shell", False)),
            required_capabilities=frozenset(data.get("required_capabilities") or ()),
        )
