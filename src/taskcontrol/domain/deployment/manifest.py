"""The installed revision — what a cron-woken wrapper reads instead of the database.

R1 Finding 2: the runtime reached persistence before it could do anything at all, including
learn its own activation policy. So the availability-first mode of ADR 0024 was
unimplementable — a wrapper cannot decide what to do when the control plane is unreachable
if it must ask the control plane what to do.

The fix is a boundary, not a fallback path:

```text
Control plane          resolves and validates
      |
Installed revision     immutable local representation
      |
Cron wrapper           loads locally, decides locally
      |
Runtime                executes
```

The wrapper never asks *"what is the current definition of this task?"*. It asks
*"execute installed revision R, whose validated manifest is here."* That distinction is
what makes immutability reach all the way to activation: without it, a revision can change
between deployment and firing, and a locally journalled run would record a revision that no
longer means what it meant.

**Secrets are references, never values.** A manifest is a file on disk next to a cron
artefact; putting a resolved secret in it would put it somewhere no rotation reaches and no
audit sees. The consequence is deliberate and must stay visible: a capability needing a
secret it cannot resolve locally **cannot run** in degraded mode, and says so, rather than
running with something missing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Self

from taskcontrol.common.errors import ValidationError
from taskcontrol.domain.common.identifiers import TaskId, TaskRevisionId
from taskcontrol.domain.common.values import ContentDigest, RevisionNumber, Slug
from taskcontrol.domain.deployment.strategies import DeploymentSpecification
from taskcontrol.domain.tasks.actions import ActionSpecification
from taskcontrol.domain.tasks.revision import (
    CURRENT_REVISION_SCHEMA_VERSION,
    ActivationPolicy,
    ExecutionControls,
    TaskRevision,
)
from taskcontrol.domain.tasks.task import Task

MANIFEST_FORMAT_VERSION = 1
"""Version of the manifest file format itself.

