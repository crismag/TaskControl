"""Portable task bundles: YAML and JSON on the outside, domain objects on the inside.

This lives in an adapter, not in the domain, because the domain may import only the
standard library and PyYAML is a third-party library. That constraint is a feature: it
forces the domain to expose ``to_primitive``/``from_primitive`` and keeps serialisation
format entirely replaceable.

Round-tripping is exact by design. ``load(dump(bundle))`` returns an equal bundle, and
``dump`` of the result is byte-identical, so a definition kept in version control produces
a clean diff when — and only when — it actually changed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Self

import yaml

from taskcontrol.common.errors import ValidationError
from taskcontrol.domain.common.identifiers import OwnerId, TaskId, TaskRevisionId
from taskcontrol.domain.common.values import (
    RevisionNumber,
    SchemaVersion,
    Slug,
    UtcTimestamp,
)
from taskcontrol.domain.deployment.strategies import DeploymentSpecification
from taskcontrol.domain.scheduling.expressions import parse_schedule_expression
from taskcontrol.domain.scheduling.schedules import CronExpression
from taskcontrol.domain.tasks.actions import ActionSpecification
from taskcontrol.domain.tasks.lifecycle import PublicationState, TaskLifecycleState
from taskcontrol.domain.tasks.revision import (
    CURRENT_REVISION_SCHEMA_VERSION,
    ExecutionControls,
    TaskRevision,
)
from taskcontrol.domain.tasks.task import Task

BUNDLE_KIND = "TaskBundle"


@dataclass(frozen=True, slots=True)
class TaskBundle:
    """A task and one of its revisions, in portable form.

    Attributes:
        task: The task.
        revision: The revision being carried.
    """

    task: Task
    revision: TaskRevision

    def __post_init__(self) -> None:
        """Validate that the pair belongs together.

        Raises:
            ValidationError: If the revision does not belong to the task.
        """
        if self.revision.task_id != self.task.task_id:
            raise ValidationError(
                "The revision in a bundle must belong to the bundle's task.",
                details={
                    "task_id": str(self.task.task_id),
                    "revision_task_id": str(self.revision.task_id),
                },
            )

    def to_primitive(self) -> dict[str, Any]:
        """Return the bundle as plain data.

        Returns:
            A mapping with deterministic key ordering.
        """
        return {
            "kind": BUNDLE_KIND,
            "schema_version": self.revision.schema_version.to_primitive(),
            "task": self.task.to_primitive(),
            "revision": {
                "revision_id": self.revision.revision_id.to_primitive(),
                "revision_number": self.revision.revision_number.to_primitive(),
                "publication_state": str(self.revision.publication_state),
                "change_summary": self.revision.change_summary,
                "created_at": self.revision.created_at.to_primitive(),
                "created_by": self.revision.created_by.to_primitive(),
                "published_at": (
                    self.revision.published_at.to_primitive()
                    if self.revision.published_at
                    else None
                ),
                "published_by": (
                    self.revision.published_by.to_primitive()
                    if self.revision.published_by
                    else None
                ),
                "content_digest": (
                    self.revision.content_digest.to_primitive()
                    if self.revision.content_digest
                    else None
                ),
                "action": self.revision.action.to_primitive(),
                "controls": self.revision.controls.to_primitive(),
                "deployment": self.revision.deployment.to_primitive(),
                "activation_schedule": (
                    self.revision.activation_schedule.to_primitive()
                    if self.revision.activation_schedule
                    else None
                ),
            },
        }

    @classmethod
    def from_primitive(cls, data: dict[str, Any]) -> Self:
        """Rebuild a bundle from plain data.

        Args:
            data: A previously produced mapping.

        Returns:
            The bundle.

        Raises:
            ValidationError: If the data is malformed or its schema is unsupported.
        """
        if not isinstance(data, dict):
            raise ValidationError("A task bundle must be a mapping.")
        if data.get("kind") != BUNDLE_KIND:
            raise ValidationError(
                "Not a TaskControl task bundle.",
                details={"expected_kind": BUNDLE_KIND, "received_kind": data.get("kind")},
            )

        schema_version = SchemaVersion.parse(str(data.get("schema_version", "")))
        if not schema_version.is_compatible_with(CURRENT_REVISION_SCHEMA_VERSION):
            raise ValidationError(
                "This bundle's schema version is not supported by this build.",
                details={
                    "bundle_schema_version": schema_version.to_primitive(),
                    "supported": CURRENT_REVISION_SCHEMA_VERSION.to_primitive(),
                },
            )

        task_data = _require_mapping(data, "task")
        revision_data = _require_mapping(data, "revision")

        task = Task(
            task_id=TaskId(task_data["task_id"]),
            name=task_data["name"],
            slug=Slug(task_data["slug"]),
            owner_id=OwnerId(task_data["owner_id"]),
            created_at=UtcTimestamp.from_primitive(task_data["created_at"]),
            created_by=OwnerId(task_data["created_by"]),
            description=task_data.get("description", ""),
            lifecycle_state=TaskLifecycleState(task_data.get("lifecycle_state", "draft")),
            active_revision_id=(
                TaskRevisionId(task_data["active_revision_id"])
                if task_data.get("active_revision_id")
                else None
            ),
            labels=frozenset(task_data.get("labels") or ()),
            updated_at=(
                UtcTimestamp.from_primitive(task_data["updated_at"])
                if task_data.get("updated_at")
                else None
            ),
            updated_by=(OwnerId(task_data["updated_by"]) if task_data.get("updated_by") else None),
        )

        from taskcontrol.domain.common.values import ContentDigest

        revision = TaskRevision(
            revision_id=TaskRevisionId(revision_data["revision_id"]),
            task_id=task.task_id,
            revision_number=RevisionNumber(revision_data["revision_number"]),
            action=ActionSpecification.from_primitive(revision_data["action"]),
            created_at=UtcTimestamp.from_primitive(revision_data["created_at"]),
            created_by=OwnerId(revision_data["created_by"]),
            schema_version=schema_version,
            publication_state=PublicationState(revision_data.get("publication_state", "draft")),
            controls=ExecutionControls.from_primitive(revision_data.get("controls") or {}),
            deployment=DeploymentSpecification.from_primitive(
                revision_data.get("deployment") or {}
            ),
            activation_schedule=_parse_schedule(revision_data.get("activation_schedule")),
            change_summary=revision_data.get("change_summary", ""),
            published_at=(
                UtcTimestamp.from_primitive(revision_data["published_at"])
                if revision_data.get("published_at")
                else None
            ),
            published_by=(
                OwnerId(revision_data["published_by"])
                if revision_data.get("published_by")
                else None
            ),
            content_digest=(
                ContentDigest(revision_data["content_digest"])
                if revision_data.get("content_digest")
                else None
            ),
        )

        return cls(task=task, revision=revision)


def _require_mapping(data: dict[str, Any], key: str) -> dict[str, Any]:
    """Return a required nested mapping.

    Args:
        data: The parent mapping.
        key: The key to read.

    Returns:
        The nested mapping.

    Raises:
        ValidationError: If the key is missing or is not a mapping.
    """
    value = data.get(key)
    if not isinstance(value, dict):
        raise ValidationError(
            f"A task bundle requires a {key!r} mapping.", details={"missing_key": key}
        )
    return value


def dump_yaml(bundle: TaskBundle) -> str:
    """Serialise a bundle to YAML.

    Keys are written in the order the domain produced them rather than sorted, because a
    definition a human maintains should read in a sensible order — action before controls,
    identity before content.

    Args:
        bundle: The bundle to serialise.

    Returns:
        YAML text, ending in a newline.
    """
    return yaml.safe_dump(
        bundle.to_primitive(),
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        width=100,
    )


def load_yaml(text: str) -> TaskBundle:
    """Parse a bundle from YAML.

    Uses ``safe_load``: a task definition is untrusted input, and YAML's full loader can
    construct arbitrary Python objects.

    Args:
        text: YAML text.

    Returns:
        The bundle.

    Raises:
        ValidationError: If the text is not valid YAML or not a valid bundle.
    """
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ValidationError(
            "Task bundle is not valid YAML.", details={"parser_error": str(exc)}
        ) from exc

    if data is None:
        raise ValidationError("Task bundle is empty.")
    return TaskBundle.from_primitive(data)


def _parse_schedule(value: object) -> CronExpression | None:
    """Accept either a cron expression or a human schedule expression.

    ``30 17 * * 1-5`` and ``every weekday at 17:30`` both work, and the distinction is made
    on whether the text contains letters — cron's five fields never do, in the portable
    subset TaskControl accepts. Nothing is guessed: an unrecognised expression of either
    kind is rejected with the accepted forms.

    A bundle written back out carries the cron expression, because that is the canonical
    form and the one the deployed artefact contains. An author who writes English will see
    it normalised on the next dump — the schedule is unchanged, but the wording is not
    preserved.

    Args:
        value: The stored or authored schedule, or ``None``.

    Returns:
        The cron expression, or ``None`` when there is no schedule.

    Raises:
        ValidationError: If the text is neither a valid cron expression nor a recognised
            schedule expression.
    """
    if not value:
        return None
    if not isinstance(value, str):
        raise ValidationError("A schedule must be text.")

    if any(character.isalpha() for character in value):
        return parse_schedule_expression(value)
    return CronExpression(value)
