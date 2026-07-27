"""Structured logging with correlation context and secret redaction.

Two properties matter more than convenience here, both required by
``development/engineering/standards/22_RUNTIME_OBSERVABILITY_AND_SECURITY.md``:

1. **Correlation.** Every record carries the identifiers that let an operator follow one
   request or execution across the API, the runtime, and the adapters. Later waves add
   task, execution, attempt, and deployment identifiers to the same context.
2. **Redaction.** A secret value must never reach a log sink. Redaction is applied at the
   handler, so it cannot be bypassed by a caller who formats a message carelessly.

Redaction is defence in depth, not a licence to log secrets. The primary rule remains
that secret values are referenced and never passed to a logger in the first place.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Final

from taskcontrol.infrastructure.settings import LogFormat, Settings

REDACTED: Final = "***redacted***"

_SENSITIVE_KEY_PATTERN: Final = re.compile(
    r"(secret|password|passwd|token|api[_-]?key|credential|private[_-]?key|authorization)",
    re.IGNORECASE,
)

_RESERVED_RECORD_FIELDS: Final[frozenset[str]] = frozenset(
    logging.LogRecord("", 0, "", 0, "", None, None).__dict__
) | {
    "asctime",
    "message",
    "taskcontrol_context",
    # Uvicorn attaches an ANSI-coloured duplicate of its own message. It is noise in a
    # structured record and unreadable in a log aggregator.
    "color_message",
}

# A mutable default would be shared by every context, so the empty case is None.
_correlation_context: ContextVar[dict[str, str] | None] = ContextVar(
    "taskcontrol_correlation", default=None
)

_registered_secrets: set[str] = set()


def register_secret(value: str) -> None:
    """Register a literal value to be scrubbed from every log record.

    Call this when a secret is resolved, so that an accidental interpolation of it into a
    message or an exception string is masked before it reaches a sink.

    Args:
        value: The literal secret. Values shorter than eight characters are ignored,
            because masking them would corrupt unrelated text without meaningfully
            protecting anything.
    """
    if len(value) >= 8:
        _registered_secrets.add(value)


def clear_registered_secrets() -> None:
    """Forget every registered secret. Intended for test isolation."""
    _registered_secrets.clear()


def get_correlation_context() -> dict[str, str]:
    """Return the correlation identifiers bound to the current context.

    Returns:
        A copy of the current context. Mutating it has no effect on logging.
    """
    return dict(_correlation_context.get() or {})


@contextmanager
def correlation_context(**fields: str) -> Iterator[None]:
    """Bind correlation identifiers for the duration of a block.

    Nested use merges with the enclosing context rather than replacing it, so an
    execution identifier bound inside a request keeps the request identifier.

    Args:
        **fields: Identifiers to bind, such as ``correlation_id`` or ``execution_id``.

    Yields:
        None.
    """
    token = _correlation_context.set({**(_correlation_context.get() or {}), **fields})
    try:
        yield
    finally:
        _correlation_context.reset(token)


def _redact_value(value: Any) -> Any:
    """Mask registered secrets appearing anywhere inside a value."""
    if isinstance(value, str):
        for secret in _registered_secrets:
            if secret in value:
                value = value.replace(secret, REDACTED)
        return value
    if isinstance(value, dict):
        return _redact_mapping(value)
    if isinstance(value, (list, tuple)):
        return type(value)(_redact_value(item) for item in value)
    return value


def _redact_mapping(mapping: dict[Any, Any]) -> dict[Any, Any]:
    """Mask values whose key names them sensitive, and scrub the rest."""
    redacted: dict[Any, Any] = {}
    for key, value in mapping.items():
        if isinstance(key, str) and _SENSITIVE_KEY_PATTERN.search(key):
            redacted[key] = REDACTED
        else:
            redacted[key] = _redact_value(value)
    return redacted


def _record_extras(record: logging.LogRecord) -> dict[str, Any]:
    """Return the caller-supplied ``extra`` fields attached to a record."""
    return {
        key: value
        for key, value in record.__dict__.items()
        if key not in _RESERVED_RECORD_FIELDS and not key.startswith("_")
    }


class RedactionFilter(logging.Filter):
    """Scrub registered secret values from a record before it is formatted.

    Applied at the handler so that every sink inherits it, including sinks added by a
    later wave.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact the record in place and always allow it through.

        Args:
            record: The record about to be emitted.

        Returns:
            Always ``True``; this filter masks rather than drops.
        """
        if _registered_secrets:
            if isinstance(record.msg, str):
                record.msg = _redact_value(record.msg)
            if record.args:
                record.args = (
                    _redact_mapping(record.args)
                    if isinstance(record.args, dict)
                    else tuple(_redact_value(arg) for arg in record.args)
                )
        for key, value in _record_extras(record).items():
            setattr(record, key, _redact_value(value))
        return True


class StructuredFormatter(logging.Formatter):
    """Render a record as a single line of JSON with correlation fields merged in."""

    def format(self, record: logging.LogRecord) -> str:
        """Return the record as compact JSON.

        Args:
            record: The record to render.

        Returns:
            One line of JSON. Never contains a newline, so a sink can rely on
            line-delimited parsing.
        """
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update(_redact_mapping(get_correlation_context()))
        payload.update(_redact_mapping(_record_extras(record)))

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str, separators=(",", ":"))


class TextFormatter(logging.Formatter):
    """Render a record for a human, appending correlation and extra fields."""

    def __init__(self) -> None:
        super().__init__(fmt="%(asctime)s %(levelname)-8s %(name)s: %(message)s")

    def format(self, record: logging.LogRecord) -> str:
        """Return a human-readable line with context appended.

        Args:
            record: The record to render.

        Returns:
            The formatted line.
        """
        base = super().format(record)
        context = {**get_correlation_context(), **_record_extras(record)}
        if not context:
            return base
        rendered = " ".join(f"{key}={value}" for key, value in _redact_mapping(context).items())
        return f"{base} [{rendered}]"


def configure_logging(settings: Settings) -> None:
    """Install TaskControl's logging configuration on the root logger.

    Idempotent: calling it again replaces the previously installed handler rather than
    adding a second one, so a process cannot silently double-log.

    Args:
        settings: Validated settings supplying the level and format.
    """
    formatter: logging.Formatter = (
        StructuredFormatter() if settings.log_format is LogFormat.JSON else TextFormatter()
    )

    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(formatter)
    handler.addFilter(RedactionFilter())
    handler.set_name("taskcontrol")

    root = logging.getLogger()
    for existing in [h for h in root.handlers if h.get_name() == "taskcontrol"]:
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(settings.log_level)


def uvicorn_log_config(settings: Settings) -> dict[str, Any]:
    """Return a uvicorn logging configuration that routes through TaskControl's handler.

    Uvicorn ships ``uvicorn``, ``uvicorn.error``, and ``uvicorn.access`` with their own
    handlers and ``propagate = False``, so by default none of the server's output reaches
    the handler :func:`configure_logging` installs. The result is a process that emits
    structured JSON for application events and plain text for everything the server says
    — unparseable as a whole, and impossible to correlate.

    This configuration removes uvicorn's handlers and lets its records propagate to the
    root logger, so one process emits one format.

    ``uvicorn.access`` is silenced entirely. TaskControl emits its own access log from the
    request middleware, where correlation context is bound; uvicorn's equivalent is
    emitted outside that context and could not carry a correlation identifier.

    Args:
        settings: Validated settings supplying the level.

    Returns:
        A :func:`logging.config.dictConfig` mapping for uvicorn's ``log_config``.
    """
    return {
        "version": 1,
        # Loggers created before uvicorn applies this config must keep working.
        "disable_existing_loggers": False,
        "loggers": {
            "uvicorn": {"handlers": [], "level": settings.log_level, "propagate": True},
            "uvicorn.error": {"handlers": [], "level": settings.log_level, "propagate": True},
            "uvicorn.access": {"handlers": [], "level": "CRITICAL", "propagate": False},
        },
    }


def get_logger(name: str) -> logging.Logger:
    """Return a named logger.

    Args:
        name: Usually ``__name__`` of the calling module.

    Returns:
        A standard library logger; TaskControl adds no wrapper.
    """
    return logging.getLogger(name)
