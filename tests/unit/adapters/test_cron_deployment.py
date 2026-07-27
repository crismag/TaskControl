"""Contract tests for cron deployment — the same suite for every strategy.

ADR 0026 accepted four strategies knowing the risk: one built well and three built
shallowly. The mitigation is this module. Every strategy is driven through the *same*
parametrised tests, so a guarantee that holds for a crontab block holds for a run-parts
script too, or the suite says so.

Nothing here touches a real crontab. Crontab-style targets are backed by a temporary file,
directories by a temporary directory, and the ``crontab`` command is never invoked.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from taskcontrol.adapters.schedulers.cron import (
    AmbiguousManagedContentError,
    CronLayout,
    CronSchedulerManagement,
    FileCrontab,
    FilesystemDirectory,
    render_artefact,
)
from taskcontrol.adapters.schedulers.cron.rendering import (
    BLOCK_BEGIN_MARKER,
    BLOCK_END_MARKER,
    find_block_members,
    find_managed_regions,
    render_block_member,
)
from taskcontrol.common.errors import ValidationError
from taskcontrol.domain.common.identifiers import TaskId
from taskcontrol.domain.deployment.strategies import (
    DeploymentSpecification,
    DeploymentStrategy,
    DeploymentTarget,
    PeriodicClassification,
)
from taskcontrol.ports.scheduler_management import (
    DeploymentChange,
    DeploymentPlan,
    DesiredArtefact,
    DriftKind,
)

UNMANAGED = """# my own entries, please leave them alone
0 4 * * *   /usr/local/bin/rotate-logs

