"""CLI smoke tests covering success and the documented failure paths."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from taskcontrol import __version__
from taskcontrol.apps.cli.main import EXIT_CONFIGURATION, EXIT_ERROR, main
from taskcontrol.cli.commands import app
from taskcontrol.common.errors import NotFoundError

pytestmark = pytest.mark.integration

runner = CliRunner()


def test_version_prints_the_package_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == __version__


def test_version_json_output_is_machine_readable() -> None:
    result = runner.invoke(app, ["version", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"version": __version__}


def test_health_reports_effective_configuration() -> None:
    result = runner.invoke(app, ["health"])
    assert result.exit_code == 0
    assert "ok" in result.stdout
    assert "environment" in result.stdout


def test_health_json_output_is_machine_readable() -> None:
    result = runner.invoke(app, ["health", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["version"] == __version__
    assert payload["environment"] == "local"


def test_health_makes_no_network_call() -> None:
    """`taskctl health` reports on this process, so it works with no server running."""
    result = runner.invoke(app, ["health", "--json"])
    assert result.exit_code == 0


def test_no_arguments_shows_help() -> None:
    """A bare invocation prints help and exits 2, the Click convention for usage output."""
    result = runner.invoke(app, [])
    assert result.exit_code == 2
    assert "Usage" in result.stdout


def test_explicit_help_exits_zero() -> None:
    """Asking for help is not an error."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Usage" in result.stdout


def test_unknown_command_exits_non_zero() -> None:
    assert runner.invoke(app, ["definitely-not-a-command"]).exit_code != 0


def test_taskcontrol_errors_exit_with_code_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """A TaskControl error the user can act on exits 1, distinct from misconfiguration."""

    def _raise(*_: object, **__: object) -> None:
        raise NotFoundError("task not found")

    monkeypatch.setattr("taskcontrol.apps.cli.main.commands", _raise)
    assert main() == EXIT_ERROR


def test_error_output_goes_to_stderr(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Errors must not pollute stdout, which scripts parse."""

    def _raise(*_: object, **__: object) -> None:
        raise NotFoundError("task not found")

    monkeypatch.setattr("taskcontrol.apps.cli.main.commands", _raise)
    main()
    captured = capsys.readouterr()
    assert "task not found" in captured.err
    assert captured.out == ""


def test_invalid_configuration_exits_with_ex_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Documented exit code 78 lets a script distinguish misconfiguration from failure."""
    monkeypatch.setenv("TASKCONTROL_LOG_LEVEL", "not-a-level")
    monkeypatch.setattr("sys.argv", ["taskctl", "version"])
    assert main() == EXIT_CONFIGURATION


class TestUnreachableDatabase:
    """R1 Finding 3: an operator saw forty-three lines of SQLAlchemy traceback.

    Standards require that internal paths, vendor errors, and stack traces never reach a
    user. The exit code was always right — cron saw a failure rather than a false success —
    but what it printed was the library's problem, not the operator's.
    """

    def test_the_operator_sees_a_sentence_not_a_traceback(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv("TASKCONTROL_DATABASE_URL", "sqlite+pysqlite:////nonexistent/tc.db")
        monkeypatch.setattr("sys.argv", ["taskctl", "run", "nightly-backup"])

        exit_code = main()
        output = capsys.readouterr()
        combined = output.out + output.err

        assert exit_code == EXIT_ERROR
        assert "Traceback" not in combined
        assert "sqlalchemy" not in combined.lower()
        assert "site-packages" not in combined
        assert "database" in combined.lower()

    def test_it_still_fails_loudly(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The half that already worked, and must keep working: cron must see a failure."""
        monkeypatch.setenv("TASKCONTROL_DATABASE_URL", "sqlite+pysqlite:////nonexistent/tc.db")
        monkeypatch.setattr("sys.argv", ["taskctl", "run", "nightly-backup"])

        assert main() == EXIT_ERROR
        capsys.readouterr()
