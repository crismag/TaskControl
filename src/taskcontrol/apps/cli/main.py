"""Composition root for the command-line interface.

Builds settings, configures logging, and hands control to the command group. It wires; it
does not define commands (ADR 0019).
"""

from __future__ import annotations

import sys

import typer

from taskcontrol.cli.commands import app as commands
from taskcontrol.common.errors import ConfigurationError, TaskControlError
from taskcontrol.infrastructure.logging import configure_logging
from taskcontrol.infrastructure.settings import Settings, load_settings

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_CONFIGURATION = 78  # EX_CONFIG, sysexits.h


@commands.callback()
def _bootstrap(ctx: typer.Context) -> None:
    """Build settings and configure logging before any command runs.

    Args:
        ctx: The Typer context, which carries settings to the commands.

    Raises:
        ConfigurationError: If the environment does not produce valid settings.
    """
    settings: Settings = load_settings()
    configure_logging(settings)
    ctx.obj = settings


def main() -> int:
    """Run the CLI.

    Translates the error taxonomy into documented exit codes so that scripts and CI can
    branch on the result:

    * ``0`` — success
    * ``1`` — a TaskControl error the user can act on
    * ``78`` — invalid configuration (``EX_CONFIG``)

    Returns:
        The process exit code.
    """
    try:
        commands()
    except ConfigurationError as exc:
        print(f"Configuration error: {exc.message}", file=sys.stderr)  # noqa: T201
        if exc.details:
            print(f"  {exc.details}", file=sys.stderr)  # noqa: T201
        return EXIT_CONFIGURATION
    except TaskControlError as exc:
        print(f"Error [{exc.code}]: {exc.message}", file=sys.stderr)  # noqa: T201
        return EXIT_ERROR
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
