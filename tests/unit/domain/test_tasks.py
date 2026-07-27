"""Tasks, revisions, and actions.

The invariant under test throughout: **published content never changes.** Everything else
here exists to protect that, because it is what makes an execution record from last year
still mean what it said.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from taskcontrol.common.errors import DomainRuleViolationError, ValidationError
from taskcontrol.domain.common import (
    Duration,
    OwnerId,
    RevisionNumber,
    SchemaVersion,
    SecretReference,
    Slug,
    TaskId,
    TaskRevisionId,
    UtcTimestamp,
)
from taskcontrol.domain.execution import OverlapPolicy, RetryPolicy, TimeoutPolicy
from taskcontrol.domain.tasks import (
    ActionSpecification,
    EnvironmentBinding,
    ExecutionControls,
    ExecutorType,
    PublicationState,
    Task,
    TaskLifecycleState,
    TaskRevision,
    is_legal_publication_transition,
    is_legal_task_transition,
)

NOW = UtcTimestamp(datetime(2026, 7, 27, 6, 0, tzinfo=UTC))
LATER = UtcTimestamp(datetime(2026, 7, 27, 7, 0, tzinfo=UTC))
ACTOR = OwnerId.generate()


def an_action(**overrides: object) -> ActionSpecification:
    """Build a valid shell action for tests."""
    defaults: dict[str, object] = {
        "executor_type": ExecutorType.SHELL,
        "entrypoint": "/usr/bin/bash",
        "arguments": ("/opt/tasks/report.sh", "--date", "2026-07-27"),
    }
    return ActionSpecification(**(defaults | overrides))  # type: ignore[arg-type]


def a_revision(**overrides: object) -> TaskRevision:
    """Build a valid draft revision for tests."""
    defaults: dict[str, object] = {
        "revision_id": TaskRevisionId.generate(),
        "task_id": TaskId.generate(),
        "revision_number": RevisionNumber.first(),
        "action": an_action(),
        "created_at": NOW,
        "created_by": ACTOR,
    }
    return TaskRevision(**(defaults | overrides))  # type: ignore[arg-type]


def a_task(**overrides: object) -> Task:
    """Build a valid draft task for tests."""
    defaults: dict[str, object] = {
        "name": "Daily Settlement Report",
        "owner_id": ACTOR,
        "created_by": ACTOR,
        "created_at": NOW,
    }
    return Task.create(**(defaults | overrides))  # type: ignore[arg-type]


class TestActionSafety:
    def test_arguments_are_a_vector_not_a_string(self) -> None:
        """A vector reaches the OS without a shell, so metacharacters stay data."""
        action = an_action(arguments=("--name", "; rm -rf /"))
        assert action.command_vector() == ("/usr/bin/bash", "--name", "; rm -rf /")

    def test_raw_shell_is_off_by_default(self) -> None:
        assert not an_action().use_raw_shell
        assert not an_action().is_elevated_risk

    def test_raw_shell_is_flagged_as_elevated_risk(self) -> None:
        action = an_action(entrypoint="tidy && report", arguments=(), use_raw_shell=True)
        assert action.is_elevated_risk

    def test_raw_shell_has_no_argument_vector(self) -> None:
        """Asking for one means the caller is about to run it the wrong way."""
        action = an_action(entrypoint="a && b", arguments=(), use_raw_shell=True)
        with pytest.raises(DomainRuleViolationError):
            action.command_vector()

    def test_raw_shell_rejects_separate_arguments(self) -> None:
        with pytest.raises(ValidationError):
            an_action(entrypoint="a && b", arguments=("--x",), use_raw_shell=True)

    def test_raw_shell_only_applies_to_the_shell_executor(self) -> None:
        with pytest.raises(ValidationError):
            an_action(executor_type=ExecutorType.PYTHON, arguments=(), use_raw_shell=True)

    def test_requires_an_entrypoint(self) -> None:
        for entrypoint in ("", "   "):
            with pytest.raises(ValidationError):
                an_action(entrypoint=entrypoint)

    def test_rejects_a_null_byte_in_an_argument(self) -> None:
        with pytest.raises(ValidationError):
            an_action(arguments=("ok", "bad\x00value"))

    def test_rejects_a_non_string_argument(self) -> None:
        with pytest.raises(ValidationError):
            an_action(arguments=("ok", 42))

    def test_rejects_a_relative_working_directory(self) -> None:
        """A relative path depends on wherever the runtime happened to start."""
        with pytest.raises(ValidationError):
            an_action(working_directory="reports")

    def test_rejects_parent_traversal_in_the_working_directory(self) -> None:
        with pytest.raises(ValidationError):
            an_action(working_directory="/opt/tasks/../../etc")

    def test_accepts_an_absolute_working_directory(self) -> None:
        assert an_action(working_directory="/opt/tasks").working_directory == "/opt/tasks"

    def test_rejects_duplicate_environment_names(self) -> None:
        with pytest.raises(ValidationError) as caught:
            an_action(
                environment=(
                    EnvironmentBinding("REGION", value="eu"),
                    EnvironmentBinding("REGION", value="us"),
                )
            )
        assert caught.value.details["duplicates"] == ["REGION"]

    def test_round_trips_through_primitive(self) -> None:
        action = an_action(
            working_directory="/opt/tasks",
            environment=(
                EnvironmentBinding("REGION", value="eu-west-1"),
                EnvironmentBinding("TOKEN", secret=SecretReference.parse("env://API_TOKEN")),
            ),
        )
        assert ActionSpecification.from_primitive(action.to_primitive()) == action

    def test_from_primitive_rejects_an_unknown_executor(self) -> None:
        with pytest.raises(ValidationError) as caught:
            ActionSpecification.from_primitive({"executor_type": "telepathy", "entrypoint": "x"})
        assert "supported" in caught.value.details


class TestEnvironmentBinding:
    def test_holds_a_literal_value(self) -> None:
        assert not EnvironmentBinding("REGION", value="eu").is_secret

    def test_holds_a_secret_reference(self) -> None:
        binding = EnvironmentBinding("TOKEN", secret=SecretReference.parse("env://TOKEN"))
        assert binding.is_secret

    def test_rejects_both_a_value_and_a_secret(self) -> None:
        with pytest.raises(ValidationError):
            EnvironmentBinding(
                "TOKEN", value="literal", secret=SecretReference.parse("env://TOKEN")
            )

    def test_rejects_neither(self) -> None:
        with pytest.raises(ValidationError):
            EnvironmentBinding("TOKEN")

    @pytest.mark.parametrize("name", ["", "1STARTS_WITH_DIGIT", "HAS-HYPHEN", "HAS SPACE"])
    def test_rejects_invalid_names(self, name: str) -> None:
        with pytest.raises(ValidationError):
            EnvironmentBinding(name, value="x")

    def test_a_secret_binding_serialises_only_the_reference(self) -> None:
        binding = EnvironmentBinding("TOKEN", secret=SecretReference.parse("env://API_TOKEN"))
        assert binding.to_primitive() == {"name": "TOKEN", "secret": "env://API_TOKEN"}


class TestExecutionControls:
    def test_defaults_forbid_overlap(self) -> None:
        """The safe default: two copies of a report job should not run at once."""
        assert ExecutionControls().overlap is OverlapPolicy.FORBID

    def test_rejects_concurrency_above_one_without_allowing_overlap(self) -> None:
        """The two settings would otherwise disagree about whether overlap is permitted."""
        with pytest.raises(ValidationError):
            ExecutionControls(overlap=OverlapPolicy.FORBID, max_concurrent=4)

    def test_permits_concurrency_when_overlap_is_allowed(self) -> None:
        controls = ExecutionControls(overlap=OverlapPolicy.ALLOW, max_concurrent=4)
        assert controls.max_concurrent == 4

    def test_rejects_zero_concurrency(self) -> None:
        with pytest.raises(ValidationError):
            ExecutionControls(max_concurrent=0)

    def test_round_trips_through_primitive(self) -> None:
        controls = ExecutionControls(
            timeout=TimeoutPolicy(run_timeout=Duration(1200), termination_grace=Duration(30)),
            retry=RetryPolicy(max_attempts=3, retry_timeouts=True),
            overlap=OverlapPolicy.ALLOW,
            max_concurrent=2,
        )
        assert ExecutionControls.from_primitive(controls.to_primitive()) == controls


class TestRevisionImmutability:
    def test_a_draft_carries_no_digest(self) -> None:
        """Content can still change, so any digest would immediately be a lie."""
        assert a_revision().content_digest is None

    def test_a_draft_may_be_edited(self) -> None:
        revision = a_revision()
        updated = revision.with_changes(change_summary="clarify arguments")
        assert updated.change_summary == "clarify arguments"

    def test_publishing_freezes_and_digests(self) -> None:
        published = a_revision().publish(published_by=ACTOR, published_at=NOW)
        assert published.publication_state is PublicationState.PUBLISHED
        assert published.content_digest is not None
        assert published.published_by == ACTOR

    def test_a_published_revision_cannot_be_edited(self) -> None:
        """The whole point: editing in place would change what past executions meant."""
        published = a_revision().publish(published_by=ACTOR, published_at=NOW)
        with pytest.raises(DomainRuleViolationError) as caught:
            published.with_changes(change_summary="sneaky change")
        assert "new revision" in caught.value.message

    def test_a_published_revision_cannot_be_published_again(self) -> None:
        published = a_revision().publish(published_by=ACTOR, published_at=NOW)
        with pytest.raises(DomainRuleViolationError):
            published.publish(published_by=ACTOR, published_at=LATER)

    def test_a_frozen_revision_must_carry_a_digest(self) -> None:
        with pytest.raises(ValidationError):
            a_revision(
                publication_state=PublicationState.PUBLISHED,
                published_at=NOW,
                published_by=ACTOR,
            )

    def test_a_frozen_revision_must_record_who_published_it(self) -> None:
        digest = a_revision().compute_digest()
        with pytest.raises(ValidationError):
            a_revision(publication_state=PublicationState.PUBLISHED, content_digest=digest)

    def test_a_draft_must_not_carry_a_digest(self) -> None:
        with pytest.raises(ValidationError):
            a_revision(content_digest=a_revision().compute_digest())


class TestContentDigest:
    def test_identical_intent_digests_identically(self) -> None:
        """Reproducibility across machines is what makes drift detection meaningful."""
        first = a_revision(revision_id=TaskRevisionId.generate())
        second = a_revision(revision_id=TaskRevisionId.generate())
        assert first.compute_digest() == second.compute_digest()

    def test_changing_the_action_changes_the_digest(self) -> None:
        original = a_revision()
        changed = original.with_changes(action=an_action(arguments=("--different",)))
        assert original.compute_digest() != changed.compute_digest()

    def test_changing_controls_changes_the_digest(self) -> None:
        original = a_revision()
        changed = original.with_changes(
            controls=ExecutionControls(retry=RetryPolicy(max_attempts=5))
        )
        assert original.compute_digest() != changed.compute_digest()

    def test_identifiers_and_actors_do_not_affect_the_digest(self) -> None:
        """Two people creating identical intent on different days must agree."""
        first = a_revision(created_at=NOW, created_by=OwnerId.generate())
        second = a_revision(created_at=LATER, created_by=OwnerId.generate())
        assert first.compute_digest() == second.compute_digest()

    def test_a_secret_reference_participates_but_no_value_can(self) -> None:
        with_secret = a_revision(
            action=an_action(
                environment=(
                    EnvironmentBinding("TOKEN", secret=SecretReference.parse("env://TOKEN")),
                )
            )
        )
        content = str(with_secret.canonical_content())
        assert "env://TOKEN" in content


class TestPublicationValidation:
    def test_rejects_an_unimplemented_executor(self) -> None:
        """Publishing something that could never run is a mistake caught at the gate."""
        revision = a_revision(action=an_action(executor_type=ExecutorType.TCL))
        with pytest.raises(ValidationError) as caught:
            revision.publish(published_by=ACTOR, published_at=NOW)
        assert caught.value.details["executor_type"] == "tcl"

    def test_rejects_an_unsupported_schema_version(self) -> None:
        revision = a_revision(schema_version=SchemaVersion(9, 0))
        with pytest.raises(ValidationError):
            revision.publish(published_by=ACTOR, published_at=NOW)

    def test_rejects_an_inline_secret(self) -> None:
        """A secret-sounding name with a real value must become a reference."""
        revision = a_revision(
            action=an_action(
                environment=(EnvironmentBinding("DB_PASSWORD", value="hunter2-real-value"),)
            )
        )
        with pytest.raises(ValidationError) as caught:
            revision.publish(published_by=ACTOR, published_at=NOW)
        assert caught.value.details["name"] == "DB_PASSWORD"

    def test_permits_a_secret_reference(self) -> None:
        revision = a_revision(
            action=an_action(
                environment=(
                    EnvironmentBinding(
                        "DB_PASSWORD", secret=SecretReference.parse("env://DB_PASSWORD")
                    ),
                )
            )
        )
        assert revision.publish(published_by=ACTOR, published_at=NOW).content_digest

    def test_does_not_flag_an_innocuous_binding(self) -> None:
        revision = a_revision(
            action=an_action(environment=(EnvironmentBinding("REGION", value="eu-west-1"),))
        )
        assert revision.publish(published_by=ACTOR, published_at=NOW).content_digest


class TestRevisionSupersession:
    def test_a_published_revision_may_be_superseded(self) -> None:
        published = a_revision().publish(published_by=ACTOR, published_at=NOW)
        superseded = published.supersede()
        assert superseded.publication_state is PublicationState.SUPERSEDED

    def test_supersession_preserves_content_and_digest(self) -> None:
        published = a_revision().publish(published_by=ACTOR, published_at=NOW)
        superseded = published.supersede()
        assert superseded.content_digest == published.content_digest
        assert superseded.action == published.action

    def test_a_draft_cannot_be_superseded(self) -> None:
        with pytest.raises(DomainRuleViolationError):
            a_revision().supersede()

    def test_a_withdrawn_revision_is_terminal(self) -> None:
        withdrawn = a_revision().publish(published_by=ACTOR, published_at=NOW).withdraw()
        with pytest.raises(DomainRuleViolationError):
            withdrawn.supersede()

    @pytest.mark.parametrize(
        ("current", "proposed", "legal"),
        [
            (PublicationState.DRAFT, PublicationState.PUBLISHED, True),
            (PublicationState.DRAFT, PublicationState.SUPERSEDED, False),
            (PublicationState.PUBLISHED, PublicationState.DRAFT, False),
            (PublicationState.PUBLISHED, PublicationState.SUPERSEDED, True),
            (PublicationState.SUPERSEDED, PublicationState.PUBLISHED, False),
            (PublicationState.WITHDRAWN, PublicationState.PUBLISHED, False),
        ],
    )
    def test_publication_transition_table(
        self, current: PublicationState, proposed: PublicationState, legal: bool
    ) -> None:
        assert is_legal_publication_transition(current, proposed) is legal


class TestTaskLifecycle:
    def test_a_new_task_is_a_draft(self) -> None:
        """A task is never born active: it has no revision to run."""
        assert a_task().lifecycle_state is TaskLifecycleState.DRAFT

    def test_a_draft_does_not_accept_triggers(self) -> None:
        assert not a_task().accepts_triggers

    def test_a_slug_is_derived_from_the_name(self) -> None:
        assert a_task().slug == Slug("daily-settlement-report")

    def test_an_explicit_slug_is_honoured(self) -> None:
        assert a_task(slug=Slug("settlement")).slug == Slug("settlement")

    def test_activating_a_revision_makes_the_task_active(self) -> None:
        revision_id = TaskRevisionId.generate()
        task = a_task().activate_revision(revision_id, updated_by=ACTOR, updated_at=LATER)
        assert task.lifecycle_state is TaskLifecycleState.ACTIVE
        assert task.active_revision_id == revision_id
        assert task.accepts_triggers

    def test_an_active_task_must_reference_a_revision(self) -> None:
        with pytest.raises(ValidationError):
            Task(
                task_id=TaskId.generate(),
                name="Orphan",
                slug=Slug("orphan"),
                owner_id=ACTOR,
                created_at=NOW,
                created_by=ACTOR,
                lifecycle_state=TaskLifecycleState.ACTIVE,
            )

    def test_a_task_cannot_become_active_without_a_revision(self) -> None:
        with pytest.raises(DomainRuleViolationError):
            a_task().transition_to(TaskLifecycleState.ACTIVE, updated_by=ACTOR, updated_at=LATER)

    def test_suspend_and_resume(self) -> None:
        active = a_task().activate_revision(
            TaskRevisionId.generate(), updated_by=ACTOR, updated_at=LATER
        )
        suspended = active.suspend(updated_by=ACTOR, updated_at=LATER)
        assert not suspended.accepts_triggers
        assert suspended.resume(updated_by=ACTOR, updated_at=LATER).accepts_triggers

    def test_suspension_keeps_the_active_revision(self) -> None:
        """A suspended task keeps a perfectly good revision; only availability changed."""
        revision_id = TaskRevisionId.generate()
        active = a_task().activate_revision(revision_id, updated_by=ACTOR, updated_at=LATER)
        assert active.suspend(updated_by=ACTOR, updated_at=LATER).active_revision_id == revision_id

    def test_an_archived_task_is_read_only(self) -> None:
        archived = a_task().archive(updated_by=ACTOR, updated_at=LATER)
        with pytest.raises(DomainRuleViolationError):
            archived.update_metadata(name="New name", updated_by=ACTOR, updated_at=LATER)

    def test_an_archived_task_cannot_activate_a_revision(self) -> None:
        archived = a_task().archive(updated_by=ACTOR, updated_at=LATER)
        with pytest.raises(DomainRuleViolationError):
            archived.activate_revision(
                TaskRevisionId.generate(), updated_by=ACTOR, updated_at=LATER
            )

    def test_archived_is_terminal(self) -> None:
        archived = a_task().archive(updated_by=ACTOR, updated_at=LATER)
        for state in TaskLifecycleState:
            assert not is_legal_task_transition(archived.lifecycle_state, state)

    @pytest.mark.parametrize(
        ("current", "proposed", "legal"),
        [
            (TaskLifecycleState.DRAFT, TaskLifecycleState.ACTIVE, True),
            (TaskLifecycleState.DRAFT, TaskLifecycleState.SUSPENDED, False),
            (TaskLifecycleState.ACTIVE, TaskLifecycleState.SUSPENDED, True),
            (TaskLifecycleState.ACTIVE, TaskLifecycleState.ARCHIVED, False),
            (TaskLifecycleState.SUSPENDED, TaskLifecycleState.ACTIVE, True),
            (TaskLifecycleState.RETIRED, TaskLifecycleState.ACTIVE, True),
            (TaskLifecycleState.ARCHIVED, TaskLifecycleState.ACTIVE, False),
        ],
    )
    def test_task_transition_table(
        self, current: TaskLifecycleState, proposed: TaskLifecycleState, legal: bool
    ) -> None:
        assert is_legal_task_transition(current, proposed) is legal


class TestTaskMetadata:
    def test_renaming_does_not_require_a_revision(self) -> None:
        """Display metadata cannot change what runs, so it is a plain mutation."""
        task = a_task().update_metadata(
            name="Settlement Report", updated_by=ACTOR, updated_at=LATER
        )
        assert task.name == "Settlement Report"
        assert task.updated_by == ACTOR

    def test_renaming_does_not_change_the_slug(self) -> None:
        """The slug appears in URLs and artefacts; renaming must not break a reference."""
        original = a_task()
        renamed = original.update_metadata(
            name="Completely Different", updated_by=ACTOR, updated_at=LATER
        )
        assert renamed.slug == original.slug

    def test_ownership_can_change(self) -> None:
        new_owner = OwnerId.generate()
        task = a_task().update_metadata(owner_id=new_owner, updated_by=ACTOR, updated_at=LATER)
        assert task.owner_id == new_owner

    def test_omitted_fields_are_left_alone(self) -> None:
        original = a_task(description="Original description")
        updated = original.update_metadata(name="Renamed", updated_by=ACTOR, updated_at=LATER)
        assert updated.description == "Original description"

    def test_rejects_an_empty_name(self) -> None:
        with pytest.raises(ValidationError):
            a_task(name="   ")

    def test_rejects_an_over_long_name(self) -> None:
        with pytest.raises(ValidationError):
            a_task(name="x" * 500)

    def test_serialises_to_a_stable_representation(self) -> None:
        primitive = a_task().to_primitive()
        assert primitive["lifecycle_state"] == "draft"
        assert primitive["slug"] == "daily-settlement-report"
        assert primitive["active_revision_id"] is None