MAILTO=ops@example.com
*/5 * * * * /usr/local/bin/probe   # trailing comment
"""

ALL_STRATEGIES = [
    DeploymentStrategy.CRONTAB_BLOCK_PER_TASK,
    DeploymentStrategy.CRONTAB_SINGLE_BLOCK,
    DeploymentStrategy.CRON_D_FILE,
    DeploymentStrategy.RUN_PARTS_DIRECTORY,
]


def specification_for(strategy: DeploymentStrategy) -> DeploymentSpecification:
    """Return a valid specification for a strategy."""
    if strategy is DeploymentStrategy.RUN_PARTS_DIRECTORY:
        return DeploymentSpecification(
            strategy=strategy,
            target=DeploymentTarget.RUN_PARTS,
            classification=PeriodicClassification.DAILY,
        )
    if strategy is DeploymentStrategy.CRON_D_FILE:
        return DeploymentSpecification(
            strategy=strategy,
            target=DeploymentTarget.CRON_D,
            execution_user="settlement",
        )
    return DeploymentSpecification(strategy=strategy, target=DeploymentTarget.USER_CRONTAB)


def artefact_for(
    strategy: DeploymentStrategy,
    *,
    slug: str = "nightly-backup",
    command: str = "/usr/bin/taskctl run nightly-backup",
    digest: str = "sha256:aaaa",
    task_id: TaskId | None = None,
) -> DesiredArtefact:
    """Return a deployable artefact for a strategy.

    A capability keeps its identity across revisions, so ``task_id`` is passed explicitly
    wherever a test deploys the same capability twice.
    """
    specification = specification_for(strategy)
    return DesiredArtefact(
        task_id=task_id or TaskId.generate(),
        slug=slug,
        deployment=specification,
        command=command,
        content_digest=digest,
        schedule=None if strategy is DeploymentStrategy.RUN_PARTS_DIRECTORY else "0 2 * * *",
        description="Back up the trading database.",
    )


@pytest.fixture
def host(tmp_path: Path) -> tuple[CronSchedulerManagement, Path, Path, Path]:
    """Return a manager over temporary stores, plus the paths behind them."""
    crontab_path = tmp_path / "user.crontab"
    crontab_path.write_text(UNMANAGED, encoding="utf-8")
    cron_d = tmp_path / "cron.d"
    cron_d.mkdir()
    daily = tmp_path / "cron.daily"
    daily.mkdir()

    layout = CronLayout(
        user_crontab=FileCrontab(crontab_path),
        cron_d=FilesystemDirectory(cron_d),
        run_parts={PeriodicClassification.DAILY: FilesystemDirectory(daily)},
    )
    return CronSchedulerManagement(layout), crontab_path, cron_d, daily


# -- rule 7: rendering is deterministic ----------------------------------------------


@pytest.mark.parametrize("strategy", ALL_STRATEGIES)
def test_rendering_is_byte_identical_every_time(strategy: DeploymentStrategy) -> None:
    """The same artefact renders identically, which is what makes verification possible."""
    artefact = artefact_for(strategy)
    assert render_artefact(artefact) == render_artefact(artefact)


@pytest.mark.parametrize("strategy", ALL_STRATEGIES)
def test_rendered_content_carries_task_and_digest(strategy: DeploymentStrategy) -> None:
    """Rule 2: managed artefacts name the task and the revision they came from."""
    artefact = artefact_for(strategy)
    rendered = render_artefact(artefact)
    assert artefact.slug in rendered
    assert artefact.content_digest in rendered
    assert str(artefact.task_id) in rendered


def test_a_description_cannot_escape_its_comment() -> None:
    """A multi-line description must not become a second cron directive."""
    artefact = DesiredArtefact(
        task_id=TaskId.generate(),
        slug="probe",
        deployment=specification_for(DeploymentStrategy.CRONTAB_BLOCK_PER_TASK),
        command="/bin/true",
        content_digest="sha256:bb",
        schedule="0 1 * * *",
        description="First line\n* * * * * /bin/rm -rf /",
    )
    rendered = render_artefact(artefact)
    directives = [line for line in rendered.splitlines() if not line.startswith("#")]
    assert directives == ["0 1 * * * /bin/true"]


# -- planning and applying -------------------------------------------------------------


@pytest.mark.parametrize("strategy", ALL_STRATEGIES)
def test_plan_then_apply_deploys_and_verifies(
    strategy: DeploymentStrategy, host: tuple[CronSchedulerManagement, Path, Path, Path]
) -> None:
    """The core loop: plan says create, apply succeeds, verify finds no drift."""
    manager, _, _, _ = host
    artefact = artefact_for(strategy)

    plan = manager.plan([artefact])
    assert plan.count_of(DeploymentChange.CREATE) == 1

    result = manager.apply(plan)
    assert result.succeeded, result.failure
    assert manager.verify([artefact]).matches


@pytest.mark.parametrize("strategy", ALL_STRATEGIES)
def test_reapplying_changes_nothing(
    strategy: DeploymentStrategy, host: tuple[CronSchedulerManagement, Path, Path, Path]
) -> None:
    """Idempotence. A second apply must be a no-op, not a rewrite."""
    manager, _, _, _ = host
    artefact = artefact_for(strategy)
    manager.apply(manager.plan([artefact]))

    second = manager.plan([artefact])
    assert second.is_empty
    assert second.count_of(DeploymentChange.UNCHANGED) == 1


@pytest.mark.parametrize("strategy", ALL_STRATEGIES)
def test_updating_a_revision_is_planned_as_an_update(
    strategy: DeploymentStrategy, host: tuple[CronSchedulerManagement, Path, Path, Path]
) -> None:
    """A new revision of the same capability updates in place rather than duplicating."""
    manager, _, _, _ = host
    original = artefact_for(strategy)
    manager.apply(manager.plan([original]))

    changed = artefact_for(
        strategy,
        command="/usr/bin/taskctl run nightly-backup --full",
        task_id=original.task_id,
    )
    plan = manager.plan([changed])
    assert plan.count_of(DeploymentChange.UPDATE) == 1

    assert manager.apply(plan).succeeded
    assert manager.verify([changed]).matches


@pytest.mark.parametrize("strategy", ALL_STRATEGIES)
def test_removal_leaves_nothing_behind(
    strategy: DeploymentStrategy, host: tuple[CronSchedulerManagement, Path, Path, Path]
) -> None:
    """Undeploying removes the artefact, and verify then reports it missing."""
    manager, _, _, _ = host
    artefact = artefact_for(strategy)
    manager.apply(manager.plan([artefact]))

    assert manager.remove([artefact.task_id]).succeeded

    report = manager.verify([artefact])
    assert [finding.kind for finding in report.findings] == [DriftKind.MISSING]


@pytest.mark.parametrize("strategy", ALL_STRATEGIES)
def test_an_artefact_absent_from_desired_is_planned_for_removal(
    strategy: DeploymentStrategy, host: tuple[CronSchedulerManagement, Path, Path, Path]
) -> None:
    """A plan is a statement about the whole estate, not a diff of what was passed in."""
    manager, _, _, _ = host
    manager.apply(manager.plan([artefact_for(strategy)]))

    plan = manager.plan([])
    assert plan.count_of(DeploymentChange.REMOVE) == 1


# -- rule 1: unmanaged content is never modified ---------------------------------------


def test_unmanaged_crontab_content_survives_byte_identically(
    host: tuple[CronSchedulerManagement, Path, Path, Path],
) -> None:
    """The rule the whole design rests on. Somebody else's crontab is not ours to tidy."""
    manager, crontab_path, _, _ = host
    artefact = artefact_for(DeploymentStrategy.CRONTAB_BLOCK_PER_TASK)

    manager.apply(manager.plan([artefact]))
    manager.apply(
        manager.plan(
            [
                artefact_for(
                    DeploymentStrategy.CRONTAB_BLOCK_PER_TASK,
                    command="/bin/true",
                    task_id=artefact.task_id,
                )
            ]
        )
    )
    manager.remove([artefact.task_id])

    assert crontab_path.read_text(encoding="utf-8") == UNMANAGED


