"""CLI command definitions.

Commands translate arguments into calls and results into terminal output. They contain no
business rules; from Wave 6 they call application services.
"""

from __future__ import annotations

import json
from typing import Annotated

import typer

from taskcontrol import __version__
from taskcontrol.adapters.clock import SystemClock
from taskcontrol.application.runtime import RunRequest
from taskcontrol.cli.wiring import (
    build_activation_service,
    build_deployment_service,
    build_reconciliation_service,
    build_runtime,
)
from taskcontrol.domain.common.identifiers import OwnerId
from taskcontrol.domain.common.tracing import IdempotencyKey
from taskcontrol.domain.common.values import Slug
from taskcontrol.domain.execution.execution import Execution, TriggerSource
from taskcontrol.domain.scheduling.expressions import describe, parse_schedule_expression
from taskcontrol.infrastructure.database import (
    create_database_engine,
    database_url,
    ensure_data_directory,
)
from taskcontrol.infrastructure.migrations import current_revision, upgrade_to_head
from taskcontrol.infrastructure.server import run_api
from taskcontrol.infrastructure.settings import Settings
from taskcontrol.ports.scheduler_management import DeploymentChange, DeploymentPlan

app = typer.Typer(
    name="taskctl",
    help="Define, schedule, execute, observe, and govern automated work.",
    no_args_is_help=True,
    add_completion=True,
)


def _settings(ctx: typer.Context) -> Settings:
    """Return the settings the composition root placed on the context."""
    assert isinstance(ctx.obj, Settings)  # noqa: S101 — guaranteed by the composition root
    return ctx.obj


@app.command()
def version(
    ctx: typer.Context,
    as_json: Annotated[bool, typer.Option("--json", help="Emit machine-readable output.")] = False,
) -> None:
    """Print the installed TaskControl version."""
    if as_json:
        typer.echo(json.dumps({"version": __version__}))
    else:
        typer.echo(__version__)
    _ = ctx


@app.command()
def init(
    ctx: typer.Context,
    as_json: Annotated[bool, typer.Option("--json", help="Emit machine-readable output.")] = False,
) -> None:
    """Create the TaskControl database and bring it up to date.

    Safe to run repeatedly: applying no outstanding migrations is a successful no-op, so
    this is also the upgrade command.
    """
    settings = _settings(ctx)
    ensure_data_directory(settings)

    url = database_url(settings)
    engine = create_database_engine(url)
    try:
        before = current_revision(engine)
        after = upgrade_to_head(engine)
    finally:
        engine.dispose()

    payload = {
        "status": "ok",
        "backend": settings.database_backend,
        "data_dir": str(settings.data_dir),
        "previous_revision": before,
        "current_revision": after,
        "changed": before != after,
    }

    if as_json:
        typer.echo(json.dumps(payload))
        return

    if before == after:
        typer.echo(f"Database already up to date at revision {after}.")
    elif before is None:
        typer.echo(f"Database created at revision {after}.")
    else:
        typer.echo(f"Database upgraded from revision {before} to {after}.")
    typer.echo(f"Backend: {settings.database_backend}    Data directory: {settings.data_dir}")


@app.command()
def server(
    ctx: typer.Context,
    host: Annotated[
        str | None,
        typer.Option("--host", help="Override the configured bind interface."),
    ] = None,
    port: Annotated[
        int | None,
        typer.Option("--port", help="Override the configured bind port."),
    ] = None,
    reload: Annotated[
        bool, typer.Option("--reload", help="Restart on source change. Development only.")
    ] = False,
) -> None:
    """Start the TaskControl API server.

    Binds to TASKCONTROL_API_HOST and TASKCONTROL_API_PORT unless overridden, so the
    address reported by `taskctl health` is the address actually served.
    """
    settings = _settings(ctx)
    if host is not None or port is not None:
        settings = settings.model_copy(
            update={
                "api_host": host if host is not None else settings.api_host,
                "api_port": port if port is not None else settings.api_port,
            }
        )

    typer.echo(f"TaskControl API on http://{settings.api_host}:{settings.api_port}")
    run_api(settings, reload=reload)