Distinct from the revision schema version: this describes the envelope a wrapper reads,
and a wrapper that does not understand the format must refuse rather than guess.
"""


@dataclass(frozen=True, slots=True)
class InstalledRevision:
    """Everything a cron-woken wrapper needs, resolvable without the control plane.

    Written at deploy time and never afterwards. It is the local half of the immutability
    guarantee: the deployed artefact and the definition it executes are installed together
    and change together.

    Attributes:
        task_id: The capability, so a later reconciliation can attribute the run.
        slug: Its stable name, which is how an operator and the artefact refer to it.
        revision_id: The exact revision installed.
        revision_number: Which revision of the capability this is, for a human reading it.
        content_digest: The digest of the revision's canonical content, verified on load.
        action: What to execute — entrypoint, arguments, working directory, environment.
        controls: Timeout, retry, overlap, and the activation policy.
        deployment: Where the artefact was installed. The wrapper never reads it — but it
            is part of what was published, and the manifest digest must reproduce the
            revision's digest exactly or "installed revision R" cannot be checked against
            anything.
        activation_schedule: When cron activates this, for the same reason.
        description: What this capability is for, so the file explains itself.
    """

    task_id: TaskId
    slug: Slug
    revision_id: TaskRevisionId
    revision_number: RevisionNumber
    content_digest: ContentDigest
    action: ActionSpecification
    controls: ExecutionControls
    deployment: DeploymentSpecification = field(default_factory=DeploymentSpecification)
    activation_schedule: str | None = None
    description: str = ""

    @property
    def activation_policy(self) -> ActivationPolicy:
        """What to do when the control plane is unreachable.

        Read from the manifest, never from the database. A wrapper that had to ask the
        control plane for its own degraded-mode policy would have no policy exactly when
        it needed one.
        """
        return self.controls.activation_policy

    @property
    def requires_unresolvable_secrets(self) -> bool:
        """Whether this capability needs secrets a local wrapper cannot resolve.

        Manifests carry references, never values. A capability whose action needs a secret
        therefore cannot run while the control plane is unreachable — it must refuse and
        say so, rather than run with an environment that is quietly incomplete.
        """
        return bool(self.action.secret_references)

    @classmethod
    def install(cls, task: Task, revision: TaskRevision) -> Self:
        """Build a manifest from a published capability and revision.

        Args:
            task: The capability.
            revision: The revision being installed.

        Returns:
            The installed revision.

        Raises:
            ValidationError: If the revision is not published. An unpublished revision has
                no digest, so nothing installed from it could be verified — and its content
                can still change, which is precisely what installation must rule out.
        """
        if revision.content_digest is None:
            raise ValidationError(
                "Only a published revision can be installed. A draft has no content "
                "digest, so what was installed could never be verified against what was "
                "meant — and its content can still change underneath the deployment.",
                details={"slug": task.slug.to_primitive()},
            )

        return cls(
            task_id=task.task_id,
            slug=task.slug,
            revision_id=revision.revision_id,
            revision_number=revision.revision_number,
            content_digest=revision.content_digest,
            action=revision.action,
            controls=revision.controls,
            deployment=revision.deployment,
            activation_schedule=(
                revision.activation_schedule.to_primitive()
                if revision.activation_schedule
                else None
            ),
            description=task.description or task.name,
        )

    def verify_integrity(self) -> None:
        """Raise unless this manifest's content matches the digest it carries.

        A manifest is a file on a host that an administrator can edit, and cron will run
        whatever it finds. Verifying on load is what makes "installed revision R" a claim
        rather than a hope.

        Raises:
            ValidationError: If the content does not match the digest.
        """
        computed = ContentDigest.of_canonical(self._digestible_content())
        if computed != self.content_digest:
            raise ValidationError(
                f"The installed manifest for '{self.slug}' does not match its own digest, "
                "so it was modified after installation. Refusing to run it. Re-run "
                "'taskctl schedule apply' to reinstall from the published revision.",
                details={
                    "slug": self.slug.to_primitive(),
                    "revision_id": self.revision_id.to_primitive(),
                },
            )

    def _digestible_content(self) -> dict[str, Any]:
        """Return the content the digest covers.

        **Must stay identical to** :meth:`TaskRevision.canonical_content`. The digest a
        manifest carries is the revision's own digest, which is what lets an operator check
        an installed manifest against the published revision and against the digest written
        into the cron artefact's marker. A field added to one and not the other silently
        makes every manifest unverifiable — which is exactly what happened when the
        revision gained ``deployment`` in schema 1.2 and this did not.
        """
        return {
            "schema_version": CURRENT_REVISION_SCHEMA_VERSION.to_primitive(),
            "action": self.action.to_primitive(),
            "controls": self.controls.to_primitive(),
            "deployment": self.deployment.to_primitive(),
            "activation_schedule": self.activation_schedule,
        }

    def to_primitive(self) -> dict[str, Any]:
        """Return the manifest as plain data, ready to be written.

        Returns:
            A mapping. Keys are ordered so a human opening the file reads identity first
            and payload second.
        """
        return {
            "format_version": MANIFEST_FORMAT_VERSION,
            "task_id": self.task_id.to_primitive(),
            "slug": self.slug.to_primitive(),
            "revision_id": self.revision_id.to_primitive(),
            "revision_number": self.revision_number.to_primitive(),
            "content_digest": self.content_digest.to_primitive(),
            "description": self.description,
            "action": self.action.to_primitive(),
            "controls": self.controls.to_primitive(),
            "deployment": self.deployment.to_primitive(),
            "activation_schedule": self.activation_schedule,
        }

    @classmethod
    def from_primitive(cls, data: dict[str, Any]) -> Self:
        """Rebuild a manifest from a written file.

        Args:
            data: The parsed file contents.

        Returns:
            The installed revision. **Not** integrity-checked here; call
            :meth:`verify_integrity` before acting on it.

        Raises:
            ValidationError: If the file is malformed or written by a newer TaskControl.
        """
        if not isinstance(data, dict):
            raise ValidationError("An installed manifest must be a mapping.")

        version = data.get("format_version")
        if version != MANIFEST_FORMAT_VERSION:
            raise ValidationError(
                f"This installed manifest is format version {version!r}, and this build "
                f"understands {MANIFEST_FORMAT_VERSION}. Refusing to guess what it means.",
                details={"found": version, "supported": MANIFEST_FORMAT_VERSION},
            )

        try:
            return cls(
                task_id=TaskId(data["task_id"]),
                slug=Slug(data["slug"]),
                revision_id=TaskRevisionId(data["revision_id"]),
                revision_number=RevisionNumber(data["revision_number"]),
                content_digest=ContentDigest(data["content_digest"]),
                action=ActionSpecification.from_primitive(data["action"]),
                controls=ExecutionControls.from_primitive(data.get("controls") or {}),
                deployment=DeploymentSpecification.from_primitive(data.get("deployment") or {}),
                activation_schedule=data.get("activation_schedule"),
                description=data.get("description", ""),
            )
        except KeyError as error:
            raise ValidationError(
                "An installed manifest is missing a required field.",
                details={"missing_field": str(error.args[0])},
            ) from error
