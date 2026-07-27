"""Task — the stable identity of an operational activity.

A Task is not a bag of runtime fields. It owns identity, ownership, and operational
availability; everything that affects *how* work executes lives in an immutable
:class:`TaskRevision`.

That split is what makes the metadata rule possible: renaming a task or changing its
description is a mutation, while changing its command is a new revision.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Self

from taskcontrol.common.errors import DomainRuleViolationError, ValidationError
from taskcontrol.domain.common.identifiers import OwnerId, TaskId, TaskRevisionId
from taskcontrol.domain.common.values import Slug, UtcTimestamp
from taskcontrol.domain.tasks.lifecycle import (
    TaskLifecycleState,
    assert_legal_task_transition,
)

MAX_NAME_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 4000
MAX_LABELS = 50


@dataclass(frozen=True, slots=True)
class Task:
    """The durable identity of an operational activity.

    Attributes:
        task_id: Stable identifier.
        name: Human-readable name, unique within its owning scope.
        slug: Stable URL- and CLI-safe name.
        owner_id: Who owns this task.
        created_at: When it was created.
        created_by: Who created it.
        description: Operational purpose and expected effect.
        lifecycle_state: Operational availability.
        active_revision_id: The published revision currently selected, if any.
        labels: Free-form organisational labels.
        updated_at: When mutable metadata last changed.
        updated_by: Who last changed mutable metadata.
    """

    task_id: TaskId
    name: str
    slug: Slug
    owner_id: OwnerId
    created_at: UtcTimestamp
    created_by: OwnerId
    description: str = ""
    lifecycle_state: TaskLifecycleState = TaskLifecycleState.DRAFT
    active_revision_id: TaskRevisionId | None = None
    labels: frozenset[str] = field(default_factory=frozenset)
    updated_at: UtcTimestamp | None = None
    updated_by: OwnerId | None = None

    def __post_init__(self) -> None:
        """Validate the task.

        Raises:
            ValidationError: If a field is unusable or the state is self-contradictory.
        """
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValidationError("A task requires a name.")
        if len(self.name) > MAX_NAME_LENGTH:
            raise ValidationError("Task name is too long.", details={"maximum": MAX_NAME_LENGTH})
        if len(self.description) > MAX_DESCRIPTION_LENGTH:
            raise ValidationError(
                "Task description is too long.", details={"maximum": MAX_DESCRIPTION_LENGTH}
            )
        if len(self.labels) > MAX_LABELS:
            raise ValidationError(
                "Too many labels.", details={"count": len(self.labels), "maximum": MAX_LABELS}
            )

        # An active task without a published revision has nothing to run. Allowing it
        # would mean a trigger arrives and the runtime has no definition to execute.
        if self.lifecycle_state is TaskLifecycleState.ACTIVE and self.active_revision_id is None:
            raise ValidationError(
                "An active task must reference a published revision.",
                details={"task_id": str(self.task_id)},
            )

    @classmethod
    def create(
        cls,
        *,
        name: str,
        owner_id: OwnerId,
        created_by: OwnerId,
        created_at: UtcTimestamp,
        task_id: TaskId | None = None,
        slug: Slug | None = None,
        description: str = "",
        labels: frozenset[str] | None = None,
    ) -> Self:
        """Create a new task in draft.

        Args:
            name: Human-readable name.
            owner_id: Who owns it.
            created_by: Who is creating it.
            created_at: When.
            task_id: Explicit identifier. Generated when omitted.
            slug: Explicit slug. Derived from the name when omitted.
            description: Operational purpose.
            labels: Organisational labels.

        Returns:
            The new task, in ``DRAFT``. A task is never born active: it has no revision
            to run yet.

        Raises:
            ValidationError: If the name cannot produce a valid slug.
        """
        return cls(
            task_id=task_id or TaskId.generate(),
            name=name,
            slug=slug or Slug.from_display_name(name),
            owner_id=owner_id,
            created_at=created_at,
            created_by=created_by,
            description=description,
            labels=labels or frozenset(),
        )

    @property
    def accepts_triggers(self) -> bool:
        """Whether an ordinary trigger may start an execution now."""
        return self.lifecycle_state.accepts_triggers

    def update_metadata(
        self,
        *,
        updated_by: OwnerId,
        updated_at: UtcTimestamp,
        name: str | None = None,
        description: str | None = None,
        owner_id: OwnerId | None = None,
        labels: frozenset[str] | None = None,
    ) -> Self:
        """Change metadata that does not affect execution.

        Name, description, ownership, and labels are display and organisational concerns.
        Changing them does not create a revision, because they cannot change what runs.
        Anything that *can* change what runs belongs in a new revision instead.

        The slug is deliberately not updatable: it appears in URLs and generated
        artefacts, so renaming a task must not break an existing reference.

        Args:
            updated_by: Who is making the change.
            updated_at: When.
            name: New display name.
            description: New description.
            owner_id: New owner.
            labels: New label set.

        Returns:
            The updated task.

        Raises:
            DomainRuleViolationError: If the task is archived and therefore read-only.
            ValidationError: If a new value is invalid.
        """
        if not self.lifecycle_state.is_editable:
            raise DomainRuleViolationError(
                "An archived task is read-only.",
                details={"task_id": str(self.task_id)},
            )

        return replace(
            self,
            name=self.name if name is None else name,
            description=self.description if description is None else description,
            owner_id=self.owner_id if owner_id is None else owner_id,
            labels=self.labels if labels is None else labels,
            updated_at=updated_at,
            updated_by=updated_by,
        )

    def activate_revision(
        self,
        revision_id: TaskRevisionId,
        *,
        updated_by: OwnerId,
        updated_at: UtcTimestamp,
    ) -> Self:
        """Select a published revision as the one that runs.

        Activation is separate from publication: publishing freezes content, activating
        chooses which frozen content is live. Running executions stay on the revision they
        started with.

        Args:
            revision_id: The published revision to activate.
            updated_by: Who is activating.
            updated_at: When.

        Returns:
            The task, active, referencing the given revision.

        Raises:
            DomainRuleViolationError: If the task cannot become active from its state.
        """
        if self.lifecycle_state is TaskLifecycleState.ARCHIVED:
            raise DomainRuleViolationError(
                "An archived task cannot activate a revision.",
                details={"task_id": str(self.task_id)},
            )
        if self.lifecycle_state is not TaskLifecycleState.ACTIVE:
            assert_legal_task_transition(self.lifecycle_state, TaskLifecycleState.ACTIVE)

        return replace(
            self,
            lifecycle_state=TaskLifecycleState.ACTIVE,
            active_revision_id=revision_id,
            updated_at=updated_at,
            updated_by=updated_by,
        )

    def transition_to(
        self,
        proposed: TaskLifecycleState,
        *,
        updated_by: OwnerId,
        updated_at: UtcTimestamp,
    ) -> Self:
        """Move the task to another lifecycle state.

        Args:
            proposed: The state to move to.
            updated_by: Who is making the change.
            updated_at: When.

        Returns:
            The task in its new state.

        Raises:
            DomainRuleViolationError: If the transition is not legal, or would produce an
                active task with no revision to run.
        """
        assert_legal_task_transition(self.lifecycle_state, proposed)

        if proposed is TaskLifecycleState.ACTIVE and self.active_revision_id is None:
            raise DomainRuleViolationError(
                "A task cannot become active without a published revision to run. "
                "Activate a revision instead.",
                details={"task_id": str(self.task_id)},
            )

        return replace(
            self,
            lifecycle_state=proposed,
            updated_at=updated_at,
            updated_by=updated_by,
        )

    def suspend(self, *, updated_by: OwnerId, updated_at: UtcTimestamp) -> Self:
        """Stop new executions while leaving running ones alone."""
        return self.transition_to(
            TaskLifecycleState.SUSPENDED, updated_by=updated_by, updated_at=updated_at
        )

    def resume(self, *, updated_by: OwnerId, updated_at: UtcTimestamp) -> Self:
        """Return a suspended task to service."""
        return self.transition_to(
            TaskLifecycleState.ACTIVE, updated_by=updated_by, updated_at=updated_at
        )

    def retire(self, *, updated_by: OwnerId, updated_at: UtcTimestamp) -> Self:
        """Withdraw the task while keeping its history visible."""
        return self.transition_to(
            TaskLifecycleState.RETIRED, updated_by=updated_by, updated_at=updated_at
        )

    def archive(self, *, updated_by: OwnerId, updated_at: UtcTimestamp) -> Self:
        """Make the task read-only and hide it from ordinary views."""
        return self.transition_to(
            TaskLifecycleState.ARCHIVED, updated_by=updated_by, updated_at=updated_at
        )

    def to_primitive(self) -> dict[str, Any]:
        """Return a stable representation for storage or transport."""
        return {
            "task_id": self.task_id.to_primitive(),
            "name": self.name,
            "slug": self.slug.to_primitive(),
            "description": self.description,
            "owner_id": self.owner_id.to_primitive(),
            "lifecycle_state": str(self.lifecycle_state),
            "active_revision_id": (
                self.active_revision_id.to_primitive() if self.active_revision_id else None
            ),
            "labels": sorted(self.labels),
            "created_at": self.created_at.to_primitive(),
            "created_by": self.created_by.to_primitive(),
            "updated_at": self.updated_at.to_primitive() if self.updated_at else None,
            "updated_by": self.updated_by.to_primitive() if self.updated_by else None,
        }