@app.command()
def run(
    ctx: typer.Context,
    task: Annotated[str, typer.Argument(help="Task identifier or slug.")],
    as_json: Annotated[bool, typer.Option("--json", help="Emit machine-readable output.")] = False,
    idempotency_key: Annotated[
        str | None,
        typer.Option("--idempotency-key", help="Recognise a repeated request as the same run."),
    ] = None,
) -> None:
    """Run a task once and report what happened.

    Enters the same runtime the scheduler and the API use, so a manual run is classified
    exactly as a scheduled one would be.

    Exits 0 when the execution succeeded, 1 when it did not. A skipped or blocked
    execution is not a success — it is a recorded reason the work did not happen.
    """
    settings = _settings(ctx)
    runtime, resolve = build_runtime(settings)

    task_id = resolve(task)
    result = runtime.run(
        RunRequest(
            task_id=task_id,
            trigger_source=TriggerSource.MANUAL,
            idempotency_key=IdempotencyKey(idempotency_key) if idempotency_key else None,
        )
    )
    execution = result.execution

    if as_json:
        typer.echo(json.dumps(execution.to_primitive()))
    else:
        _print_execution(execution, duplicate=result.was_duplicate)

    raise typer.Exit(code=0 if result.succeeded else 1)


def _print_execution(execution: Execution, *, duplicate: bool = False) -> None:
    """Render an execution for a human."""
    if duplicate:
        typer.echo("This request matched an earlier one; showing the original execution.")

    typer.echo(f"Execution  {execution.execution_id}")
    typer.echo(f"Outcome    {execution.outcome}")
    if execution.reason_code:
        typer.echo(f"Reason     {execution.reason_code}")
    typer.echo(f"Attempts   {execution.attempt_count}")
    if execution.explanation:
        typer.echo(f"\n{execution.explanation}")

    for attempt in execution.attempts:
        typer.echo(f"\n--- attempt {attempt.attempt_number} ({attempt.duration}) ---")
        if attempt.result and attempt.result.exit_code is not None:
            typer.echo(f"exit code: {attempt.result.exit_code}")
        if attempt.stdout:
            typer.echo(f"stdout:\n{attempt.stdout.rstrip()}")
        if attempt.stderr:
            typer.echo(f"stderr:\n{attempt.stderr.rstrip()}")


@app.command()
def health(
    ctx: typer.Context,
    as_json: Annotated[bool, typer.Option("--json", help="Emit machine-readable output.")] = False,
) -> None:
    """Report local process health and effective configuration.

    Reports on this process only. It makes no network call, so it succeeds whether or not
    an API server is running.
    """
    settings = _settings(ctx)
    payload = {"status": "ok", "version": __version__, **settings.describe()}

    if as_json:
        typer.echo(json.dumps(payload))
        return

    width = max(len(key) for key in payload)
    for key, value in payload.items():
        typer.echo(f"{key.ljust(width)}  {value}")


schedule_app = typer.Typer(
    help="Manage the cron artefacts that activate recurring work.",
    no_args_is_help=True,
)
app.add_typer(schedule_app, name="schedule")


@schedule_app.command("plan")
def schedule_plan(
    ctx: typer.Context,
    as_json: Annotated[bool, typer.Option("--json", help="Emit machine-readable output.")] = False,
) -> None:
    """Show what deploying would change, without changing anything.

    Read this before running ``schedule apply``. A tool that rewrites the crontab of a
    production host without showing its work will not be trusted with the crontab of a
    production host.

    Exits 0 whether or not there is anything to do; a plan is information, not a verdict.
    """
    settings = _settings(ctx)
    plan = build_deployment_service(settings).plan()

    if as_json:
        typer.echo(json.dumps(_plan_payload(plan)))
        return

    _print_plan(plan)


@schedule_app.command("apply")
def schedule_apply(
    ctx: typer.Context,
    as_json: Annotated[bool, typer.Option("--json", help="Emit machine-readable output.")] = False,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Skip the confirmation prompt. Required for automation."),
    ] = False,
) -> None:
    """Deploy the current estate to this host's cron, verifying every write.

    Each artefact is written and then read back and compared. On any failure the host is
    restored to its previous state — a partially applied deployment is the one outcome an
    operator cannot reason about.

    Exits 0 when everything applied, 1 when anything failed.
    """
    settings = _settings(ctx)
    service = build_deployment_service(settings)
    plan = service.plan()

    if plan.is_empty:
        typer.echo("Nothing to do; this host already matches what is published.")
        raise typer.Exit(code=0)

    if not as_json and not yes:
        _print_plan(plan)
        typer.confirm("\nApply these changes?", abort=True)

    result = service.apply(plan)

    if as_json:
        typer.echo(
            json.dumps(
                {
                    "applied": [entry.slug for entry in result.applied],
                    "rolled_back": result.rolled_back,
                    "failure": result.failure,
                }
            )
        )
    elif result.succeeded:
        typer.echo(f"Applied {len(result.applied)} change(s) and verified each one.")
    else:
        typer.echo(result.failure, err=True)

    raise typer.Exit(code=0 if result.succeeded else 1)


