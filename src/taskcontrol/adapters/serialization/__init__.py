"""Serialisation adapters: portable bundles and the published JSON Schema.

Serialisation lives here rather than in the domain because the domain may import only the
standard library. The domain exposes `to_primitive`/`from_primitive`; this package decides
what those primitives look like on disk.
"""

from __future__ import annotations

from taskcontrol.adapters.serialization.bundles import (
    BUNDLE_KIND,
    TaskBundle,
    dump_yaml,
    load_yaml,
)
from taskcontrol.adapters.serialization.json_schema import (
    SCHEMA_ID,
    dump_schema,
    task_bundle_schema,
)

__all__ = [
    "BUNDLE_KIND",
    "SCHEMA_ID",
    "TaskBundle",
    "dump_schema",
    "dump_yaml",
    "load_yaml",
    "task_bundle_schema",
]
