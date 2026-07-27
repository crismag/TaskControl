"""TaskControl — define, schedule, execute, observe, and govern automated work.

TaskControl is an operational automation platform. It manages the lifecycle of operational
capabilities — definition, deployment, activation, execution, observation, and audit.

**Cron owns recurring activation** (ADR 0022). TaskControl renders and installs managed cron
artefacts, and cron invokes short-lived TaskControl wrappers. Nothing here runs a timer or a
polling loop, and already-installed recurring work keeps running when the control plane is
down.

Layer boundaries and the dependency direction are normative in
``development/engineering/repository/11_DEPENDENCY_RULES.md`` and are enforced by
``tests/unit/test_architecture.py``.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