@schedule_app.command("verify")
def schedule_verify(
    ctx: typer.Context,
    as_json: Annotated[bool, typer.Option("--json", help="Emit machine-readable output.")] = False,
) -> None:
    """Report how this host differs from what TaskControl published.

    This is how hand-edited crontabs are found. It only reads.

    Exits 0 when the host matches, 1 when it has drifted — so it can be run from
    monitoring.
    """
    settings = _settings(ctx)
    report = build_deployment_service(settings).verify()

    if as_json:
        typer.echo(
            json.dumps(
                {
                    "matches": report.matches,
                    "artefacts_checked": report.artefacts_checked,
                    "findings": [
                        {
                            "kind": str(finding.kind),
                            "where": finding.target_description,
                            "detail": finding.detail,
                        }
                        for finding in report.findings
                    ],
                }
            )
        )
    elif report.matches:
        typer.echo(f"All {report.artefacts_checked} deployed artefact(s) match what was published.")
    else:
        typer.echo(f"Checked {report.artefacts_checked} artefact(s); found drift:\n")
        for finding in report.findings:
            typer.echo(f"  {str(finding.kind).upper():<10} {finding.target_description}")
            if finding.detail:
                typer.echo(f"             {finding.detail}")

    raise typer.Exit(code=0 if report.matches else 1)


@schedule_app.command("status")
def schedule_status(
    ctx: typer.Context,
    as_json: Annotated[bool, typer.Option("--json", help="Emit machine-readable output.")] = False,
) -> None:
    """Report what TaskControl can deploy on this host, and where.

    Capability is reported rather than assumed: whether this process can write
    ``/etc/cron.d`` is a fact about the host, and finding out halfway through an apply is
    the wrong time.
    """
    settings = _settings(ctx)
    service = build_deployment_service(settings)
    artefacts = service.desired_artefacts()

    if as_json:
        typer.echo(
            json.dumps(
                {
                    "deployable": [
                        {
                            "slug": artefact.slug,
                            "strategy": str(artefact.deployment.strategy),
                            "target": str(artefact.deployment.target),
                            "schedule": artefact.schedule,
                        }
                        for artefact in artefacts
                    ]
                }
            )
        )
        return

    if not artefacts:
        typer.echo("No active capability has a published revision to deploy.")
        return

    width = max(len(artefact.slug) for artefact in artefacts)
    for artefact in artefacts:
        where = f"{artefact.deployment.strategy} -> {artefact.deployment.target}"
        when = artefact.schedule or f"{artefact.deployment.classification} (by classification)"
        typer.echo(f"{artefact.slug.ljust(width)}  {when:<24}  {where}")


def _plan_payload(plan: DeploymentPlan) -> dict[str, object]:
    """Render a plan as machine-readable data."""
    return {
        "changes": [
            {
                "slug": entry.slug,
                "change": str(entry.change),
                "where": entry.target_description,
                "detail": entry.detail,
            }
            for entry in plan.entries
        ],
        "is_empty": plan.is_empty,
    }


def _print_plan(plan: DeploymentPlan) -> None:
    """Render a plan for a human.

    Unchanged entries are summarised rather than listed. "These forty are already correct"
    is what makes a plan trustworthy; forty lines saying so is what makes it unread.
    """
    changing = plan.entries_changing()
    unchanged = plan.count_of(DeploymentChange.UNCHANGED)

    if not changing:
        typer.echo(f"Nothing to do. {unchanged} artefact(s) already match what is published.")
        return

    typer.echo(f"{len(changing)} change(s) to apply:\n")
    for entry in changing:
        typer.echo(f"  {str(entry.change).upper():<10} {entry.slug}")
        typer.echo(f"             {entry.target_description}")
        if entry.detail:
            typer.echo(f"             {entry.detail}")

    if unchanged:
        typer.echo(f"\n{unchanged} artefact(s) already correct and will not be touched.")


