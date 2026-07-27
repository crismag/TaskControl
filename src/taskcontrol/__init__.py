"""TaskControl — define, schedule, execute, observe, and govern automated work.

TaskControl is a standalone application. In the current phase it schedules and runs work
itself through an internal scheduler; it does not write to any host scheduler
configuration (ADR 0018).

Layer boundaries and the dependency direction are normative in
``development/engineering/repository/11_DEPENDENCY_RULES.md`` and are enforced by
``tests/unit/test_architecture.py``.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