def test_an_unmanaged_file_in_cron_d_is_never_touched(
    host: tuple[CronSchedulerManagement, Path, Path, Path],
) -> None:
    """A file somebody else wrote is left alone, even when it is named like ours."""
    manager, _, cron_d, _ = host
    foreign = cron_d / "nightly-backup"
    foreign.write_text("0 3 * * * root /opt/legacy/backup.sh\n", encoding="utf-8")

    with pytest.raises(AmbiguousManagedContentError):
        manager.plan([artefact_for(DeploymentStrategy.CRON_D_FILE)])

    assert foreign.read_text(encoding="utf-8") == "0 3 * * * root /opt/legacy/backup.sh\n"


# -- rule 5: fail closed on ambiguous identity -----------------------------------------


def test_two_regions_claiming_one_task_are_refused(
    host: tuple[CronSchedulerManagement, Path, Path, Path],
) -> None:
    """Rewriting either could leave the other running stale work, so neither is chosen."""
    manager, crontab_path, _, _ = host
    artefact = artefact_for(DeploymentStrategy.CRONTAB_BLOCK_PER_TASK)
    manager.apply(manager.plan([artefact]))

    doubled = crontab_path.read_text(encoding="utf-8")
    crontab_path.write_text(doubled + render_artefact(artefact), encoding="utf-8")

    with pytest.raises(AmbiguousManagedContentError):
        manager.plan([artefact])