@app.command()
def activate(
    ctx: typer.Context,
    task: Annotated[str, typer.Argument(help="Slug of the capability to activate.")],
    as_json: Annotated[bool, typer.Option("--json", help="Emit machine-readable output.")] = False,
) -> None:
    """Run a capability from its locally installed revision. Invoked by cron.

    Unlike ``run``, this needs nothing from the control plane to decide what to do. It
    reads the installed manifest, and only then tries to reach the database — to *record*,
    never to *decide*. If it cannot, the capability's activation policy governs what
    happens next.

    Exit codes are distinct on purpose, because they call for different responses:

    * ``0`` — the work ran and succeeded.
    * ``1`` — the work ran and did not succeed.
    * ``75`` — TaskControl declined to run, because it could not record the run.
    * ``70`` — the work ran and TaskControl could not record that it ran. Investigate.
    """
    settings = _settings(ctx)
    result = build_activation_service(settings).activate(
        Slug(task), trigger_source=TriggerSource.SCHEDULE
    )

    if as_json:
        typer.echo(
            json.dumps(
                {
                    "outcome": str(result.outcome) if result.outcome else None,
                    "degraded": result.degraded,
                    "journalled": result.journalled,
                    "explanation": result.explanation,
                    "exit_code": result.exit_code,
                }
            )
        )
    elif result.explanation:
        typer.echo(result.explanation, err=result.exit_code != 0)

    raise typer.Exit(code=result.exit_code)


@app.command()
def reconcile(
    ctx: typer.Context,
    as_json: Annotated[bool, typer.Option("--json", help="Emit machine-readable output.")] = False,
) -> None:
    """Ingest locally journalled activations into the control plane.

    Safe to run repeatedly and safe to run on a schedule: ingestion keys on the execution
    identity the wrapper allocated before the work ran, so replaying a journal produces
    one record per run rather than one per attempt to reconcile.

    Exits 1 if the control plane is still unreachable, leaving the journal untouched.
    """
    settings = _settings(ctx)
    report = build_reconciliation_service(settings).reconcile()

    if as_json:
        typer.echo(
            json.dumps(
                {
                    "ingested": report.ingested,
                    "already_known": report.already_known,
                    "unreadable": report.unreadable,
                    "cleared": report.cleared,
                }
            )
        )
        return

    if not report.total_seen and not report.unreadable:
        typer.echo("Nothing to reconcile; no activations were journalled locally.")
        return

    typer.echo(
        f"Recorded {report.ingested} journalled activation(s); "
        f"{report.already_known} were already known."
    )
    if report.unreadable:
        typer.echo(
            f"{report.unreadable} journal line(s) could not be read and were lost. "
            "They were most likely truncated by a power failure.",
            err=True,
        )


@schedule_app.command("disable")
def schedule_disable(
    ctx: typer.Context,
    task: Annotated[str, typer.Argument(help="Slug of the capability to disable.")],
) -> None:
    """Stop a capability running, without deleting anything.

    Its definition, revisions, and history stay exactly where they are; only the artefact
    that causes cron to run it is removed. The removal happens now rather than at the next
    apply — an operator who disables a job at 01:50 expects it not to run at 02:00.
    """
    settings = _settings(ctx)
    result = build_deployment_service(settings).disable(
        Slug(task), actor=OwnerId.generate(), at=SystemClock().now()
    )

    if result.succeeded:
        typer.echo(f"'{task}' is disabled and its cron artefact has been removed.")
    else:
        typer.echo(result.failure, err=True)
    raise typer.Exit(code=0 if result.succeeded else 1)


@schedule_app.command("enable")
def schedule_enable(
    ctx: typer.Context,
    task: Annotated[str, typer.Argument(help="Slug of the capability to enable.")],
) -> None:
    """Return a disabled capability to service and redeploy its artefact."""
    settings = _settings(ctx)
    result = build_deployment_service(settings).enable(
        Slug(task), actor=OwnerId.generate(), at=SystemClock().now()
    )

    if result.succeeded:
        typer.echo(f"'{task}' is enabled and its cron artefact has been deployed.")
    else:
        typer.echo(result.failure, err=True)
    raise typer.Exit(code=0 if result.succeeded else 1)


@schedule_app.command("explain")
def schedule_explain(
    ctx: typer.Context,
    expression: Annotated[
        str,
        typer.Argument(help='A schedule expression, such as "every weekday at 06:30".'),
    ],
) -> None:
    """Show the cron expression a schedule expression produces, without saving anything.

    Deliberately available before a capability exists. Checking what you meant should not
    require first defining the job you are unsure about.
    """
    del ctx
    cron = parse_schedule_expression(expression)
    typer.echo(f"{expression}  ->  {cron.to_primitive()}")
    typer.echo(f"reads back as: {describe(cron)}")
