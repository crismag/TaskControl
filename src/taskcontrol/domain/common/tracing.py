"""Correlation and idempotency keys.

Both are caller-supplied strings rather than generated identifiers, because both exist to
let an *external* system tie its request to what TaskControl did with it. Validation is
therefore about safety and bounds, not about owning the format.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Self

from taskcontrol.common.errors import ValidationError
from taskcontrol.domain.common.identifiers import generate_uuid7

_SAFE_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._:\-]+$")

KEY_MAX_LENGTH = 128


def _validate_key(type_name: str, value: object) -> None:
    """Validate a caller-supplied key.

    Args:
        type_name: Name used in the error message.
        value: The candidate key.

    Raises:
        ValidationError: If the key is unusable or unsafe.
    """
    if not isinstance(value, str):
        raise ValidationError(
            f"{type_name} must be a string.",
            details={"received_type": type(value).__name__},
        )
    if not value:
        raise ValidationError(f"{type_name} must not be empty.")
    if len(value) > KEY_MAX_LENGTH:
        raise ValidationError(
            f"{type_name} is too long.",
            details={"length": len(value), "maximum": KEY_MAX_LENGTH},
        )
    if not _SAFE_KEY_PATTERN.match(value):
        raise ValidationError(
            f"{type_name} may contain only letters, digits, dot, underscore, colon, and hyphen.",
        )


@dataclass(frozen=True, slots=True)
class CorrelationId:
    """Ties together every record produced while handling one request or execution.

    Accepted from a client so a trace can span systems, which is exactly why it is
    validated: an unvalidated caller-supplied value ends up in log files, response
    headers, and audit records.

    Attributes:
        value: The correlation string.
    """

    value: str

    def __post_init__(self) -> None:
        """Validate the value.

        Raises:
            ValidationError: If empty, too long, or containing unsafe characters.
        """
        _validate_key("CorrelationId", self.value)

    @classmethod
    def generate(cls) -> Self:
        """Return a new correlation identifier."""
        return cls(str(generate_uuid7()))

    @classmethod
    def from_primitive(cls, value: Any) -> Self:
        """Build from a stored or transmitted value."""
        return cls(value)

    def to_primitive(self) -> str:
        """Return the correlation string."""
        return self.value

    def __str__(self) -> str:
        """Return the correlation string."""
        return self.value


@dataclass(frozen=True, slots=True)
class IdempotencyKey:
    """Makes a repeated request safe to replay.

    A duplicate trigger delivery must not produce a duplicate execution side effect. This
    key is what lets the application recognise the repeat, so it is supplied by the caller
    and stays stable across their retries.

    Attributes:
        value: The idempotency string.
    """

    value: str

    def __post_init__(self) -> None:
        """Validate the value.

        Raises:
            ValidationError: If empty, too long, or containing unsafe characters.
        """
        _validate_key("IdempotencyKey", self.value)

    @classmethod
    def from_primitive(cls, value: Any) -> Self:
        """Build from a stored or transmitted value."""
        return cls(value)

    def to_primitive(self) -> str:
        """Return the idempotency string."""
        return self.value

    def __str__(self) -> str:
        """Return the idempotency string."""
        return self.value
