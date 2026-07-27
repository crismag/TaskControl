"""The installed revision, and the coupling that must never quietly break.

An installed manifest carries the *revision's own* digest. That is what lets an operator
check what is installed against what was published, and against the digest written into the
cron artefact's marker. It only works while the manifest digests exactly the same content
the revision does — and when it stopped doing so, nothing failed loudly: every manifest
simply became unverifiable, and every cron activation refused to run.

So that coupling is asserted here directly, rather than left to be rediscovered.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from taskcontrol.common.errors import ValidationError
from taskcontrol.domain.common.identifiers import OwnerId, TaskRevisionId
from taskcontrol.domain.common.values import RevisionNumber, UtcTimestamp
from taskcontrol.domain.deployment.manifest import (
    MANIFEST_FORMAT_VERSION,
    InstalledRevision,
)
from taskcontrol.domain.deployment.strategies import (
    DeploymentSpecification,
    PeriodicClassification,
)
from taskcontrol.domain.tasks.actions import ActionSpecification, ExecutorType
from taskcontrol.domain.tasks.revision import (
    ActivationPolicy,
    ExecutionControls,
    TaskRevision,
)
from taskcontrol.domain.tasks.task import Task

NOW = UtcTimestamp(datetime(2026, 7, 27, 9, 0, tzinfo=UTC))
ACTOR = OwnerId.generate()


def a_task() -> Task:
    return Task.create(name="Nightly backup", owner_id=ACTOR, created_by=ACTOR, created_at=NOW)


def a_revision(task: Task, **overrides: object) -> TaskRevision:
    fields: dict[str, object] = {
        "revision_id": TaskRevisionId.generate(),
        "task_id": task.task_id,
        "revision_number": RevisionNumber(1),
        "action": ActionSpecification(
            executor_type=ExecutorType.EXECUTABLE, entrypoint="/usr/bin/backup"
        ),
        "created_at": NOW,
        "created_by": ACTOR,
        "controls": ExecutionControls(
            activation_policy=ActivationPolicy.CONTINUE_WITH_LOCAL_JOURNAL
        ),
        "deployment": DeploymentSpecification.for_classification(PeriodicClassification.DAILY),
    }
    fields.update(overrides)
    return TaskRevision(**fields)  # type: ignore[arg-type]


class TestDigestCoupling:
    def test_a_manifest_digests_exactly_what_its_revision_digests(self) -> None:
        """The coupling. Break it and every manifest silently becomes unverifiable.

        Not "an error appears somewhere" — every cron activation on every host refuses to
        run, and the message says the manifest was tampered with, which it was not.
        """
        task = a_task()
        revision = a_revision(task).publish(published_by=ACTOR, published_at=NOW)

        installed = InstalledRevision.install(task, revision)

        assert installed.content_digest == revision.compute_digest()
        installed.verify_integrity()

    def test_a_field_added_to_the_revision_must_reach_the_manifest(self) -> None:
        """A revision field that changes execution meaning must change both digests.

        This is the shape of the failure that already happened once: the revision gained a
        deployment specification and the manifest did not, so the two digests diverged for
        every capability at once.
        """
        task = a_task()
        first = a_revision(
            task,
            deployment=DeploymentSpecification.for_classification(PeriodicClassification.DAILY),
        ).publish(published_by=ACTOR, published_at=NOW)
        second = a_revision(
            task,
            deployment=DeploymentSpecification.for_classification(PeriodicClassification.WEEKLY),
        ).publish(published_by=ACTOR, published_at=NOW)

        assert first.content_digest != second.content_digest
        assert (
            InstalledRevision.install(task, first).content_digest
            != InstalledRevision.install(task, second).content_digest
        )


class TestInstallation:
    def test_a_draft_cannot_be_installed(self) -> None:
        """Its content can still change underneath the deployment, and it has no digest."""
        task = a_task()

        with pytest.raises(ValidationError, match="published"):
            InstalledRevision.install(task, a_revision(task))

    def test_the_activation_policy_comes_from_the_manifest(self) -> None:
        """The whole point: a wrapper learns its degraded-mode policy without the database."""
        task = a_task()
        revision = a_revision(task).publish(published_by=ACTOR, published_at=NOW)

        installed = InstalledRevision.install(task, revision)

        assert installed.activation_policy is ActivationPolicy.CONTINUE_WITH_LOCAL_JOURNAL
        assert installed.activation_policy.executes_without_control_state


class TestRoundTrip:
    def test_a_manifest_survives_being_written_and_read(self) -> None:
        task = a_task()
        revision = a_revision(task).publish(published_by=ACTOR, published_at=NOW)
        installed = InstalledRevision.install(task, revision)

        restored = InstalledRevision.from_primitive(installed.to_primitive())

        assert restored == installed
        restored.verify_integrity()

    def test_a_modified_manifest_is_refused(self) -> None:
        """Cron runs whatever it finds, so this is the only thing standing between an
        edited file and a privileged process running something nobody published."""
        task = a_task()
        revision = a_revision(task).publish(published_by=ACTOR, published_at=NOW)
        data = InstalledRevision.install(task, revision).to_primitive()
        data["action"]["entrypoint"] = "/bin/rm"

        with pytest.raises(ValidationError, match="modified after installation"):
            InstalledRevision.from_primitive(data).verify_integrity()

    def test_an_unknown_format_version_is_refused_rather_than_guessed(self) -> None:
        task = a_task()
        revision = a_revision(task).publish(published_by=ACTOR, published_at=NOW)
        data = InstalledRevision.install(task, revision).to_primitive()
        data["format_version"] = MANIFEST_FORMAT_VERSION + 1

        with pytest.raises(ValidationError, match="format version"):
            InstalledRevision.from_primitive(data)
