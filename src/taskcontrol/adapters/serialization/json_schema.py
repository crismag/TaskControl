"""JSON Schema for portable task bundles.

The schema is hand-maintained rather than derived from the domain classes. That is
deliberate: the domain is plain Python with no schema framework, and generating a schema by
reflecting over dataclasses would silently publish every internal rename as a breaking
contract change. Writing it out makes the published contract an explicit decision.

The schema is exported to ``schemas/`` and validated against the examples in CI, so it
cannot drift from what the code actually accepts without a test failing.
"""

from __future__ import annotations

import json
from enum import StrEnum
from typing import Any

from taskcontrol.domain.execution.results import BackoffStrategy, OverlapPolicy
from taskcontrol.domain.tasks.actions import (
    ExecutorType,
    OutputCapturePolicy,
    StdinPolicy,
)
from taskcontrol.domain.tasks.lifecycle import PublicationState, TaskLifecycleState
from taskcontrol.domain.tasks.revision import CURRENT_REVISION_SCHEMA_VERSION

SCHEMA_ID = "https://taskcontrol.dev/schemas/task-bundle-v1.json"


def _enum_values(enum_type: type[StrEnum]) -> list[str]:
    """Return an enum's wire values, so the schema cannot drift from the code."""
    return [member.value for member in enum_type]


def task_bundle_schema() -> dict[str, Any]:
    """Return the JSON Schema for a portable task bundle.

    Enum members are read from the domain enums rather than repeated as literals, so
    adding an executor type or a publication state updates the published schema
    automatically.

    Returns:
        A JSON Schema draft 2020-12 document.
    """
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": SCHEMA_ID,
        "title": "TaskControl Task Bundle",
        "description": (
            "A portable task definition: one task and one of its revisions. "
            "Secret values never appear; secrets are carried as references."
        ),
        "type": "object",
        "required": ["kind", "schema_version", "task", "revision"],
        "additionalProperties": False,
        "properties": {
            "kind": {"const": "TaskBundle"},
            "schema_version": {
                "type": "string",
                "pattern": r"^\d+\.\d+$",
                "description": "Bundle schema version.",
                "examples": [CURRENT_REVISION_SCHEMA_VERSION.to_primitive()],
            },
            "task": _task_schema(),
            "revision": _revision_schema(),
        },
    }


def _task_schema() -> dict[str, Any]:
    """Return the schema fragment for a task."""
    return {
        "type": "object",
        "required": ["task_id", "name", "slug", "owner_id", "created_at", "created_by"],
        "additionalProperties": False,
        "properties": {
            "task_id": {"type": "string", "pattern": "^task_"},
            "name": {"type": "string", "minLength": 1, "maxLength": 200},
            "slug": {"type": "string", "pattern": "^[a-z0-9]+(?:-[a-z0-9]+)*$"},
            "description": {"type": "string", "maxLength": 4000},
            "owner_id": {"type": "string", "pattern": "^own_"},
            "lifecycle_state": {"enum": _enum_values(TaskLifecycleState)},
            "active_revision_id": {
                "type": ["string", "null"],
                "description": "Required when lifecycle_state is 'active'.",
            },
            "labels": {"type": "array", "items": {"type": "string"}, "maxItems": 50},
            "created_at": {"type": "string", "format": "date-time"},
            "created_by": {"type": "string"},
            "updated_at": {"type": ["string", "null"], "format": "date-time"},
            "updated_by": {"type": ["string", "null"]},
        },
    }


def _revision_schema() -> dict[str, Any]:
    """Return the schema fragment for a revision."""
    return {
        "type": "object",
        "required": [
            "revision_id",
            "revision_number",
            "publication_state",
            "created_at",
            "created_by",
            "action",
        ],
        "additionalProperties": False,
        "properties": {
            "revision_id": {"type": "string", "pattern": "^rev_"},
            "revision_number": {"type": "integer", "minimum": 1},
            "publication_state": {"enum": _enum_values(PublicationState)},
            "change_summary": {"type": "string", "maxLength": 2000},
            "created_at": {"type": "string", "format": "date-time"},
            "created_by": {"type": "string"},
            "published_at": {"type": ["string", "null"], "format": "date-time"},
            "published_by": {"type": ["string", "null"]},
            "content_digest": {
                "type": ["string", "null"],
                "pattern": "^sha256:[0-9a-f]{64}$",
                "description": "Present only once published; absent on a draft.",
            },
            "action": _action_schema(),
            "controls": _controls_schema(),
        },
    }


def _action_schema() -> dict[str, Any]:
    """Return the schema fragment for an action specification."""
    return {
        "type": "object",
        "required": ["executor_type", "entrypoint"],
        "additionalProperties": False,
        "properties": {
            "executor_type": {"enum": _enum_values(ExecutorType)},
            "entrypoint": {"type": "string", "minLength": 1},
            "arguments": {"type": "array", "items": {"type": "string"}, "maxItems": 1024},
            "working_directory": {
                "type": ["string", "null"],
                "pattern": "^/",
                "description": "Absolute path. Parent traversal is rejected.",
            },
            "environment": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["name"],
                    "additionalProperties": False,
                    "description": (
                        "Exactly one of 'value' or 'secret'. A secret value never appears "
                        "in a bundle."
                    ),
                    "properties": {
                        "name": {"type": "string", "pattern": "^[A-Za-z_][A-Za-z0-9_]*$"},
                        "value": {"type": "string"},
                        "secret": {
                            "type": "string",
                            "pattern": "^[a-z][a-z0-9_-]*://[^\\s]+$",
                            "description": "provider://path[#version]",
                        },
                    },
                },
            },
            "stdin_policy": {"enum": _enum_values(StdinPolicy)},
            "output_capture": {"enum": _enum_values(OutputCapturePolicy)},
            "use_raw_shell": {
                "type": "boolean",
                "description": (
                    "Elevated risk. Interprets shell metacharacters; only valid for the "
                    "shell executor and incompatible with separate arguments."
                ),
            },
            "required_capabilities": {"type": "array", "items": {"type": "string"}},
        },
    }


def _controls_schema() -> dict[str, Any]:
    """Return the schema fragment for execution controls."""
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "timeout": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "run_timeout_seconds": {"type": "integer", "minimum": 0},
                    "termination_grace_seconds": {"type": "integer", "minimum": 0},
                },
            },
            "retry": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "max_attempts": {"type": "integer", "minimum": 1, "maximum": 100},
                    "backoff": {"enum": _enum_values(BackoffStrategy)},
                    "base_delay_seconds": {"type": "integer", "minimum": 0},
                    "max_delay_seconds": {"type": "integer", "minimum": 0},
                    "retry_outcome_failures": {"type": "boolean"},
                    "retry_timeouts": {"type": "boolean"},
                },
            },
            "overlap": {"enum": _enum_values(OverlapPolicy)},
            "max_concurrent": {"type": "integer", "minimum": 1},
        },
    }


def dump_schema() -> str:
    """Return the schema as formatted JSON, ready to write to ``schemas/``.

    Returns:
        Indented JSON with sorted keys, ending in a newline, so the exported file
        produces a clean diff when the contract genuinely changes.
    """
    return json.dumps(task_bundle_schema(), indent=2, sort_keys=True) + "\n"