def test_an_unterminated_region_is_refused(
    host: tuple[CronSchedulerManagement, Path, Path, Path],
) -> None:
    """A begin marker with no end means the file was truncated or hand-edited."""
    manager, crontab_path, _, _ = host
    artefact = artefact_for(DeploymentStrategy.CRONTAB_BLOCK_PER_TASK)
    manager.apply(manager.plan([artefact]))

    text = crontab_path.read_text(encoding="utf-8")
    crontab_path.write_text(
        "\n".join(line for line in text.splitlines() if "<<<" not in line) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(AmbiguousManagedContentError):
        manager.plan([artefact])


# -- drift ------------------------------------------------------------------------------


@pytest.mark.parametrize("strategy", ALL_STRATEGIES)
def test_a_hand_edited_artefact_is_reported_as_modified(
    strategy: DeploymentStrategy, host: tuple[CronSchedulerManagement, Path, Path, Path]
) -> None:
    """Finding hand-edited jobs is most of why verify exists."""
    manager, crontab_path, cron_d, daily = host
    artefact = artefact_for(strategy)
    manager.apply(manager.plan([artefact]))

    if strategy is DeploymentStrategy.CRON_D_FILE:
        edited = cron_d / artefact.slug
    elif strategy is DeploymentStrategy.RUN_PARTS_DIRECTORY:
        edited = daily / artefact.slug
    else:
        edited = crontab_path
    edited.write_text(
        edited.read_text(encoding="utf-8").replace("taskctl", "taskctl-old"), encoding="utf-8"
    )

    report = manager.verify([artefact])
    assert [finding.kind for finding in report.findings] == [DriftKind.MODIFIED]


def test_a_managed_artefact_for_nothing_deployed_is_unexpected(
    host: tuple[CronSchedulerManagement, Path, Path, Path],
) -> None:
    """Something we wrote, for a capability nobody deploys any more."""
    manager, _, _, _ = host
    manager.apply(manager.plan([artefact_for(DeploymentStrategy.CRON_D_FILE)]))

    report = manager.verify([])
    assert [finding.kind for finding in report.findings] == [DriftKind.UNEXPECTED]


# -- rule 6: rollback -------------------------------------------------------------------


def test_a_failed_apply_restores_the_host_exactly(
    host: tuple[CronSchedulerManagement, Path, Path, Path], tmp_path: Path
) -> None:
    """The one outcome that must never be left behind is a partial deployment."""
    manager, crontab_path, _, _ = host
    before = crontab_path.read_text(encoding="utf-8")

    good = artefact_for(DeploymentStrategy.CRONTAB_BLOCK_PER_TASK, slug="first")
    # Deploys to a run-parts classification with no directory configured for it, so
    # applying fails after the first entry has already been written.
    doomed = DesiredArtefact(
        task_id=TaskId.generate(),
        slug="second",
        deployment=DeploymentSpecification(
            strategy=DeploymentStrategy.RUN_PARTS_DIRECTORY,
            target=DeploymentTarget.RUN_PARTS,
            classification=PeriodicClassification.WEEKLY,
        ),
        command="/bin/true",
        content_digest="sha256:cc",
    )

    plan = DeploymentPlan(entries=(*manager.plan([good]).entries, _doomed_entry(doomed)))
    result = manager.apply(plan)

    assert not result.succeeded
    assert result.rolled_back
    assert crontab_path.read_text(encoding="utf-8") == before


def _doomed_entry(artefact: DesiredArtefact):
    """Build a create entry by hand for a target that is not configured."""
    from taskcontrol.ports.scheduler_management import PlanEntry

    return PlanEntry(
        task_id=artefact.task_id,
        slug=artefact.slug,
        change=DeploymentChange.CREATE,
        target_description="an unconfigured run-parts directory",
        after=render_artefact(artefact),
        artefact=artefact,
    )


# -- run-parts specifics ----------------------------------------------------------------


def test_a_run_parts_artefact_is_executable(
    host: tuple[CronSchedulerManagement, Path, Path, Path],
) -> None:
    """A run-parts script that is not executable is silently ignored by cron.

    Which looks exactly like a deployment that worked, and is the reason the mode is set
    explicitly rather than left to the umask.
    """
    manager, _, _, daily = host
    artefact = artefact_for(DeploymentStrategy.RUN_PARTS_DIRECTORY)
    manager.apply(manager.plan([artefact]))

    deployed = daily / artefact.slug
    assert deployed.stat().st_mode & 0o111


def test_a_cron_d_file_is_not_executable(
    host: tuple[CronSchedulerManagement, Path, Path, Path],
) -> None:
    """A cron.d file is data, not a script."""
    manager, _, cron_d, _ = host
    artefact = artefact_for(DeploymentStrategy.CRON_D_FILE)
    manager.apply(manager.plan([artefact]))

    assert not (cron_d / artefact.slug).stat().st_mode & 0o111


def test_a_run_parts_artefact_refuses_to_carry_a_schedule() -> None:
    """The directory supplies the cadence; a schedule here would be silently ignored."""
    artefact = DesiredArtefact(
        task_id=TaskId.generate(),
        slug="cleanup",
        deployment=specification_for(DeploymentStrategy.RUN_PARTS_DIRECTORY),
        command="/bin/true",
        content_digest="sha256:dd",
        schedule="0 2 * * *",
    )
    with pytest.raises(ValidationError, match="silently ignored"):
        render_artefact(artefact)


def test_a_crontab_strategy_requires_a_schedule() -> None:
    """The mirror image: a strategy that states when the work runs needs to be told."""
    artefact = DesiredArtefact(
        task_id=TaskId.generate(),
        slug="cleanup",
        deployment=specification_for(DeploymentStrategy.CRONTAB_BLOCK_PER_TASK),
        command="/bin/true",
        content_digest="sha256:ee",
    )
    with pytest.raises(ValidationError, match="needs a schedule"):
        render_artefact(artefact)


def test_only_cron_d_and_system_crontab_name_the_execution_user() -> None:
    """The whole point of cron.d: it can say who the work runs as."""
    rendered = render_artefact(artefact_for(DeploymentStrategy.CRON_D_FILE))
    assert "settlement" in rendered

    rendered = render_artefact(artefact_for(DeploymentStrategy.CRONTAB_BLOCK_PER_TASK))
    assert "settlement" not in rendered


def test_two_capabilities_cannot_share_a_slug(
    host: tuple[CronSchedulerManagement, Path, Path, Path],
) -> None:
    """The identity failure that looks entirely normal from the outside.

    A well-formed, correctly marked artefact, about to be silently replaced by somebody
    else's work because the two capabilities happen to share a name.
    """
    manager, _, _, _ = host
    manager.apply(manager.plan([artefact_for(DeploymentStrategy.CRONTAB_BLOCK_PER_TASK)]))

    impostor = artefact_for(DeploymentStrategy.CRONTAB_BLOCK_PER_TASK, command="/bin/false")
    with pytest.raises(AmbiguousManagedContentError, match="different capability"):
        manager.plan([impostor])


# -- plurality: the dimension the original contract tests were missing -------------------
#
# Every test above deploys one capability at a time, and with one capability a per-task
# block and a single shared block are genuinely indistinguishable. That is how
# `crontab_single_block` shipped as a synonym for `crontab_block_per_task` with a full
# green suite behind it. The missing dimension was never a strategy — it was plurality.


@pytest.mark.parametrize("strategy", ALL_STRATEGIES)
def test_three_capabilities_deploy_independently(
    strategy: DeploymentStrategy, host: tuple[CronSchedulerManagement, Path, Path, Path]
) -> None:
    """All three land, and each is separately identifiable afterwards."""
    manager, _, _, _ = host
    estate = [artefact_for(strategy, slug=slug) for slug in ("alpha", "beta", "gamma")]

    plan = manager.plan(estate)
    assert plan.count_of(DeploymentChange.CREATE) == 3

    assert manager.apply(plan).succeeded
    assert manager.verify(estate).matches


@pytest.mark.parametrize("strategy", ALL_STRATEGIES)
def test_updating_one_capability_leaves_its_neighbours_untouched(
    strategy: DeploymentStrategy, host: tuple[CronSchedulerManagement, Path, Path, Path]
) -> None:
    """The test that would have caught the single-block defect.

    Rewriting a shared block must preserve every entry that is not being changed. Getting
    this wrong silently unschedules other people's jobs — the worst available failure,
    because the artefact still looks correct for the capability you were working on.
    """
    manager, _, _, _ = host
    estate = [artefact_for(strategy, slug=slug) for slug in ("alpha", "beta", "gamma")]
    manager.apply(manager.plan(estate))

    changed = [
        artefact_for(strategy, slug="beta", command="/bin/true", task_id=estate[1].task_id)
        if artefact.slug == "beta"
        else artefact
        for artefact in estate
    ]

    plan = manager.plan(changed)
    assert plan.count_of(DeploymentChange.UPDATE) == 1
    assert plan.count_of(DeploymentChange.UNCHANGED) == 2

    assert manager.apply(plan).succeeded
    assert manager.verify(changed).matches


@pytest.mark.parametrize("strategy", ALL_STRATEGIES)
def test_removing_one_capability_leaves_its_neighbours_deployed(
    strategy: DeploymentStrategy, host: tuple[CronSchedulerManagement, Path, Path, Path]
) -> None:
    """Undeploying one job must not undeploy the others sharing its artefact."""
    manager, _, _, _ = host
    estate = [artefact_for(strategy, slug=slug) for slug in ("alpha", "beta", "gamma")]
    manager.apply(manager.plan(estate))

    assert manager.remove([estate[1].task_id]).succeeded

    survivors = [estate[0], estate[2]]
    assert manager.verify(survivors).matches
    assert [f.kind for f in manager.verify(estate).findings] == [DriftKind.MISSING]


@pytest.mark.parametrize("strategy", ALL_STRATEGIES)
def test_unmanaged_content_survives_a_whole_estate_lifecycle(
    strategy: DeploymentStrategy, host: tuple[CronSchedulerManagement, Path, Path, Path]
) -> None:
    """Deploy three, change one, remove all — somebody's crontab comes back byte-identical."""
    manager, crontab_path, _, _ = host
    estate = [artefact_for(strategy, slug=slug) for slug in ("alpha", "beta", "gamma")]

    manager.apply(manager.plan(estate))
    manager.apply(
        manager.plan(
            [
                artefact_for(strategy, slug="beta", command="/bin/true", task_id=estate[1].task_id)
                if artefact.slug == "beta"
                else artefact
                for artefact in estate
            ]
        )
    )
    manager.remove([artefact.task_id for artefact in estate])

    assert crontab_path.read_text(encoding="utf-8") == UNMANAGED


def test_the_single_block_holds_every_entry_in_one_region(
    host: tuple[CronSchedulerManagement, Path, Path, Path],
) -> None:
    """What distinguishes this strategy, asserted rather than assumed.

    One region, three entries. Previously this rendered as three separate regions, which
    is what `crontab_block_per_task` is for.
    """
    manager, crontab_path, _, _ = host
    estate = [
        artefact_for(DeploymentStrategy.CRONTAB_SINGLE_BLOCK, slug=slug)
        for slug in ("alpha", "beta", "gamma")
    ]
    manager.apply(manager.plan(estate))

    content = crontab_path.read_text(encoding="utf-8")

    assert content.count(BLOCK_BEGIN_MARKER) == 1
    assert content.count(BLOCK_END_MARKER) == 1
    assert [member.slug for member in find_block_members(content)] == ["alpha", "beta", "gamma"]


def test_per_task_blocks_are_separate_regions(
    host: tuple[CronSchedulerManagement, Path, Path, Path],
) -> None:
    """The other half of the distinction, so neither strategy can drift into the other."""
    manager, crontab_path, _, _ = host
    estate = [
        artefact_for(DeploymentStrategy.CRONTAB_BLOCK_PER_TASK, slug=slug)
        for slug in ("alpha", "beta", "gamma")
    ]
    manager.apply(manager.plan(estate))

    content = crontab_path.read_text(encoding="utf-8")

    assert len(find_managed_regions(content)) == 3
    assert BLOCK_BEGIN_MARKER not in content


def test_the_block_disappears_when_it_holds_nothing(
    host: tuple[CronSchedulerManagement, Path, Path, Path],
) -> None:
    """An empty pair of markers is litter in somebody's working crontab."""
    manager, crontab_path, _, _ = host
    artefact = artefact_for(DeploymentStrategy.CRONTAB_SINGLE_BLOCK, slug="alpha")
    manager.apply(manager.plan([artefact]))

    manager.remove([artefact.task_id])

    assert BLOCK_BEGIN_MARKER not in crontab_path.read_text(encoding="utf-8")


def test_two_entries_in_the_block_claiming_one_task_are_refused(
    host: tuple[CronSchedulerManagement, Path, Path, Path],
) -> None:
    """Rule 5 inside the block, not only around it."""
    manager, crontab_path, _, _ = host
    artefact = artefact_for(DeploymentStrategy.CRONTAB_SINGLE_BLOCK, slug="alpha")
    manager.apply(manager.plan([artefact]))

    content = crontab_path.read_text(encoding="utf-8")
    duplicated = content.replace(BLOCK_END_MARKER, render_block_member(artefact) + BLOCK_END_MARKER)
    crontab_path.write_text(duplicated, encoding="utf-8")

    with pytest.raises(AmbiguousManagedContentError, match="two entries"):
        manager.plan([artefact])
