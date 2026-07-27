"""Deployment strategies — where a managed cron artefact lives and what shape it takes.

The question "one block per task or one block for all?" has no single right answer, because
it is not TaskControl's question. It belongs to the task, and to the operator who knows
whether this is a daily cleanup or the market-close job that runs as ``settlement`` at
17:30 (ADR 0026).

So the layout is a **strategy** carried by the revision, and this module is where the
strategies, the targets they may land on, and the rules relating them live. It contains no
crontab syntax at all — rendering is the cron adapter's job, and keeping the vocabulary here
is what lets a systemd-timer adapter reuse the concept rather than reinvent it.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any, Self

from taskcontrol.common.errors import ValidationError
from taskcontrol.domain.common.values import Slug

MAX_EXECUTION_USER_LENGTH = 32
"""Longest execution user name accepted, matching the usual ``useradd`` limit."""


class DeploymentTarget(StrEnum):
    """Where the artefact is written.

    A target is a *place*. It determines what privilege is needed to write there and
    whether the artefact can name the user the work runs as.
    """

    USER_CRONTAB = "user_crontab"
    """The invoking user's own crontab. No privilege; work runs as that user."""

    SYSTEM_CRONTAB = "system_crontab"
    """``/etc/crontab``. Root to write; each line names its execution user."""

    CRON_D = "cron_d"
    """``/etc/cron.d``. Root to write; each file names its execution user."""

    RUN_PARTS = "run_parts"
    """A run-parts directory such as ``/etc/cron.daily``.

    Root to write. The execution user is configured on the directory's own crontab entry,
    not on the artefact, so an artefact here cannot choose it.
    """

    @property
    def requires_privilege(self) -> bool:
        """Whether writing here needs more than the invoking user's own permissions."""
        return self is not DeploymentTarget.USER_CRONTAB

    @property
    def expresses_execution_user(self) -> bool:
        """Whether an artefact written here can name the user the work runs as."""
        return self in {DeploymentTarget.SYSTEM_CRONTAB, DeploymentTarget.CRON_D}


class DeploymentStrategy(StrEnum):
    """The shape of the artefact TaskControl writes."""

    RUN_PARTS_DIRECTORY = "run_parts_directory"
    """An executable file dropped into ``/etc/cron.daily`` and its siblings.

    The oldest and most widely understood shape of operational automation: put a file in a
    directory and let the system run it. Requires a classification, because the
    classification *is* the schedule — the directory decides when, not the artefact.
    """

    CRONTAB_BLOCK_PER_TASK = "crontab_block_per_task"
    """A marked region per task within a crontab.

    Changes to one task do not rewrite another's region, so two concurrent applies to
    different tasks do not contend. The default for unclassified work.
    """

    CRONTAB_SINGLE_BLOCK = "crontab_single_block"
    """One marked region holding every managed line.

    Tidier to locate and read, and appropriate for a small estate managed as a unit. The
    trade-off is that any apply rewrites the whole region.
    """

    CRON_D_FILE = "cron_d_file"
    """One file per task in ``/etc/cron.d``.

    The only strategy that both isolates a task in its own file *and* names its execution
    user, which is what multi-user hosts need.
    """

    @property
    def permitted_targets(self) -> frozenset[DeploymentTarget]:
        """The targets this strategy may be written to.

        Most strategies imply their target exactly. Only the crontab block strategies have
        a genuine choice, and that choice is between a user crontab and the system one.
        """
        match self:
            case DeploymentStrategy.RUN_PARTS_DIRECTORY:
                return frozenset({DeploymentTarget.RUN_PARTS})
            case DeploymentStrategy.CRON_D_FILE:
                return frozenset({DeploymentTarget.CRON_D})
            case _:
                return frozenset({DeploymentTarget.USER_CRONTAB, DeploymentTarget.SYSTEM_CRONTAB})

    @property
    def default_target(self) -> DeploymentTarget:
        """The target used when none is stated.

        The crontab strategies default to the user crontab so the zero-privilege path is
        what an operator gets without asking for it.
        """
        match self:
            case DeploymentStrategy.RUN_PARTS_DIRECTORY:
                return DeploymentTarget.RUN_PARTS
            case DeploymentStrategy.CRON_D_FILE:
                return DeploymentTarget.CRON_D
            case _:
                return DeploymentTarget.USER_CRONTAB

    @property
    def writes_a_file_per_task(self) -> bool:
        """Whether the artefact is a file whose name derives from the task's slug.

        Where it is, the filename must satisfy the rules of the directory it lands in, and
        that is checked when the specification is written rather than when it is deployed.
        """
        return self in {
            DeploymentStrategy.RUN_PARTS_DIRECTORY,
            DeploymentStrategy.CRON_D_FILE,
        }

    @property
    def carries_its_own_schedule(self) -> bool:
        """Whether the artefact states when the work runs.

        A run-parts artefact does not: the directory decides. Everything else does, which
        is why only run-parts deployment requires a classification and forbids a schedule
        of its own.
        """
        return self is not DeploymentStrategy.RUN_PARTS_DIRECTORY


