"""Validated value objects shared across the domain.

Every type here refuses to hold an invalid value. That is the point: once a
:class:`UtcTimestamp` exists, no downstream code needs to ask whether it is timezone-aware,
and once a :class:`Slug` exists, nothing needs to re-check it for path separators.

The engineering standards forbid dictionaries as permanent substitutes for stable domain
types, so these are the currency of the domain layer. Each provides ``to_primitive`` and
``from_primitive`` so a boundary can serialise them without the domain knowing what a
boundary is.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from taskcontrol.common.errors import ValidationError

_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_SECRET_REFERENCE_PATTERN = re.compile(r"^(?P<provider>[a-z][a-z0-9_-]*)://(?P<path>[^\s]+)$")
_DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_SCHEMA_VERSION_PATTERN = re.compile(r"^(?P<major>\d+)\.(?P<minor>\d+)$")

SLUG_MAX_LENGTH = 100
MAX_DURATION_SECONDS = 86_400 * 366


@dataclass(frozen=True, slots=True, order=True)
class UtcTimestamp:
    """An instant, always stored in UTC.

    TaskControl persists UTC and displays local time. A naive datetime is rejected rather
    than assumed to be UTC, because that assumption is how scheduled systems silently run
    an hour early twice a year.

    Attributes:
        value: A timezone-aware datetime normalised to UTC.
    """

    value: datetime

    def __post_init__(self) -> None:
        """Validate awareness and normalise to UTC.

        Raises:
            ValidationError: If the datetime is naive or not a datetime.
        """
        if not isinstance(self.value, datetime):
            raise ValidationError(
                "UtcTimestamp requires a datetime.",
                details={"received_type": type(self.value).__name__},
            )
        if self.value.tzinfo is None or self.value.utcoffset() is None:
            raise ValidationError(
                "UtcTimestamp requires a timezone-aware datetime. "
                "A naive datetime has no defined instant.",
            )
        object.__setattr__(self, "value", self.value.astimezone(UTC))

    @classmethod
    def now(cls) -> Self:
        """Return the current instant.

        Prefer injecting a clock where the time affects a decision; this exists for the
        edges where it genuinely does not.

        Returns:
            The current instant in UTC.
        """
        return cls(datetime.now(UTC))

    @classmethod
    def from_primitive(cls, value: Any) -> Self:
        """Parse an ISO-8601 string or accept a datetime.

        Args:
            value: An ISO-8601 string with an offset, or a timezone-aware datetime.

        Returns:
            The timestamp.

        Raises:
            ValidationError: If the value cannot be parsed or lacks an offset.
        """
        if isinstance(value, datetime):
            return cls(value)
        if not isinstance(value, str):
            raise ValidationError(
                "UtcTimestamp must be an ISO-8601 string or a datetime.",
                details={"received_type": type(value).__name__},
            )
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValidationError(
                "UtcTimestamp is not a valid ISO-8601 timestamp.",
            ) from exc
        return cls(parsed)

    def to_primitive(self) -> str:
        """Return the ISO-8601 representation in UTC.

        Returns:
            An ISO-8601 string ending in ``+00:00``.
        """
        return self.value.isoformat()

    def __str__(self) -> str:
        """Return the ISO-8601 representation."""
        return self.to_primitive()


@dataclass(frozen=True, slots=True, order=True)
class Duration:
    """A non-negative span of time, held in whole seconds.

    Used for timeouts, backoff, grace periods, and freshness windows. Whole seconds are
    deliberate: sub-second precision would imply a scheduling accuracy the product does not
    offer, and would invite comparisons that fail on floating-point noise.

    Attributes:
        seconds: The span, zero or greater.
    """

    seconds: int

    def __post_init__(self) -> None:
        """Validate the span.

        Raises:
            ValidationError: If negative, non-integral, or implausibly large.
        """
        if isinstance(self.seconds, bool) or not isinstance(self.seconds, int):
            raise ValidationError(
                "Duration requires whole seconds as an integer.",
                details={"received_type": type(self.seconds).__name__},
            )
        if self.seconds < 0:
            raise ValidationError(
                "Duration must not be negative.", details={"seconds": self.seconds}
            )
        if self.seconds > MAX_DURATION_SECONDS:
            raise ValidationError(
                "Duration exceeds the supported maximum of one year.",
                details={"seconds": self.seconds, "maximum": MAX_DURATION_SECONDS},
            )

    @classmethod
    def of(cls, *, hours: int = 0, minutes: int = 0, seconds: int = 0) -> Self:
        """Build a duration from parts.

        Args:
            hours: Whole hours.
            minutes: Whole minutes.
            seconds: Whole seconds.

        Returns:
            The combined duration.
        """
        return cls(hours * 3600 + minutes * 60 + seconds)

    @classmethod
    def from_primitive(cls, value: Any) -> Self:
        """Accept an integer number of seconds.

        Args:
            value: Whole seconds.

        Returns:
            The duration.

        Raises:
            ValidationError: If the value is not a whole number of seconds.
        """
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValidationError(
                "Duration must be an integer number of seconds.",
                details={"received_type": type(value).__name__},
            )
        return cls(value)

    def to_primitive(self) -> int:
        """Return the span in whole seconds."""
        return self.seconds

    def as_timedelta(self) -> timedelta:
        """Return the span as a :class:`datetime.timedelta`."""
        return timedelta(seconds=self.seconds)

    @property
    def is_zero(self) -> bool:
        """Whether the span is zero, which usually means "disabled"."""
        return self.seconds == 0

    def __str__(self) -> str:
        """Return a compact human-readable form such as ``1h30m`` or ``45s``."""
        if self.seconds == 0:
            return "0s"
        hours, remainder = divmod(self.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        parts = [
            f"{hours}h" if hours else "",
            f"{minutes}m" if minutes else "",
            f"{seconds}s" if seconds else "",
        ]
        return "".join(parts)


@dataclass(frozen=True, slots=True)
class TimeZoneName:
    """An IANA time zone name, validated against the system database.

    Stored as a name rather than a fixed offset. An offset cannot express "Europe/London",
    so it cannot survive a daylight-saving transition, and a schedule that means 06:00
    local must keep meaning 06:00 local.

    Attributes:
        name: An IANA identifier such as ``Europe/London``.
    """

    name: str

    def __post_init__(self) -> None:
        """Validate the zone exists.

        Raises:
            ValidationError: If the name is empty or unknown to the zone database.
        """
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValidationError("TimeZoneName must be a non-empty string.")
        try:
            ZoneInfo(self.name)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValidationError(
                "Unknown IANA time zone.",
                details={"timezone": self.name},
            ) from exc

    @classmethod
    def utc(cls) -> Self:
        """Return the UTC zone."""
        return cls("UTC")

    @classmethod
    def from_primitive(cls, value: Any) -> Self:
        """Build from a stored name.

        Args:
            value: An IANA time zone name.

        Returns:
            The validated zone name.

        Raises:
            ValidationError: If the value is not a known zone.
        """
        if not isinstance(value, str):
            raise ValidationError(
                "TimeZoneName must be a string.",
                details={"received_type": type(value).__name__},
            )
        return cls(value)

    def to_primitive(self) -> str:
        """Return the IANA name."""
        return self.name

    def zone_info(self) -> ZoneInfo:
        """Return the loaded zone, for converting an instant to local time."""
        return ZoneInfo(self.name)

    def __str__(self) -> str:
        """Return the IANA name."""
        return self.name


@dataclass(frozen=True, slots=True)
class Slug:
    """A stable, URL- and CLI-safe name.

    Lower case, digits, and single hyphens. A slug appears in URLs, generated filenames,
    and CLI arguments, so anything that could be a path separator, a shell metacharacter,
    or a case-sensitivity trap is rejected at construction.

    Attributes:
        value: The slug text.
    """

    value: str

    def __post_init__(self) -> None:
        """Validate the slug.

        Raises:
            ValidationError: If the value is empty, too long, or not slug-shaped.
        """
        if not isinstance(self.value, str):
            raise ValidationError(
                "Slug must be a string.", details={"received_type": type(self.value).__name__}
            )
        if not self.value:
            raise ValidationError("Slug must not be empty.")
        if len(self.value) > SLUG_MAX_LENGTH:
            raise ValidationError(
                "Slug is too long.",
                details={"length": len(self.value), "maximum": SLUG_MAX_LENGTH},
            )
        if not _SLUG_PATTERN.match(self.value):
            raise ValidationError(
                "Slug must be lower-case alphanumeric words separated by single hyphens.",
                details={"slug": self.value},
            )

    @classmethod
    def from_display_name(cls, name: str) -> Self:
        """Derive a slug from a human-readable name.

        Args:
            name: The display name.

        Returns:
            The derived slug.

        Raises:
            ValidationError: If nothing slug-shaped can be derived.
        """
        lowered = name.strip().lower()
        collapsed = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
        if not collapsed:
            raise ValidationError(
                "Cannot derive a slug from the given name.", details={"name": name}
            )
        return cls(collapsed[:SLUG_MAX_LENGTH].rstrip("-"))

    @classmethod
    def from_primitive(cls, value: Any) -> Self:
        """Build from a stored value.

        Args:
            value: The slug text.

        Returns:
            The validated slug.

        Raises:
            ValidationError: If the value is not a valid slug.
        """
        return cls(value)

    def to_primitive(self) -> str:
        """Return the slug text."""
        return self.value

    def __str__(self) -> str:
        """Return the slug text."""
        return self.value


@dataclass(frozen=True, slots=True, order=True)
class RevisionNumber:
    """A monotonically increasing revision number within one Task.

    Revision numbers never decrease and never repeat. They start at 1; there is no
    revision zero, because a revision that has not been created has no number.

    Attributes:
        value: The number, one or greater.
    """

    value: int

    def __post_init__(self) -> None:
        """Validate the number.

        Raises:
            ValidationError: If not a positive integer.
        """
        if isinstance(self.value, bool) or not isinstance(self.value, int):
            raise ValidationError(
                "RevisionNumber must be an integer.",
                details={"received_type": type(self.value).__name__},
            )
        if self.value < 1:
            raise ValidationError(
                "RevisionNumber starts at 1.", details={"revision_number": self.value}
            )

    @classmethod
    def first(cls) -> Self:
        """Return the first revision number."""
        return cls(1)

    def next(self) -> Self:
        """Return the next revision number.

        Returns:
            The successor. The domain never reuses or decrements a revision number.
        """
        return type(self)(self.value + 1)

    @classmethod
    def from_primitive(cls, value: Any) -> Self:
        """Build from a stored value."""
        return cls(value)

    def to_primitive(self) -> int:
        """Return the number."""
        return self.value

    def __str__(self) -> str:
        """Return the number as text."""
        return str(self.value)


@dataclass(frozen=True, slots=True)
class ContentDigest:
    """A deterministic digest of canonical content.

    Supports deployment integrity, drift detection, execution provenance, and comparison
    across control planes. Two revisions with the same digest have the same execution
    meaning, whichever machine computed them.

    Secret *values* never participate in a digest; secret *references* may.

    Attributes:
        value: The digest, formatted ``sha256:<64 hex characters>``.
    """

    value: str

    def __post_init__(self) -> None:
        """Validate the digest format.

        Raises:
            ValidationError: If the value is not a well-formed sha256 digest.
        """
        if not isinstance(self.value, str) or not _DIGEST_PATTERN.match(self.value):
            raise ValidationError(
                "ContentDigest must look like 'sha256:<64 hex characters>'.",
            )

    @classmethod
    def of_canonical(cls, content: Any) -> Self:
        """Compute a digest over canonically serialised content.

        Canonicalisation sorts keys and uses compact separators, so two structurally equal
        payloads digest identically regardless of key order or whitespace. This is what
        makes the digest reproducible across processes and machines.

        Args:
            content: JSON-serialisable content. Callers pass already-primitive data.

        Returns:
            The digest.

        Raises:
            ValidationError: If the content cannot be canonically serialised.
        """
        try:
            canonical = json.dumps(
                content,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                "Content is not canonically serialisable, so it cannot be digested.",
            ) from exc
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return cls(f"sha256:{digest}")

    @classmethod
    def from_primitive(cls, value: Any) -> Self:
        """Build from a stored value."""
        return cls(value)

    def to_primitive(self) -> str:
        """Return the digest string."""
        return self.value

    @property
    def short(self) -> str:
        """Return a 12-character prefix of the hex digest, for display only."""
        return self.value.removeprefix("sha256:")[:12]

    def __str__(self) -> str:
        """Return the digest string."""
        return self.value


@dataclass(frozen=True, slots=True, order=True)
class SchemaVersion:
    """The version of a public schema, as ``major.minor``.

    Compatibility is the point: a consumer supporting 1.3 can read 1.0 through 1.3, but
    must refuse 2.0. Encoding that rule here keeps it out of every call site.

    Attributes:
        major: Incremented by a breaking change.
        minor: Incremented by a backward-compatible addition.
    """

    major: int
    minor: int

    def __post_init__(self) -> None:
        """Validate the parts.

        Raises:
            ValidationError: If either part is negative or not an integer.
        """
        for part_name, part in (("major", self.major), ("minor", self.minor)):
            if isinstance(part, bool) or not isinstance(part, int) or part < 0:
                raise ValidationError(
                    "SchemaVersion parts must be non-negative integers.",
                    details={"part": part_name},
                )

    @classmethod
    def parse(cls, text: str) -> Self:
        """Parse a ``major.minor`` string.

        Args:
            text: The version string.

        Returns:
            The parsed version.

        Raises:
            ValidationError: If the text is not ``major.minor``.
        """
        if not isinstance(text, str) or not (match := _SCHEMA_VERSION_PATTERN.match(text)):
            raise ValidationError(
                "SchemaVersion must look like 'major.minor'.", details={"value": text}
            )
        return cls(int(match["major"]), int(match["minor"]))

    def is_compatible_with(self, supported: Self) -> bool:
        """Whether content at this version can be read by a consumer supporting another.

        Args:
            supported: The highest version the consumer understands.

        Returns:
            ``True`` when the major versions match and this minor version is not newer.
        """
        return self.major == supported.major and self.minor <= supported.minor

    @classmethod
    def from_primitive(cls, value: Any) -> Self:
        """Build from a stored ``major.minor`` string."""
        return cls.parse(value)

    def to_primitive(self) -> str:
        """Return the ``major.minor`` string."""
        return str(self)

    def __str__(self) -> str:
        """Return the ``major.minor`` string."""
        return f"{self.major}.{self.minor}"


@dataclass(frozen=True, slots=True)
class SecretReference:
    """A pointer to a secret, never the secret itself.

    The whole point of this type is that it is safe to persist, log, digest, display, and
    put in a generated artefact. Resolution to a value happens at the execution boundary,
    through a secrets adapter, and the value never comes back into the domain.

    Format is ``provider://path``, optionally ``#version``:
    ``env://DATABASE_PASSWORD``, ``file:///run/secrets/token#3``.

    Attributes:
        provider: The secrets provider, such as ``env`` or ``file``.
        path: The provider-specific locator.
        version: Optional version, for providers that support one.
    """

    provider: str
    path: str
    version: str | None = None

    def __post_init__(self) -> None:
        """Validate the reference.

        Raises:
            ValidationError: If the reference is malformed or looks like an inline secret.
        """
        if not isinstance(self.provider, str) or not self.provider:
            raise ValidationError("SecretReference requires a provider.")
        if not isinstance(self.path, str) or not self.path:
            raise ValidationError("SecretReference requires a path.")
        if not _SECRET_REFERENCE_PATTERN.match(f"{self.provider}://{self.path}"):
            raise ValidationError(
                "SecretReference must look like 'provider://path'.",
                details={"provider": self.provider},
            )
        if self.version is not None and (not isinstance(self.version, str) or not self.version):
            raise ValidationError("SecretReference version must be a non-empty string.")

    @classmethod
    def parse(cls, text: str) -> Self:
        """Parse a ``provider://path[#version]`` reference.

        Args:
            text: The reference string.

        Returns:
            The parsed reference.

        Raises:
            ValidationError: If the text is not a well-formed reference.
        """
        if not isinstance(text, str):
            raise ValidationError(
                "SecretReference must be a string.",
                details={"received_type": type(text).__name__},
            )
        body, separator, version = text.partition("#")
        match = _SECRET_REFERENCE_PATTERN.match(body)
        if not match:
            raise ValidationError(
                "SecretReference must look like 'provider://path'.",
            )
        if separator and not version:
            raise ValidationError("SecretReference version must not be empty when '#' is used.")
        return cls(match["provider"], match["path"], version or None)

    @classmethod
    def from_primitive(cls, value: Any) -> Self:
        """Build from a stored reference string."""
        return cls.parse(value)

    def to_primitive(self) -> str:
        """Return the reference string. Safe to persist, log, and digest."""
        return str(self)

    def __str__(self) -> str:
        """Return ``provider://path`` with an optional ``#version``."""
        base = f"{self.provider}://{self.path}"
        return f"{base}#{self.version}" if self.version else base
