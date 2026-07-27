"""The cron scheduler management adapter.

Implements :class:`~taskcontrol.ports.scheduler_management.SchedulerManagement` for all
four deployment strategies of ADR 0026, over whichever stores it is given. It is the only
module that knows both what an operator asked for and where it physically goes.

The apply loop is the part worth reading carefully. It snapshots every store it is about to
touch, writes, reads back, compares, and restores everything on the first mismatch. A
partially applied deployment is the single outcome that must never be left behind, because
it is the one an operator cannot reason about: some jobs are new, some are old, and nothing
on the host says which.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from taskcontrol.adapters.schedulers.cron.rendering import (
    AmbiguousManagedContentError,
    ManagedEntry,
    find_block_members,
    find_managed_regions,
    remove_block_member,
    remove_region,
    render_artefact,
    replace_region,
    upsert_block_member,
)
from taskcontrol.adapters.schedulers.cron.stores import CrontabText, ManagedDirectory
from taskcontrol.common.errors import ConfigurationError
from taskcontrol.domain.common.identifiers import TaskId
from taskcontrol.domain.deployment.strategies import (
    DeploymentStrategy,
    DeploymentTarget,
    PeriodicClassification,
)
from taskcontrol.ports.scheduler_management import (
    ApplyResult,
    DeploymentChange,
    DeploymentPlan,
    DesiredArtefact,
    DriftKind,
    PlanEntry,
    SchedulerCapabilities,
    VerificationFinding,
    VerificationReport,
)

SCHEDULER_NAME = "cron"


@dataclass(frozen=True, slots=True)
class CronLayout:
    """Which stores back which targets on this host.

    Every field is optional because hosts differ and privilege differs. A target with no
    store configured is simply not writable here, which is reported rather than discovered
    halfway through an apply.

    Attributes:
        user_crontab: The invoking user's crontab.
        system_crontab: ``/etc/crontab``.
        cron_d: ``/etc/cron.d``.
        run_parts: One directory per classification, such as ``/etc/cron.daily``.
    """

    user_crontab: CrontabText | None = None
    system_crontab: CrontabText | None = None
    cron_d: ManagedDirectory | None = None
    run_parts: Mapping[PeriodicClassification, ManagedDirectory] | None = None

    def crontab_for(self, target: DeploymentTarget) -> CrontabText | None:
        """Return the crontab backing a target, if one is configured."""
        if target is DeploymentTarget.USER_CRONTAB:
            return self.user_crontab
        if target is DeploymentTarget.SYSTEM_CRONTAB:
            return self.system_crontab
        return None

    def directory_for(
        self, target: DeploymentTarget, classification: PeriodicClassification | None
    ) -> ManagedDirectory | None:
        """Return the directory backing a target, if one is configured."""
        if target is DeploymentTarget.CRON_D:
            return self.cron_d
        if target is DeploymentTarget.RUN_PARTS and classification is not None:
            return (self.run_parts or {}).get(classification)
        return None


class CronSchedulerManagement:
    """Manages cron artefacts across every deployment strategy.

    Args:
        layout: Which stores back which targets on this host.
    """

    def __init__(self, layout: CronLayout) -> None:
        """Store the layout."""
        self._layout = layout

    # -- capabilities ---------------------------------------------------------------

    def capabilities(self) -> SchedulerCapabilities:
        """Report which targets this process can write to right now.

        Reported rather than assumed. Writing to ``/etc/cron.d`` needs privilege this
        process may not have, and saying so up front is better than failing halfway
        through an apply.
        """
        writable: set[str] = set()
        unavailable: list[str] = []

        for target in DeploymentTarget:
            store = self._store_for_target(target)
            if store is None:
                unavailable.append(f"{target} (not configured on this host)")
            elif store.is_writable:
                writable.add(str(target))
            else:
                unavailable.append(f"{target} (not writable by this process)")

        return SchedulerCapabilities(
            scheduler=SCHEDULER_NAME,
            writable_targets=frozenset(writable),
            detail="; ".join(unavailable),
        )

    def _store_for_target(self, target: DeploymentTarget) -> CrontabText | ManagedDirectory | None:
        """Return any store backing a target, for capability reporting only.

        Run-parts has one store per classification, so the first configured one stands for
        the target as a whole.
        """
        crontab = self._layout.crontab_for(target)
        if crontab is not None:
            return crontab
        if target is DeploymentTarget.CRON_D:
            return self._layout.cron_d
        if target is DeploymentTarget.RUN_PARTS:
            directories = self._layout.run_parts or {}
            return next(iter(directories.values()), None)
        return None

    # -- planning -------------------------------------------------------------------

    def plan(self, desired: Sequence[DesiredArtefact]) -> DeploymentPlan:
        """Compute what applying ``desired`` would change.

        ``desired`` is the complete managed estate, not a diff: anything managed on the
        host and absent from it is planned for removal.

        Raises:
            AmbiguousManagedContentError: If managed identity on the host cannot be
                resolved. A plan computed from an ambiguous host proposes wrong changes.
            ConfigurationError: If an artefact names a target with no store here.
        """
        entries: list[PlanEntry] = [self._plan_one(artefact) for artefact in desired]
        entries.extend(self._plan_removals({artefact.slug for artefact in desired}))
        return DeploymentPlan(entries=tuple(entries))

    def _plan_one(self, artefact: DesiredArtefact) -> PlanEntry:
        """Plan one artefact."""
        rendered = render_artefact(artefact)
        current = self._current_content(artefact)
        target_description = self._describe(artefact)

        if not current:
            return PlanEntry(
                task_id=artefact.task_id,
                slug=artefact.slug,
                change=DeploymentChange.CREATE,
                target_description=target_description,
                after=rendered,
                detail="No managed artefact exists for this capability yet.",
                artefact=artefact,
            )
        if current == rendered:
            return PlanEntry(
                task_id=artefact.task_id,
                slug=artefact.slug,
                change=DeploymentChange.UNCHANGED,
                target_description=target_description,
                before=current,
                after=rendered,
                artefact=artefact,
            )
        return PlanEntry(
            task_id=artefact.task_id,
            slug=artefact.slug,
            change=DeploymentChange.UPDATE,
            target_description=target_description,
            before=current,
            after=rendered,
            detail="The deployed artefact differs from the published revision.",
            artefact=artefact,
        )

    def _plan_removals(self, desired_slugs: set[str]) -> list[PlanEntry]:
        """Plan removal of every managed artefact not in ``desired_slugs``."""
        entries: list[PlanEntry] = []

        for crontab in self._configured_crontabs():
            content = crontab.read()
            managed: list[ManagedEntry] = [
                *find_managed_regions(content),
                *find_block_members(content),
            ]
            for held in managed:
                if held.slug not in desired_slugs:
                    entries.append(
                        PlanEntry(
                            task_id=TaskId.from_primitive(held.task_id),
                            slug=held.slug,
                            change=DeploymentChange.REMOVE,
                            target_description=crontab.description,
                            before=held.text,
                            detail="Managed here, but no longer part of the deployed estate.",
                        )
                    )

        for directory in self._configured_directories():
            for name in directory.names():
                if name in desired_slugs:
                    continue
                regions = find_managed_regions(directory.read(name))
                if regions:
                    entries.append(
                        PlanEntry(
                            task_id=TaskId.from_primitive(regions[0].task_id),
                            slug=regions[0].slug,
                            change=DeploymentChange.REMOVE,
                            target_description=f"{directory.description}/{name}",
                            before=directory.read(name),
                            detail="Managed here, but no longer part of the deployed estate.",
                        )
                    )

        return entries

    # -- applying -------------------------------------------------------------------

    def apply(self, plan: DeploymentPlan) -> ApplyResult:
        """Apply a plan, verifying each write and rolling back on any failure.

        Each entry is written and then read back and compared. Writing successfully is not
        evidence that the right thing is there: a file can land where cron ignores it, and
        a crontab command can succeed against a different user's table than intended.

        Returns:
            What was applied, and whether a rollback occurred. A rollback is reported
            rather than raised, because "nothing changed, and here is why" is a complete
            and useful answer.
        """
        snapshot = _Snapshot()
        applied: list[PlanEntry] = []

        for entry in plan.entries_changing():
            try:
                if entry.change is DeploymentChange.REMOVE:
                    self._apply_removal(entry, snapshot)
                else:
                    self._apply_write(entry, snapshot)
            except Exception as error:  # noqa: BLE001 - any failure means roll back
                return self._roll_back(snapshot, entry, error)
            applied.append(entry)

        return ApplyResult(applied=tuple(applied))

    def _apply_write(self, entry: PlanEntry, snapshot: _Snapshot) -> None:
        """Write one artefact and verify it by reading it back.

        Raises:
            ConfigurationError: If the entry carries no artefact to deploy.
            _VerificationFailedError: If the read-back does not match what was written.
        """
        artefact = entry.artefact
        if artefact is None:
            raise ConfigurationError(
                "A create or update entry must carry the artefact it deploys.",
                details={"slug": entry.slug},
            )

        if artefact.deployment.strategy.writes_a_file_per_task:
            directory = self._directory_for(artefact)
            snapshot.capture_file(directory, artefact.slug, directory.read(artefact.slug))
            directory.write(
                artefact.slug,
                entry.after,
                executable=is_run_parts(artefact.deployment.strategy),
            )
            written = directory.read(artefact.slug)
        else:
            crontab = self._crontab_for(artefact)
            original = crontab.read()
            snapshot.capture_crontab(crontab, original)
            if _is_single_block(artefact):
                crontab.write(upsert_block_member(original, artefact.slug, entry.after))
            else:
                crontab.write(replace_region(original, artefact.slug, entry.after))
            written = self._current_content(artefact)

        if written.strip() != entry.after.strip():
            raise _VerificationFailedError(
                f"After writing '{artefact.slug}' to {entry.target_description}, reading "
                "it back produced something different. The write did not take effect "
                "where TaskControl expected it to."
            )

    def _apply_removal(self, entry: PlanEntry, snapshot: _Snapshot) -> None:
        """Remove one managed artefact, wherever on the host it currently is.

        The location is rediscovered now rather than trusted from planning time, because
        the host may have changed in between and removal must never act on a stale idea of
        where something lives.

        Raises:
            _VerificationFailedError: If the artefact is still present after removal.
        """
        for crontab in self._configured_crontabs():
            original = crontab.read()
            # Both shapes are checked. A capability can only be in one of them at a time,
            # but which one is a property of its current deployment rather than of what the
            # caller believes, and removal must act on what is actually there.
            in_region = any(r.slug == entry.slug for r in find_managed_regions(original))
            in_block = any(m.slug == entry.slug for m in find_block_members(original))
            if not in_region and not in_block:
                continue

            snapshot.capture_crontab(crontab, original)
            updated = remove_region(original, entry.slug) if in_region else original
            crontab.write(remove_block_member(updated, entry.slug) if in_block else updated)

            after = crontab.read()
            still_there = any(r.slug == entry.slug for r in find_managed_regions(after)) or any(
                m.slug == entry.slug for m in find_block_members(after)
            )
            if still_there:
                raise _VerificationFailedError(
                    f"'{entry.slug}' is still present in {crontab.description} after removing it."
                )

        for directory in self._configured_directories():
            content = directory.read(entry.slug)
            if not content or not find_managed_regions(content):
                continue
            snapshot.capture_file(directory, entry.slug, content)
            directory.remove(entry.slug)
            if directory.read(entry.slug):
                raise _VerificationFailedError(
                    f"'{entry.slug}' is still present in {directory.description} after removing it."
                )

    def _roll_back(self, snapshot: _Snapshot, entry: PlanEntry, error: Exception) -> ApplyResult:
        """Restore everything touched and report the failure.

        A rollback that itself fails is the worst case available, and it is reported as
        such rather than hidden: the operator must know the host is in a state TaskControl
        could not restore.
        """
        try:
            snapshot.restore()
        except Exception as rollback_error:  # noqa: BLE001 - reported, never swallowed
            return ApplyResult(
                rolled_back=False,
                failure=(
                    f"Applying failed on '{entry.slug}' ({error}), and rolling back also "
                    f"failed ({rollback_error}). The host may be partially deployed. "
                    "Run verify before doing anything else."
                ),
            )

        return ApplyResult(
            rolled_back=True,
            failure=f"Applying failed on '{entry.slug}': {error}. Nothing was changed.",
        )

    def verify(self, desired: Sequence[DesiredArtefact]) -> VerificationReport:
        """Read the host back and report how it differs from what was published."""
        findings: list[VerificationFinding] = []
        checked = 0
        desired_slugs = {artefact.slug for artefact in desired}

        for artefact in desired:
            checked += 1
            expected = render_artefact(artefact)
            try:
                current = self._current_content(artefact)
            except AmbiguousManagedContentError as error:
                findings.append(
                    VerificationFinding(
                        kind=DriftKind.AMBIGUOUS,
                        target_description=self._describe(artefact),
                        detail=str(error),
                        task_id=artefact.task_id,
                    )
                )
                continue

            if not current:
                findings.append(
                    VerificationFinding(
                        kind=DriftKind.MISSING,
                        target_description=self._describe(artefact),
                        detail="Nothing managed is deployed for this capability.",
                        task_id=artefact.task_id,
                    )
                )
            elif current != expected:
                findings.append(
                    VerificationFinding(
                        kind=DriftKind.MODIFIED,
                        target_description=self._describe(artefact),
                        detail=(
                            "The deployed artefact differs from the published revision. "
                            "Somebody edited it by hand, or it was deployed from a "
                            "different revision."
                        ),
                        task_id=artefact.task_id,
                    )
                )

        findings.extend(self._find_unexpected(desired_slugs))
        return VerificationReport(findings=tuple(findings), artefacts_checked=checked)

    def _find_unexpected(self, desired_slugs: set[str]) -> list[VerificationFinding]:
        """Find managed artefacts belonging to nothing currently deployed."""
        findings: list[VerificationFinding] = []

        for crontab in self._configured_crontabs():
            content = crontab.read()
            held_here: list[ManagedEntry] = [
                *find_managed_regions(content),
                *find_block_members(content),
            ]
            for held in held_here:
                if held.slug not in desired_slugs:
                    findings.append(
                        VerificationFinding(
                            kind=DriftKind.UNEXPECTED,
                            target_description=crontab.description,
                            detail=f"A managed entry for '{held.slug}' is deployed here.",
                            task_id=TaskId.from_primitive(held.task_id),
                        )
                    )

        for directory in self._configured_directories():
            for name in directory.names():
                if name in desired_slugs:
                    continue
                regions = find_managed_regions(directory.read(name))
                if regions:
                    findings.append(
                        VerificationFinding(
                            kind=DriftKind.UNEXPECTED,
                            target_description=f"{directory.description}/{name}",
                            detail=f"A managed artefact for '{regions[0].slug}' is deployed here.",
                            task_id=TaskId.from_primitive(regions[0].task_id),
                        )
                    )

        return findings

    def remove(self, task_ids: Sequence[TaskId]) -> ApplyResult:
        """Remove managed artefacts by identity.

        Removal is by managed identity alone. Content TaskControl did not write is never
        removed, however much it resembles something it would have written.

        Args:
            task_ids: The capabilities to undeploy.

        Returns:
            What was removed. Removing something already absent succeeds quietly.
        """
        wanted = {str(task_id) for task_id in task_ids}
        entries = [
            entry
            for entry in self._plan_removals(desired_slugs=set())
            if str(entry.task_id) in wanted
        ]
        return self.apply(DeploymentPlan(entries=tuple(entries)))

    # -- reading the host -----------------------------------------------------------

    def _current_content(self, artefact: DesiredArtefact) -> str:
        """Return what is currently deployed for an artefact, empty when nothing is.

        Raises:
            ConfigurationError: If the artefact's target has no store here.
            AmbiguousManagedContentError: If managed identity cannot be resolved.
        """
        if artefact.deployment.strategy.writes_a_file_per_task:
            directory = self._directory_for(artefact)
            content = directory.read(artefact.slug)
            if not content:
                return ""
            # A file with the right name but no marker was written by somebody else. It is
            # not ours to compare against, and it is certainly not ours to overwrite.
            regions = find_managed_regions(content)
            if not regions:
                raise AmbiguousManagedContentError(
                    f"{directory.description}/{artefact.slug} exists but carries no "
                    "TaskControl marker, so it was written by somebody else. TaskControl "
                    "will not overwrite it. Rename the task, or remove the file by hand.",
                    details={"path": f"{directory.description}/{artefact.slug}"},
                )
            self._assert_same_capability(artefact, regions[0].task_id, self._describe(artefact))
            return content

        crontab = self._crontab_for(artefact)

        if _is_single_block(artefact):
            member = next(
                (m for m in find_block_members(crontab.read()) if m.slug == artefact.slug), None
            )
            if member is None:
                return ""
            self._assert_same_capability(artefact, member.task_id, crontab.description)
            return member.text

        region = next(
            (r for r in find_managed_regions(crontab.read()) if r.slug == artefact.slug), None
        )
        if region is None:
            return ""
        self._assert_same_capability(artefact, region.task_id, crontab.description)
        return region.text

    def _assert_same_capability(
        self, artefact: DesiredArtefact, deployed_task_id: str, where: str
    ) -> None:
        """Raise if a deployed artefact carries a different capability under the same name.

        Slug collision between two capabilities is the one identity failure that looks
        entirely normal from the outside: the artefact is well-formed, correctly marked,
        and about to be silently replaced by somebody else's work.

        Raises:
            AmbiguousManagedContentError: If the deployed identity differs.
        """
        if deployed_task_id == str(artefact.task_id):
            return
        raise AmbiguousManagedContentError(
            f"'{artefact.slug}' is already deployed to {where} for a different capability. "
            "Overwriting it would silently replace that capability's schedule with this "
            "one. Two capabilities cannot share a slug.",
            details={
                "slug": artefact.slug,
                "deployed_task_id": deployed_task_id,
                "requested_task_id": str(artefact.task_id),
            },
        )

    def _describe(self, artefact: DesiredArtefact) -> str:
        """Describe where an artefact lives, for a plan or a finding."""
        if artefact.deployment.strategy.writes_a_file_per_task:
            return f"{self._directory_for(artefact).description}/{artefact.slug}"
        return self._crontab_for(artefact).description

    def _crontab_for(self, artefact: DesiredArtefact) -> CrontabText:
        """Return the crontab an artefact belongs in.

        Raises:
            ConfigurationError: If that target is not configured on this host.
        """
        crontab = self._layout.crontab_for(artefact.deployment.target)
        if crontab is None:
            raise ConfigurationError(
                f"This capability deploys to '{artefact.deployment.target}', which is not "
                "configured on this host.",
                details={"target": str(artefact.deployment.target), "slug": artefact.slug},
            )
        return crontab

    def _directory_for(self, artefact: DesiredArtefact) -> ManagedDirectory:
        """Return the directory an artefact belongs in.

        Raises:
            ConfigurationError: If that target, or that classification's directory, is not
                configured on this host.
        """
        directory = self._layout.directory_for(
            artefact.deployment.target, artefact.deployment.classification
        )
        if directory is None:
            classification = artefact.deployment.classification
            where = f" for {classification} work" if classification else ""
            raise ConfigurationError(
                f"This capability deploys to '{artefact.deployment.target}'{where}, which "
                "is not configured on this host.",
                details={
                    "target": str(artefact.deployment.target),
                    "classification": str(classification) if classification else None,
                    "slug": artefact.slug,
                },
            )
        return directory

    def _configured_crontabs(self) -> tuple[CrontabText, ...]:
        """Return every configured crontab store."""
        return tuple(
            store
            for store in (self._layout.user_crontab, self._layout.system_crontab)
            if store is not None
        )

    def _configured_directories(self) -> tuple[ManagedDirectory, ...]:
        """Return every configured directory store."""
        directories = [self._layout.cron_d] if self._layout.cron_d else []
        directories.extend((self._layout.run_parts or {}).values())
        return tuple(directories)


class _VerificationFailedError(Exception):
    """Raised when reading an artefact back does not match what was just written.

    Internal to this adapter: it is caught by the apply loop and turned into a rollback,
    so it never escapes as an exception type callers must know about.
    """


class _Snapshot:
    """What every touched store held before an apply began.

    Only stores that are about to be written are captured, and each only once — the first
    capture is the pre-apply state, and a later write must not overwrite that record with
    an already-modified version.
    """

    def __init__(self) -> None:
        """Start with nothing captured."""
        self._crontabs: list[tuple[CrontabText, str]] = []
        self._files: list[tuple[ManagedDirectory, str, str]] = []

    def capture_crontab(self, crontab: CrontabText, content: str) -> None:
        """Record a crontab's content, if it has not been recorded already."""
        if not any(existing is crontab for existing, _ in self._crontabs):
            self._crontabs.append((crontab, content))

    def capture_file(self, directory: ManagedDirectory, name: str, content: str) -> None:
        """Record a file's content, if it has not been recorded already.

        An empty string records that the file was absent, which restores as a removal.
        """
        if not any(
            existing is directory and existing_name == name
            for existing, existing_name, _ in self._files
        ):
            self._files.append((directory, name, content))

    def restore(self) -> None:
        """Put every captured store back exactly as it was.

        Raises:
            Exception: If a store could not be restored. The caller reports this rather
                than swallowing it: a failed rollback leaves the host in a state nobody
                intended, and the operator has to know.
        """
        for crontab, content in reversed(self._crontabs):
            crontab.write(content)
        for directory, name, content in reversed(self._files):
            if content:
                directory.write(name, content, executable=_looks_executable(content))
            else:
                directory.remove(name)


def _looks_executable(content: str) -> bool:
    """Whether restored file content should be executable.

    A run-parts artefact is a script and must keep its executable bit; a ``cron.d`` file
    must not have one. The shebang is the honest signal, and it is the same signal cron
    itself relies on.
    """
    return content.startswith("#!")


def _is_single_block(artefact: DesiredArtefact) -> bool:
    """Whether this artefact lives inside the one shared managed block."""
    return artefact.deployment.strategy is DeploymentStrategy.CRONTAB_SINGLE_BLOCK


def is_run_parts(strategy: DeploymentStrategy) -> bool:
    """Whether a strategy deploys into a run-parts directory.

    Run-parts artefacts must be executable, which is the one difference in how a file is
    written rather than rendered.
    """
    return strategy is DeploymentStrategy.RUN_PARTS_DIRECTORY
