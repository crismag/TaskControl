"""The task domain: durable identity plus immutable revisions.

A Task owns identity and operational availability. A TaskRevision owns everything that
affects how work executes, and never changes once published.
"""

from __future__ import annotations

from taskcontrol.domain.tasks.actions import (
    ActionSpecification,
    EnvironmentBinding,
    ExecutorType,
    OutputCapturePolicy,
    StdinPolicy,
)
from taskcontrol.domain.tasks.lifecycle import (
    PublicationState,
    TaskLifecycleState,
    assert_legal_publication_transition,
    assert_legal_task_transition,
    is_legal_publication_transition,
    is_legal_task_transition,
)
from taskcontrol.domain.tasks.revision import (
    CURRENT_REVISION_SCHEMA_VERSION,
    ActivationPolicy,
    ExecutionControls,
    TaskRevision,
)
from taskcontrol.domain.tasks.task import Task

__all__ = [
    "CURRENT_REVISION_SCHEMA_VERSION",
    "ActionSpecification",
    "ActivationPolicy",
    "EnvironmentBinding",
    "ExecutionControls",
    "ExecutorType",
    "OutputCapturePolicy",
    "PublicationState",
    "StdinPolicy",
    "Task",
    "TaskLifecycleState",
    "TaskRevision",
    "assert_legal_publication_transition",
    "assert_legal_task_transition",
    "is_legal_publication_transition",
    "is_legal_task_transition",
]
