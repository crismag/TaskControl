"""The TaskControl error taxonomy.

Every error raised by TaskControl carries a stable, machine-readable code so that API
responses, CLI exit codes, logs, and audit records can agree on what went wrong without
parsing prose. The taxonomy follows
``development/engineering/standards/20_PYTHON_AND_APPLICATION_STANDARDS.md``.

Codes are part of the public contract. Renaming one is a breaking change; adding one is
not.

Errors here describe *failures of an operation*. They are not the vocabulary for the
outcome of an execution — that is :mod:`taskcontrol.domain.execution`, fixed by ADR 0016.
A task that runs and exits non-zero is a successful API call reporting a ``failed``
execution, not a ``TaskControlError``.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    """Stable, machine-readable error identifiers.

    Values are ``lower_snake_case`` on every wire, matching the serialisation rule that
    ADR 0016 sets for the execution vocabulary.
    """

    VALIDATION_FAILED = "validation_failed"
    DOMAIN_RULE_VIOLATION = "domain_rule_violation"
    NOT_AUTHORISED = "not_authorised"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    CONFIGURATION_INVALID = "configuration_invalid"
    TRANSIENT_INFRASTRUCTURE_FAILURE = "transient_infrastructure_failure"
    PERMANENT_INFRASTRUCTURE_FAILURE = "permanent_infrastructure_failure"


class TaskControlError(Exception):
    """Base class for every error TaskControl raises deliberately.

    Attributes:
        code: The stable machine-readable classification.
        message: A human-readable explanation. Must never contain a secret value.
        details: Structured context for the caller, such as offending field names.
            Must never contain a secret value.

    Args:
        message: Human-readable explanation.
        details: Optional structured context.
    """

    code: ErrorCode = ErrorCode.PERMANENT_INFRASTRUCTURE_FAILURE
    "Subclasses override this. The base value is deliberately pessimistic."

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = details or {}

    def __str__(self) -> str:
        """Return the human-readable message."""
        return self.message

    def to_dict(self) -> dict[str, Any]:
        """Return a transport-neutral representation.

        The result is safe to serialise into an API response or a log record: it contains
        no traceback, no internal path, and no secret value.

        Returns:
            A mapping with ``code``, ``message``, and ``details`` keys.
        """
        return {"code": str(self.code), "message": self.message, "details": self.details}


class ValidationError(TaskControlError):
    """Input failed field-level or cross-field validation."""

    code = ErrorCode.VALIDATION_FAILED


class DomainRuleViolationError(TaskControlError):
    """A domain invariant or an illegal state transition was attempted."""

    code = ErrorCode.DOMAIN_RULE_VIOLATION


class NotAuthorisedError(TaskControlError):
    """The principal is known but not permitted to perform the action."""

    code = ErrorCode.NOT_AUTHORISED


class NotFoundError(TaskControlError):
    """The requested resource does not exist, or is not visible to the principal."""

    code = ErrorCode.NOT_FOUND


class ConflictError(TaskControlError):
    """The request conflicts with current state, such as a stale revision."""

    code = ErrorCode.CONFLICT


class ConfigurationError(TaskControlError):
    """Configuration is missing, malformed, or internally inconsistent.

    Raised at startup. A process that cannot build valid settings must not start and
    serve requests with defaults it invented.
    """

    code = ErrorCode.CONFIGURATION_INVALID


class TransientInfrastructureError(TaskControlError):
    """An external dependency failed in a way that may succeed if retried."""

    code = ErrorCode.TRANSIENT_INFRASTRUCTURE_FAILURE


class PermanentInfrastructureError(TaskControlError):
    """An external dependency failed in a way that retrying will not resolve."""

    code = ErrorCode.PERMANENT_INFRASTRUCTURE_FAILURE
