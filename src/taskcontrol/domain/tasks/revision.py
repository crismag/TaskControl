"""TaskRevision — an immutable snapshot of everything that affects execution.

The rule this module exists to enforce: **published content never changes.** A correction
produces a new revision. That is what lets an execution record from eight months ago still
mean exactly what it meant then, and it is the foundation of the deployment integrity and
drift detection that arrive in Phase 2.

Publication freezes content and computes a content digest. Two revisions with the same
digest have the same execution meaning, whichever machine produced them.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any, Self

from taskcontrol.common.errors import DomainRuleViolationError, ValidationError
from taskcontrol.domain.common.identifiers import OwnerId, TaskId, TaskRevisionId
from taskcontrol.domain.common.values import (
    ContentDigest,
    RevisionNumber,
    SchemaVersion,
    SecretReference,
    UtcTimestamp,
)
from taskcontrol.domain.execution.results import (
    OverlapPolicy,
    RetryPolicy,
    TimeoutPolicy,
)
from taskcontrol.domain.tasks.actions import ActionSpecification
from taskcontrol.domain.tasks.lifecycle import (
    PublicationState,
    assert_legal_publication_transition,
)


class ActivationPolicy(StrEnum):
    """What a cron-woken wrapper does when TaskControl's control state is unreachable.

    Cron has already activated the work; something must decide whether to proceed. The
    honest answer is task-specific, so it is recorded in the definition rather than assumed
    globally (ADR 0024).
    """

    REQUIRE_CONTROL_STATE = "require_control_state"
    """Do not execute without a durable attempt record.

    The runnable does not run; the activation is reconciled as an infrastructure failure
    once persistence returns. For work where an unrecorded run is worse than a missed one:
    financial processing, regulated operations, anything a human may re-run by hand.

    The default, so an operator who has not considered this case gets the auditable
    behaviour and a loud failure rather than a silent one.
    """

    CONTINUE_WITH_LOCAL_JOURNAL = "continue_with_local_journal"
    """Execute anyway, journal locally, and reconcile later.

    For work where missing the run is worse than temporarily missing central observability:
    backups, log rotation, cleanup, cache warming.

    The journal is not optional. Without it this is simply an unrecorded run.
    """

    @property
    def executes_without_control_state(self) -> bool:
        """Whether the runnable may proceed when persistence is unreachable."""
        return self is ActivationPolicy.CONTINUE_WITH_LOCAL_JOURNAL


CURRENT_REVISION_SCHEMA_VERSION = SchemaVersion(1, 1)
"""The revision schema this build writes. Bump the minor for additive changes.

