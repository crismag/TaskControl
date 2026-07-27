"""Cross-cutting stable concepts shared by every layer.

This package is deliberately small. It holds the error taxonomy and, later, a handful of
genuinely cross-cutting utilities. It must not become a home for domain behaviour that
was inconvenient to place correctly.
"""

from __future__ import annotations

from taskcontrol.common.errors import (
    ConfigurationError,
    ConflictError,
    DomainRuleViolationError,
    ErrorCode,
    NotAuthorisedError,
    NotFoundError,
    PermanentInfrastructureError,
    TaskControlError,
    TransientInfrastructureError,
    ValidationError,
)

__all__ = [
    "ConfigurationError",
    "ConflictError",
    "DomainRuleViolationError",
    "ErrorCode",
    "NotAuthorisedError",
    "NotFoundError",
    "PermanentInfrastructureError",
    "TaskControlError",
    "TransientInfrastructureError",
    "ValidationError",
]
