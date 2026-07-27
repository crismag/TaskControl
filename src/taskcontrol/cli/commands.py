"""CLI command definitions.

Commands translate arguments into calls and results into terminal output. They contain no
business rules; from Wave 6 they call application services.
"""

from __future__ import annotations

import json
from typing import Annotated

import typer

from taskcontrol import __version__
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
