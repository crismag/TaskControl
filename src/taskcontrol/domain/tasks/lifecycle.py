"""Task and revision lifecycle states, with their legal transitions.

Two independent lifecycles meet here. A **Task** moves through draft, active, suspended,
retired, and archived — that is operational availability. A **TaskRevision** moves through
draft, published, superseded, and withdrawn — that is content maturity.

Keeping them separate is what allows a suspended task to keep a perfectly good published
revision, and an active task to accumulate draft revisions nobody has approved yet.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from taskcontrol.common.errors import DomainRuleViolationError


class TaskLifecycleState(StrEnum):
    """Whether a Task is operationally available."""

    DRAFT = "draft"
    "Exists but has no active deployable revision."

    ACTIVE = "active"
    "Has an active published revision and may accept triggers."

    SUSPENDED = "suspended"
    "No new ordinary executions start. Running executions continue unless cancelled."

    RETIRED = "retired"
    "Intentionally withdrawn. History and deployments remain visible."

    ARCHIVED = "archived"
    "Read-only and hidden from ordinary views. Never physically deleted while referenced."

    @property
    def accepts_triggers(self) -> bool:
        """Whether an ordinary trigger may start an execution.

        Only ``ACTIVE`` does. A trigger arriving for a task in any other state produces a
        recorded, explained skip rather than silence.
        """
        return self is TaskLifecycleState.ACTIVE

    @property
    def is_editable(self) -> bool:
        """Whether the task's mutable metadata may still be changed."""
        return self not in {TaskLifecycleState.ARCHIVED}

    @property
    def is_terminal(self) -> bool:
        """Whether no further lifecycle transition is possible."""
        return self is TaskLifecycleState.ARCHIVED


class PublicationState(StrEnum):
    """How mature a TaskRevision's content is."""

    DRAFT = "draft"
    "Editable. Not deployable."

    PUBLISHED = "published"
    "Frozen and digested. Deployable and activatable."

    SUPERSEDED = "superseded"
    "A newer revision became active. Retained for history and permitted replay."

    WITHDRAWN = "withdrawn"
    "Deliberately taken out of use, for example after a defect was found."

    @property
    def is_editable(self) -> bool:
        """Whether the revision's content may still change.

        Only a draft. After publication, corrections produce a new revision — that is the
        rule that makes an execution record mean something years later.
        """
        return self is PublicationState.DRAFT

    @property
    def is_deployable(self) -> bool:
        """Whether this revision may be activated or deployed."""
        return self is PublicationState.PUBLISHED

    @property
    def is_frozen(self) -> bool:
        """Whether the content and digest are immutable."""
        return self is not PublicationState.DRAFT


_TASK_TRANSITIONS: Final[dict[TaskLifecycleState, frozenset[TaskLifecycleState]]] = {
    TaskLifecycleState.DRAFT: frozenset({TaskLifecycleState.ACTIVE, TaskLifecycleState.ARCHIVED}),
    TaskLifecycleState.ACTIVE: frozenset(
        {TaskLifecycleState.SUSPENDED, TaskLifecycleState.RETIRED}
    ),
    TaskLifecycleState.SUSPENDED: frozenset(
        {TaskLifecycleState.ACTIVE, TaskLifecycleState.RETIRED}
    ),
    # Reactivation from retired is deliberate and explicit, never incidental.
    TaskLifecycleState.RETIRED: frozenset({TaskLifecycleState.ACTIVE, TaskLifecycleState.ARCHIVED}),
    TaskLifecycleState.ARCHIVED: frozenset(),
}

_PUBLICATION_TRANSITIONS: Final[dict[PublicationState, frozenset[PublicationState]]] = {
    PublicationState.DRAFT: frozenset({PublicationState.PUBLISHED, PublicationState.WITHDRAWN}),
    PublicationState.PUBLISHED: frozenset(
        {PublicationState.SUPERSEDED, PublicationState.WITHDRAWN}
    ),
    # A superseded revision may be withdrawn if a defect is found after the fact.
    PublicationState.SUPERSEDED: frozenset({PublicationState.WITHDRAWN}),
    PublicationState.WITHDRAWN: frozenset(),
}


def is_legal_task_transition(current: TaskLifecycleState, proposed: TaskLifecycleState) -> bool:
    """Whether a Task may move between two lifecycle states.

    Args:
        current: The state now.
        proposed: The state being requested.

    Returns:
        ``True`` when the transition is permitted.
    """
    return proposed in _TASK_TRANSITIONS[current]


def assert_legal_task_transition(current: TaskLifecycleState, proposed: TaskLifecycleState) -> None:
    """Raise unless a Task may move between two lifecycle states.

    Args:
        current: The state now.
        proposed: The state being requested.

    Raises:
        DomainRuleViolationError: If the transition is not permitted.
    """
    if not is_legal_task_transition(current, proposed):
        raise DomainRuleViolationError(
            f"A task cannot move from {current} to {proposed}.",
            details={
                "current_state": str(current),
                "proposed_state": str(proposed),
                "legal_states": sorted(str(s) for s in _TASK_TRANSITIONS[current]),
            },
        )


def is_legal_publication_transition(current: PublicationState, proposed: PublicationState) -> bool:
    """Whether a TaskRevision may move between two publication states.

    Args:
        current: The state now.
        proposed: The state being requested.

    Returns:
        ``True`` when the transition is permitted.
    """
    return proposed in _PUBLICATION_TRANSITIONS[current]


def assert_legal_publication_transition(
    current: PublicationState, proposed: PublicationState
) -> None:
    """Raise unless a TaskRevision may move between two publication states.

    Args:
        current: The state now.
        proposed: The state being requested.

    Raises:
        DomainRuleViolationError: If the transition is not permitted.
    """
    if not is_legal_publication_transition(current, proposed):
        raise DomainRuleViolationError(
            f"A revision cannot move from {current} to {proposed}.",
            details={
                "current_state": str(current),
                "proposed_state": str(proposed),
                "legal_states": sorted(str(s) for s in _PUBLICATION_TRANSITIONS[current]),
            },
        )