class PeriodicClassification(StrEnum):
    """A coarse "how often" that stands in for a schedule.

    Classification is how an operator says *"this is just a daily job"* without choosing a
    layout. It supplies a default strategy and target, which is what makes the most common
    shape of operational work require no deployment decision at all.
    """

    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"

    @property
    def run_parts_directory_name(self) -> str:
        """The conventional run-parts directory for this classification.

        The name only; the absolute path is the adapter's business, because it varies by
        distribution and must be configurable.
        """
        return f"cron.{self.value}"


DEFAULT_UNCLASSIFIED_STRATEGY = DeploymentStrategy.CRONTAB_BLOCK_PER_TASK
"""What a task with no classification and no explicit strategy gets.

Chosen because it needs no privilege, works on a single-user install, and isolates each
task's changes from every other task's.
"""


@dataclass(frozen=True, slots=True)
class DeploymentSpecification:
    """How one capability's activation intent is to be deployed.

    Part of the revision, and therefore versioned and frozen at publication: an operator
    reviewing what changed sees a move from a user crontab to ``/etc/cron.d`` as a
    reviewable change, which it is.

    Attributes:
        strategy: The shape of the artefact.
        target: Where it is written.
        classification: The coarse cadence, when the strategy takes its schedule from one.
        execution_user: The user the work runs as, where the target can express it.
    """

    strategy: DeploymentStrategy = DEFAULT_UNCLASSIFIED_STRATEGY
    target: DeploymentTarget = DeploymentTarget.USER_CRONTAB
    classification: PeriodicClassification | None = None
    execution_user: str | None = None

    def __post_init__(self) -> None:
        """Validate the specification.

        Every check here exists so that an impossible deployment is refused while it is
        still cheap to fix, rather than producing an artefact that silently does something
        other than what was asked.

        Raises:
            ValidationError: If the combination cannot be deployed as described.
        """
        if self.target not in self.strategy.permitted_targets:
            raise ValidationError(
                f"A '{self.strategy}' artefact cannot be written to '{self.target}'. "
                f"Permitted targets for this strategy: "
                f"{', '.join(sorted(str(t) for t in self.strategy.permitted_targets))}.",
                details={"strategy": str(self.strategy), "target": str(self.target)},
            )

        if self.strategy is DeploymentStrategy.RUN_PARTS_DIRECTORY and self.classification is None:
            raise ValidationError(
                "Run-parts deployment requires a classification, because the directory "
                "supplies the schedule. Classify the task as hourly, daily, weekly, or "
                "monthly, or choose a strategy that carries its own schedule.",
                details={"strategy": str(self.strategy)},
            )

        if self.execution_user is not None:
            self._validate_execution_user()

    def _validate_execution_user(self) -> None:
        """Validate the execution user and that the target can express it.

        Raises:
            ValidationError: If the name is unusable or the target cannot carry it.
        """
        user = self.execution_user or ""
        if not user.strip():
            raise ValidationError(
                "An execution user must be a name, not blank. Omit it to run as the "
                "target's default user."
            )
        if len(user) > MAX_EXECUTION_USER_LENGTH:
            raise ValidationError(
                "Execution user name is too long.",
                details={"maximum": MAX_EXECUTION_USER_LENGTH},
            )
        if not user.replace("-", "").replace("_", "").isalnum() or user[0].isdigit():
            raise ValidationError(
                "An execution user name may contain only letters, digits, hyphens, and "
                "underscores, and may not start with a digit.",
                details={"execution_user": user},
            )
        if not self.target.expresses_execution_user:
            raise ValidationError(
                f"A '{self.target}' artefact cannot name the user the work runs as, so "
                f"asking it to run as '{user}' would silently run it as somebody else. "
                f"Use the system crontab or /etc/cron.d, or omit the execution user.",
                details={"target": str(self.target), "execution_user": user},
            )

    @property
    def requires_privilege(self) -> bool:
        """Whether deploying this specification needs more than the invoking user's rights."""
        return self.target.requires_privilege

    def assert_deployable_for(self, slug: Slug) -> None:
        """Raise unless this specification can produce a valid artefact for ``slug``.

        Both run-parts and ``cron.d`` silently ignore files whose names they do not like —
        run-parts rejects a name containing a dot, ``cron.d`` skips unexpected characters.
        A file that is present but ignored is the worst outcome available, because
        everything looks deployed and nothing runs. So the name is checked here.

        The current slug rules already guarantee a usable name; this asserts the guarantee
        rather than assuming it will survive a future change to those rules.

        Args:
            slug: The task's slug, which becomes the filename.

        Raises:
            ValidationError: If the slug cannot produce a valid filename.
        """
        if not self.strategy.writes_a_file_per_task:
            return

        name = slug.to_primitive()
        if not name.replace("-", "").replace("_", "").isalnum():
            raise ValidationError(
                f"The slug '{name}' cannot be used as a filename in {self.target}: cron "
                "would ignore the file, so the task would appear deployed and never run. "
                "Only letters, digits, hyphens, and underscores are safe here.",
                details={"slug": name, "target": str(self.target)},
            )

    def artefact_name(self, slug: Slug) -> str:
        """Return the artefact's filename for a task.

        Args:
            slug: The task's slug.

        Returns:
            The filename.

        Raises:
            ValidationError: If this strategy does not write a file per task, or the slug
                cannot produce a valid filename.
        """
        if not self.strategy.writes_a_file_per_task:
            raise ValidationError(
                f"A '{self.strategy}' deployment writes a region inside a crontab, not a "
                "file of its own, so it has no filename.",
                details={"strategy": str(self.strategy)},
            )
        self.assert_deployable_for(slug)
        return slug.to_primitive()

    @classmethod
    def for_classification(
        cls,
        classification: PeriodicClassification | None,
        *,
        execution_user: str | None = None,
    ) -> Self:
        """Return the default deployment for a classification.

        This is the path most tasks take. "Run this daily" becomes a file in
        ``/etc/cron.daily`` — the place the operating system already provides for exactly
        that — without the operator choosing a layout.

        Args:
            classification: The coarse cadence, or ``None`` for an unclassified task.
            execution_user: The user the work should run as, if the resulting target can
                express it.

        Returns:
            The default specification.

        Raises:
            ValidationError: If an execution user is given that the default target cannot
                express. That is not a defect to route around: the operator has asked for
                something the default layout cannot do, and must choose a layout that can.
        """
        if classification is None:
            strategy = DEFAULT_UNCLASSIFIED_STRATEGY
        else:
            strategy = DeploymentStrategy.RUN_PARTS_DIRECTORY

        return cls(
            strategy=strategy,
            target=strategy.default_target,
            classification=classification,
            execution_user=execution_user,
        )

    def with_changes(self, **changes: Any) -> Self:
        """Return a copy with changes applied and revalidated.

        Args:
            **changes: Fields to replace.

        Returns:
            The updated specification.

        Raises:
            ValidationError: If the result is not deployable.
        """
        return replace(self, **changes)

    def to_primitive(self) -> dict[str, Any]:
        """Return a stable representation."""
        return {
            "strategy": str(self.strategy),
            "target": str(self.target),
            "classification": str(self.classification) if self.classification else None,
            "execution_user": self.execution_user,
        }

    @classmethod
    def from_primitive(cls, data: dict[str, Any]) -> Self:
        """Rebuild from a stored representation.

        Args:
            data: A previously produced mapping.

        Returns:
            The specification.

        Raises:
            ValidationError: If the mapping is malformed or not deployable.
        """
        if not isinstance(data, dict):
            raise ValidationError("A deployment specification must be a mapping.")

        classification = data.get("classification")
        strategy = DeploymentStrategy(data.get("strategy", DEFAULT_UNCLASSIFIED_STRATEGY))
        return cls(
            strategy=strategy,
            target=DeploymentTarget(data.get("target", strategy.default_target)),
            classification=PeriodicClassification(classification) if classification else None,
            execution_user=data.get("execution_user"),
        )
