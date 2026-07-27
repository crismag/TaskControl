"""CLI command definitions.

Commands translate arguments into calls and results into terminal output. They contain no
business rules; from Wave 6 they call application services.
"""

from __future__ import annotations

import json
from typing import Annotated

import typer

from taskcontrol import __version__
from taskcontrol.application.runtime import RunRequest
from taskcontrol.cli.wiring import build_runtime
from taskcontrol.domain.common.tracing import IdempotencyKey
from taskcontrol.domain.execution.execution import Execution, TriggerSource
from taskcontrol.infrastructure.database import (
    create_database_engine,
    database_url,
    ensure_data_directory,
)
from taskcontrol.infrastructure.migrations import current_revision, upgrade_to_head
from taskcontrol.infrastructure.server import run_api
from taskcontrol.infrastructure.settings import Settings

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
