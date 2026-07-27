"""CLI command definitions.

Commands translate arguments into calls and results into terminal output. They contain no
business rules; from Wave 6 they call application services.
"""

from __future__ import annotations

import json
from typing import Annotated

import typer

from taskcontrol import __version__
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
