"""Stable identifiers.

Identifiers are opaque and carry no hierarchy. A readable name is a mutable label; the
identifier is the stable thing. Encoding tenant, owner, or environment into an identifier
would make those attributes unchangeable and would foreclose the federation boundary the
product intends to keep reachable.

Identifiers are UUIDv7: random like UUIDv4, but with a millisecond timestamp in the high
bits, so they sort by creation time. That matters for database index locality and for
ordering revisions and execution attempts without a separate sequence column.

Python 3.12 has no :func:`uuid.uuid7`, so generation is implemented here against RFC 9562.
"""

from __future__ import annotations

import secrets
import time
import uuid
from typing import Any, ClassVar, Self

from taskcontrol.common.errors import ValidationError

_UUID_VERSION_7 = 7
_RFC_4122_VARIANT = 0b10


def generate_uuid7(*, timestamp_ms: int | None = None) -> uuid.UUID:
    """Generate a UUIDv7.

    Layout per RFC 9562: 48 bits of Unix milliseconds, 4 version bits, 12 random bits,
    2 variant bits, 62 random bits.

    Args:
        timestamp_ms: Unix milliseconds to embed. Defaults to now. Injectable so tests can
            assert ordering without sleeping.

    Returns:
        A version 7 UUID.

    Raises:
        ValidationError: If the timestamp does not fit in the 48-bit field.
    """
    millis = time.time_ns() // 1_000_000 if timestamp_ms is None else timestamp_ms
    if not 0 <= millis < (1 << 48):
        raise ValidationError(
            "Timestamp does not fit in the 48-bit UUIDv7 field.",
            details={"timestamp_ms": millis},
        )

    rand_a = secrets.randbits(12)
    rand_b = secrets.randbits(62)

    value = millis << 80
    value |= _UUID_VERSION_7 << 76
    value |= rand_a << 64
    value |= _RFC_4122_VARIANT << 62
    value |= rand_b
    return uuid.UUID(int=value)


class EntityId:
    """An opaque, stable identifier for a domain entity.

    Subclasses carry a prefix so that an identifier is self-describing in a log, a URL, or
    a support conversation — ``task_01890c...`` rather than a bare UUID whose kind must be
    inferred from context. The prefix is presentation; the UUID is identity.

    Attributes:
        prefix: Short kind marker, set by each subclass.
    """

    prefix: ClassVar[str] = "ent"

    __slots__ = ("_value",)

    def __init__(self, value: uuid.UUID | str) -> None:
        """Build an identifier from a UUID or its string form.

        Args:
            value: A :class:`uuid.UUID`, a plain UUID string, or a prefixed string
                produced by :meth:`__str__`.

        Raises:
            ValidationError: If the value is not a well-formed identifier of this kind.
        """
        self._value = self._coerce(value)

    @classmethod
    def _coerce(cls, value: uuid.UUID | str) -> uuid.UUID:
        """Normalise accepted input forms to a UUID."""
        if isinstance(value, uuid.UUID):
            return value
        if not isinstance(value, str):
            raise ValidationError(
                f"{cls.__name__} must be built from a UUID or string.",
                details={"received_type": type(value).__name__},
            )

        text = value.strip()
        if not text:
            raise ValidationError(f"{cls.__name__} must not be empty.")

        prefix, separator, remainder = text.partition("_")
        if separator:
            if prefix != cls.prefix:
                raise ValidationError(
                    f"{cls.__name__} expects the prefix {cls.prefix!r}.",
                    details={"expected_prefix": cls.prefix, "received_prefix": prefix},
                )
            text = remainder

        try:
            return uuid.UUID(text)
        except ValueError as exc:
            raise ValidationError(
                f"{cls.__name__} is not a well-formed UUID.",
                details={"identifier_kind": cls.prefix},
            ) from exc

    @classmethod
    def generate(cls, *, timestamp_ms: int | None = None) -> Self:
        """Create a new identifier.

        Args:
            timestamp_ms: Unix milliseconds to embed. Injectable for deterministic tests.

        Returns:
            A new identifier of this kind.
        """
        return cls(generate_uuid7(timestamp_ms=timestamp_ms))

    @property
    def value(self) -> uuid.UUID:
        """The underlying UUID."""
        return self._value

    @property
    def created_at_ms(self) -> int | None:
        """Unix milliseconds embedded in the identifier, when it is a UUIDv7.

        Returns:
            The embedded timestamp, or ``None`` for an identifier of another version.
            Never treat this as an authoritative creation time — it is a hint for
            ordering and debugging, not a substitute for a recorded timestamp.
        """
        if self._value.version != _UUID_VERSION_7:
            return None
        return self._value.int >> 80

    def __str__(self) -> str:
        """Return the prefixed string form, which is what appears on any wire."""
        return f"{self.prefix}_{self._value}"

    def __repr__(self) -> str:
        """Return an unambiguous representation."""
        return f"{type(self).__name__}({str(self)!r})"

    def __eq__(self, other: object) -> bool:
        """Identifiers of different kinds are never equal, even with the same UUID."""
        if type(other) is not type(self):
            return NotImplemented
        return self._value == other._value

    def __hash__(self) -> int:
        """Hash on kind and value so distinct kinds do not collide in a set."""
        return hash((type(self).__name__, self._value))

    def __lt__(self, other: Self) -> bool:
        """Order by UUID, which for UUIDv7 is creation order."""
        if type(other) is not type(self):
            return NotImplemented
        return self._value < other._value

    def to_primitive(self) -> str:
        """Return the transport representation.

        Returns:
            The prefixed string form.
        """
        return str(self)

    @classmethod
    def from_primitive(cls, value: Any) -> Self:
        """Rebuild an identifier from its transport representation.

        Args:
            value: The stored or transmitted value.

        Returns:
            The identifier.

        Raises:
            ValidationError: If the value is not a valid identifier of this kind.
        """
        return cls(value)


class TaskId(EntityId):
    """Identifies a Task — the durable identity of an operational activity."""

    prefix: ClassVar[str] = "task"


class TaskRevisionId(EntityId):
    """Identifies an immutable TaskRevision."""

    prefix: ClassVar[str] = "rev"


class ProfileId(EntityId):
    """Identifies a configuration Profile."""

    prefix: ClassVar[str] = "prof"


class CalendarId(EntityId):
    """Identifies a Calendar."""

    prefix: ClassVar[str] = "cal"


class ScheduleId(EntityId):
    """Identifies a Schedule."""

    prefix: ClassVar[str] = "sched"


class RunConditionId(EntityId):
    """Identifies a reusable RunCondition."""

    prefix: ClassVar[str] = "cond"


class TargetId(EntityId):
    """Identifies a Target.

    Modelled from the first release even though only the local target exists, so that
    remote targets do not require a schema change (ADR 0018).
    """

    prefix: ClassVar[str] = "tgt"


class ExecutionId(EntityId):
    """Identifies one Execution — one evaluation of a trigger, run or not."""

    prefix: ClassVar[str] = "exec"


class AttemptId(EntityId):
    """Identifies one ExecutionAttempt within an Execution."""

    prefix: ClassVar[str] = "att"


class CollectionId(EntityId):
    """Identifies a TaskCollection."""

    prefix: ClassVar[str] = "coll"


class OwnerId(EntityId):
    """Identifies an owning user, team, or service identity."""

    prefix: ClassVar[str] = "own"