1.1 added ``activation_policy``. Additive and defaulted, so a 1.0 bundle still loads.
"""

MAX_CHANGE_SUMMARY_LENGTH = 2000


@dataclass(frozen=True, slots=True)
class ExecutionControls:
    """How an execution of this revision is governed at run time.

    Attributes:
        timeout: How long it may run and how it is stopped.
        retry: How many attempts and how they are spaced.
        overlap: What happens when a trigger arrives while it is already running.
        max_concurrent: Ceiling on simultaneous executions when overlap is allowed.
        activation_policy: What to do when control state is unreachable at activation
            (ADR 0024). Defaults to refusing, so the auditable behaviour is inherited and
            choosing availability is a deliberate, visible act.
    """

    timeout: TimeoutPolicy = field(default_factory=TimeoutPolicy.unlimited)
    retry: RetryPolicy = field(default_factory=RetryPolicy.none)
    overlap: OverlapPolicy = OverlapPolicy.FORBID
    max_concurrent: int = 1
    activation_policy: ActivationPolicy = ActivationPolicy.REQUIRE_CONTROL_STATE

    def __post_init__(self) -> None:
        """Validate the controls.

        Raises:
            ValidationError: If the controls contradict each other.
        """
        if self.max_concurrent < 1:
            raise ValidationError(
                "max_concurrent must be at least 1.",
                details={"max_concurrent": self.max_concurrent},
            )
        if self.overlap is not OverlapPolicy.ALLOW and self.max_concurrent > 1:
            raise ValidationError(
                "max_concurrent above 1 requires an overlap policy of 'allow'. "
                "Otherwise the two settings disagree about whether overlap is permitted.",
                details={"overlap": str(self.overlap), "max_concurrent": self.max_concurrent},
            )

    def to_primitive(self) -> dict[str, Any]:
        """Return a stable representation."""
        return {
            "timeout": {
                "run_timeout_seconds": self.timeout.run_timeout.to_primitive(),
                "termination_grace_seconds": self.timeout.termination_grace.to_primitive(),
            },
            "retry": {
                "max_attempts": self.retry.max_attempts,
                "backoff": str(self.retry.backoff),
                "base_delay_seconds": self.retry.base_delay.to_primitive(),
                "max_delay_seconds": self.retry.max_delay.to_primitive(),
                "retry_outcome_failures": self.retry.retry_outcome_failures,
                "retry_timeouts": self.retry.retry_timeouts,
            },
            "overlap": str(self.overlap),
            "max_concurrent": self.max_concurrent,
            "activation_policy": str(self.activation_policy),
        }

    @classmethod
    def from_primitive(cls, data: dict[str, Any]) -> Self:
        """Rebuild from a stored representation.

        Args:
            data: A previously produced mapping.

        Returns:
            The execution controls.

        Raises:
            ValidationError: If the mapping is malformed.
        """
        from taskcontrol.domain.common.values import Duration
        from taskcontrol.domain.execution.results import BackoffStrategy

        if not isinstance(data, dict):
            raise ValidationError("Execution controls must be a mapping.")

        timeout_data = data.get("timeout") or {}
        retry_data = data.get("retry") or {}
        return cls(
            timeout=TimeoutPolicy(
                run_timeout=Duration(timeout_data.get("run_timeout_seconds", 0)),
                termination_grace=Duration(timeout_data.get("termination_grace_seconds", 0)),
            ),
            retry=RetryPolicy(
                max_attempts=retry_data.get("max_attempts", 1),
                backoff=BackoffStrategy(retry_data.get("backoff", BackoffStrategy.EXPONENTIAL)),
                base_delay=Duration(retry_data.get("base_delay_seconds", 30)),
                max_delay=Duration(retry_data.get("max_delay_seconds", 3600)),
                retry_outcome_failures=bool(retry_data.get("retry_outcome_failures", False)),
                retry_timeouts=bool(retry_data.get("retry_timeouts", False)),
            ),
            overlap=OverlapPolicy(data.get("overlap", OverlapPolicy.FORBID)),
            max_concurrent=data.get("max_concurrent", 1),
            # Absent in schema 1.0 bundles; the strict default is what they should get.
            activation_policy=ActivationPolicy(
                data.get("activation_policy", ActivationPolicy.REQUIRE_CONTROL_STATE)
            ),
        )


@dataclass(frozen=True, slots=True)
class TaskRevision:
    """An immutable snapshot of everything affecting how a task executes.

    Attributes:
        revision_id: Stable identifier.
        task_id: The parent Task.
        revision_number: Monotonic within the Task.
        schema_version: Version of the public revision schema.
        publication_state: Draft, published, superseded, or withdrawn.
        action: What to execute.
        controls: Timeout, retry, and overlap governance.
        change_summary: Why this revision exists.
        created_at: When the draft was created.
        created_by: Who created it.
        published_at: When it was published, if it has been.
        published_by: Who published it.
        content_digest: Digest of canonical content, set at publication.
    """

    revision_id: TaskRevisionId
    task_id: TaskId
    revision_number: RevisionNumber
    action: ActionSpecification
    created_at: UtcTimestamp
    created_by: OwnerId
    schema_version: SchemaVersion = CURRENT_REVISION_SCHEMA_VERSION
    publication_state: PublicationState = PublicationState.DRAFT
    controls: ExecutionControls = field(default_factory=ExecutionControls)
    change_summary: str = ""
    published_at: UtcTimestamp | None = None
    published_by: OwnerId | None = None
    content_digest: ContentDigest | None = None

    def __post_init__(self) -> None:
        """Validate internal consistency.

        Raises:
            ValidationError: If publication metadata contradicts the publication state.
        """
        if len(self.change_summary) > MAX_CHANGE_SUMMARY_LENGTH:
            raise ValidationError(
                "Change summary is too long.",
                details={"maximum": MAX_CHANGE_SUMMARY_LENGTH},
            )

        if self.publication_state.is_frozen:
            if self.content_digest is None:
                raise ValidationError(
                    "A frozen revision must carry a content digest. Without one its "
                    "content cannot be verified or compared.",
                    details={"publication_state": str(self.publication_state)},
                )
            if self.published_at is None or self.published_by is None:
                raise ValidationError(
                    "A frozen revision must record when and by whom it was published.",
                    details={"publication_state": str(self.publication_state)},
                )
        elif self.content_digest is not None:
            raise ValidationError(
                "A draft revision must not carry a content digest: its content can "
                "still change, so any digest would immediately be a lie.",
            )

    def canonical_content(self) -> dict[str, Any]:
        """Return the content that defines this revision's execution meaning.

        Deliberately excludes identifiers, timestamps, actors, and the digest itself. Two
        revisions created on different days by different people with identical intent
        digest identically, which is what makes drift detection meaningful.

        Returns:
            A canonically ordered mapping.
        """
        return {
            "schema_version": self.schema_version.to_primitive(),
            "action": self.action.to_primitive(),
            "controls": self.controls.to_primitive(),
        }

    def compute_digest(self) -> ContentDigest:
        """Compute the digest of this revision's canonical content.

        Returns:
            The digest. Deterministic across processes and machines.
        """
        return ContentDigest.of_canonical(self.canonical_content())

    @property
    def secret_references(self) -> tuple[SecretReference, ...]:
        """Every secret this revision needs resolved at execution time."""
        return self.action.secret_references

    @property
    def is_editable(self) -> bool:
        """Whether this revision's content may still change."""
        return self.publication_state.is_editable

    def with_changes(self, **changes: Any) -> Self:
        """Return a copy with content changes applied.

        Args:
            **changes: Fields to replace, such as ``action`` or ``controls``.

        Returns:
            The updated draft revision.

        Raises:
            DomainRuleViolationError: If this revision is not a draft. Published content
                is corrected by creating a new revision, never by editing.
        """
        if not self.is_editable:
            raise DomainRuleViolationError(
                "A published revision cannot be edited. Create a new revision instead — "
                "editing in place would change what past executions meant.",
                details={
                    "revision_id": str(self.revision_id),
                    "publication_state": str(self.publication_state),
                },
            )
        return replace(self, **changes)

    def publish(self, *, published_by: OwnerId, published_at: UtcTimestamp) -> Self:
        """Freeze this revision and compute its content digest.

        Args:
            published_by: Who is publishing.
            published_at: When.

        Returns:
            The published, frozen revision.

        Raises:
            DomainRuleViolationError: If this revision is not a draft.
            ValidationError: If the content is not publishable.
        """
        assert_legal_publication_transition(self.publication_state, PublicationState.PUBLISHED)
        self.assert_publishable()

        return replace(
            self,
            publication_state=PublicationState.PUBLISHED,
            published_at=published_at,
            published_by=published_by,
            content_digest=self.compute_digest(),
        )

    def assert_publishable(self) -> None:
        """Raise unless this revision's content may be published.

        Publication is the gate where a mistake stops being cheap, so the checks here are
        the ones that must not be deferred to run time.

        Raises:
            ValidationError: If the content cannot be published.
        """
        if not self.action.executor_type.is_implemented:
            raise ValidationError(
                "This executor type has no adapter in the current phase, so a published "
                "revision using it could never run.",
                details={"executor_type": str(self.action.executor_type)},
            )

        if not self.schema_version.is_compatible_with(CURRENT_REVISION_SCHEMA_VERSION):
            raise ValidationError(
                "Revision schema version is not supported by this build.",
                details={
                    "revision_schema_version": self.schema_version.to_primitive(),
                    "supported": CURRENT_REVISION_SCHEMA_VERSION.to_primitive(),
                },
            )

        for binding in self.action.environment:
            if binding.value is not None and _looks_like_an_inline_secret(binding):
                raise ValidationError(
                    "This environment binding looks like an inline secret. Use a secret "
                    "reference so the value is never stored, logged, or digested.",
                    details={"name": binding.name},
                )

    def supersede(self) -> Self:
        """Mark this revision superseded by a newer active one.

        Returns:
            The superseded revision, its content and digest unchanged.

        Raises:
            DomainRuleViolationError: If the transition is not legal.
        """
        assert_legal_publication_transition(self.publication_state, PublicationState.SUPERSEDED)
        return replace(self, publication_state=PublicationState.SUPERSEDED)

    def withdraw(self) -> Self:
        """Withdraw this revision from use.

        Returns:
            The withdrawn revision, its content and digest unchanged.

        Raises:
            DomainRuleViolationError: If the transition is not legal.
        """
        assert_legal_publication_transition(self.publication_state, PublicationState.WITHDRAWN)
        return replace(self, publication_state=PublicationState.WITHDRAWN)


_SECRET_LIKE_NAMES = ("password", "passwd", "secret", "token", "api_key", "apikey", "credential")
_MIN_SECRET_LIKE_VALUE_LENGTH = 8


def _looks_like_an_inline_secret(binding: Any) -> bool:
    """Whether an environment binding appears to embed a secret value.

    A heuristic, and deliberately a conservative one: it fires on a secret-sounding name
    carrying a non-trivial literal value. False positives are cheap — the author switches
    to a reference, which they should have done anyway.

    Args:
        binding: The environment binding to inspect.

    Returns:
        ``True`` when the binding looks like an embedded secret.
    """
    lowered = binding.name.lower()
    if not any(marker in lowered for marker in _SECRET_LIKE_NAMES):
        return False
    return bool(binding.value) and len(binding.value) >= _MIN_SECRET_LIKE_VALUE_LENGTH
