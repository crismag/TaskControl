"""Where managed cron artefacts are actually stored.

Two shapes cover every target ADR 0026 names: a **crontab** is one blob of text read and
written whole, and a **managed directory** holds one file per task. Separating them from
the manager is what lets every strategy be tested against temporary files, with no test
ever touching a real crontab.

The user crontab is the awkward one. It is not a file an application may write — its real
location varies by cron implementation and is often not readable — so it is manipulated
through the ``crontab`` command, which is the only supported interface to it.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Protocol, runtime_checkable

from taskcontrol.common.errors import (
    ConfigurationError,
    PermanentInfrastructureError,
    TransientInfrastructureError,
)

CRONTAB_COMMAND_TIMEOUT_SECONDS = 30
"""How long to wait for ``crontab``. Generous: it is a local, near-instant operation, and a
process this slow has something wrong with it rather than something busy."""


@runtime_checkable
class CrontabText(Protocol):
    """A crontab read and written as one whole text."""

    @property
    def description(self) -> str:
        """Where this is, in terms an operator recognises."""
        ...

    @property
    def is_writable(self) -> bool:
        """Whether this process can write here right now."""
        ...

    def read(self) -> str:
        """Return the current content, empty when there is none.

        Raises:
            TransientInfrastructureError: If it could not be read.
        """
        ...

    def write(self, content: str) -> None:
        """Replace the content wholly.

        Raises:
            TransientInfrastructureError: If it could not be written.
        """
        ...


@runtime_checkable
class ManagedDirectory(Protocol):
    """A directory holding one artefact file per task."""

    @property
    def description(self) -> str:
        """Where this is, in terms an operator recognises."""
        ...

    @property
    def is_writable(self) -> bool:
        """Whether this process can write here right now."""
        ...

    def names(self) -> tuple[str, ...]:
        """Return the names of every file present, sorted."""
        ...

    def read(self, name: str) -> str:
        """Return one file's content, empty when it does not exist."""
        ...

    def write(self, name: str, content: str, *, executable: bool) -> None:
        """Write one file, replacing it if it exists."""
        ...

    def remove(self, name: str) -> None:
        """Remove one file. Removing an absent file is not an error."""
        ...


class FileCrontab:
    """A crontab that is an ordinary file, such as ``/etc/crontab``.

    Writes go to a temporary file in the same directory and are then renamed over the
    target, so a crash mid-write cannot leave cron reading half a crontab.
    """

    def __init__(self, path: Path) -> None:
        """Store the path.

        Args:
            path: The crontab file.
        """
        self._path = path

    @property
    def description(self) -> str:
        """The path."""
        return str(self._path)

    @property
    def is_writable(self) -> bool:
        """Whether this process can write the file, or create it."""
        if self._path.exists():
            return os.access(self._path, os.W_OK)
        return self._path.parent.is_dir() and os.access(self._path.parent, os.W_OK)

    def read(self) -> str:
        """Return the file's content, empty when it does not exist.

        Raises:
            TransientInfrastructureError: If the file exists and cannot be read.
        """
        try:
            return self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""
        except OSError as error:
            raise TransientInfrastructureError(
                f"Could not read the crontab at {self._path}.",
                details={"path": str(self._path), "reason": error.strerror or ""},
            ) from error

    def write(self, content: str) -> None:
        """Replace the file's content atomically.

        Raises:
            TransientInfrastructureError: If it could not be written.
        """
        temporary = self._path.with_name(f".{self._path.name}.taskcontrol.tmp")
        try:
            temporary.write_text(content, encoding="utf-8")
            temporary.replace(self._path)
        except OSError as error:
            temporary.unlink(missing_ok=True)
            raise TransientInfrastructureError(
                f"Could not write the crontab at {self._path}.",
                details={"path": str(self._path), "reason": error.strerror or ""},
            ) from error


class UserCrontab:
    """The invoking user's crontab, manipulated through the ``crontab`` command.

    The command is the only supported interface: the spool file's location varies by cron
    implementation, is usually unreadable to the user who owns it, and writing it directly
    skips the validation and reload that ``crontab`` performs.
    """

    def __init__(self, *, user: str | None = None, command: str = "crontab") -> None:
        """Configure the crontab command.

        Args:
            user: Whose crontab, or ``None`` for the invoking user's own. Naming another
                user requires privilege.
            command: The executable to use. Overridable so tests can substitute one.
        """
        self._user = user
        self._command = command

    @property
    def description(self) -> str:
        """Whose crontab this is."""
        return f"the crontab of {self._user}" if self._user else "your crontab"

    @property
    def is_writable(self) -> bool:
        """Whether the crontab command exists and can list this crontab."""
        if shutil.which(self._command) is None:
            return False
        try:
            self.read()
        except (TransientInfrastructureError, PermanentInfrastructureError):
            return False
        return True

    def _argv(self, *arguments: str) -> list[str]:
        """Build the command line, including the user selector when one is set."""
        selector = ["-u", self._user] if self._user else []
        return [self._command, *selector, *arguments]

    def read(self) -> str:
        """Return the crontab's content, empty when the user has none.

        Raises:
            PermanentInfrastructureError: If the command is missing.
            TransientInfrastructureError: If the command failed for another reason.
        """
        completed = self._run(self._argv("-l"))
        # "no crontab for <user>" is reported as a failure by every implementation, and it
        # is not one: an empty crontab is a perfectly ordinary starting state.
        if completed.returncode != 0:
            if "no crontab" in (completed.stderr or "").lower():
                return ""
            raise TransientInfrastructureError(
                f"Could not read {self.description}.",
                details={
                    "exit_code": completed.returncode,
                    "stderr": _first_line(completed.stderr),
                },
            )
        return completed.stdout

    def write(self, content: str) -> None:
        """Replace the crontab wholly.

        Raises:
            TransientInfrastructureError: If the command rejected the content or failed.
        """
        completed = self._run(self._argv("-"), stdin=content)
        if completed.returncode != 0:
            raise TransientInfrastructureError(
                f"The crontab command rejected the new content for {self.description}.",
                details={
                    "exit_code": completed.returncode,
                    "stderr": _first_line(completed.stderr),
                },
            )

    def _run(
        self, argv: list[str], *, stdin: str | None = None
    ) -> subprocess.CompletedProcess[str]:
        """Run the crontab command.

        Raises:
            PermanentInfrastructureError: If the command is not installed. Retrying will
                not install cron, so this is permanent rather than transient.
            TransientInfrastructureError: If it could not be run or did not finish.
        """
        try:
            return subprocess.run(  # noqa: S603 - argv is built here, never from user text
                argv,
                input=stdin,
                capture_output=True,
                text=True,
                timeout=CRONTAB_COMMAND_TIMEOUT_SECONDS,
                check=False,
            )
        except FileNotFoundError as error:
            raise PermanentInfrastructureError(
                f"The '{self._command}' command is not installed, so TaskControl cannot "
                "manage this crontab.",
                details={"command": self._command},
            ) from error
        except subprocess.TimeoutExpired as error:
            raise TransientInfrastructureError(
                f"The '{self._command}' command did not finish within "
                f"{CRONTAB_COMMAND_TIMEOUT_SECONDS} seconds.",
                details={"command": self._command},
            ) from error
        except OSError as error:
            raise TransientInfrastructureError(
                f"Could not run the '{self._command}' command.",
                details={"command": self._command, "reason": error.strerror or ""},
            ) from error


class FilesystemDirectory:
    """A directory of artefact files, such as ``/etc/cron.d`` or ``/etc/cron.daily``."""

    def __init__(self, path: Path) -> None:
        """Store the path.

        Args:
            path: The directory.
        """
        self._path = path

    @property
    def description(self) -> str:
        """The path."""
        return str(self._path)

    @property
    def is_writable(self) -> bool:
        """Whether the directory exists and this process can write in it."""
        return self._path.is_dir() and os.access(self._path, os.W_OK)

    def _assert_directory(self) -> None:
        """Raise if the directory is missing.

        Raises:
            ConfigurationError: If it does not exist. A missing cron directory is a
                configuration mistake — the wrong path, or the wrong host — not a
                transient fault, and retrying will not create it.
        """
        if not self._path.is_dir():
            raise ConfigurationError(
                f"The cron directory {self._path} does not exist. Check the configured "
                "path against this host's cron layout.",
                details={"path": str(self._path)},
            )

    def _resolve(self, name: str) -> Path:
        """Return the path for a file name, refusing anything that escapes the directory.

        Raises:
            ConfigurationError: If the name is not a plain file name.
        """
        if not name or "/" in name or name in {".", ".."}:
            raise ConfigurationError(
                "A cron artefact name must be a plain file name.",
                details={"name": name},
            )
        return self._path / name

    def names(self) -> tuple[str, ...]:
        """Return every file name present, sorted.

        Raises:
            ConfigurationError: If the directory does not exist.
        """
        self._assert_directory()
        return tuple(sorted(entry.name for entry in self._path.iterdir() if entry.is_file()))

    def read(self, name: str) -> str:
        """Return one file's content, empty when it does not exist.

        Raises:
            TransientInfrastructureError: If it exists and cannot be read.
        """
        try:
            return self._resolve(name).read_text(encoding="utf-8")
        except FileNotFoundError:
            return ""
        except OSError as error:
            raise TransientInfrastructureError(
                f"Could not read the cron artefact {name}.",
                details={"path": str(self._path / name), "reason": error.strerror or ""},
            ) from error

    def write(self, name: str, content: str, *, executable: bool) -> None:
        """Write one file atomically.

        A run-parts artefact that is not executable is silently ignored by cron, which
        looks exactly like a deployment that worked, so the mode is set explicitly rather
        than inherited from the umask.

        Args:
            name: The file name.
            content: What to write.
            executable: Whether the file must be executable.

        Raises:
            ConfigurationError: If the directory does not exist.
            TransientInfrastructureError: If it could not be written.
        """
        self._assert_directory()
        destination = self._resolve(name)
        temporary = destination.with_name(f".{name}.taskcontrol.tmp")
        try:
            temporary.write_text(content, encoding="utf-8")
            temporary.chmod(0o755 if executable else 0o644)
            temporary.replace(destination)
        except OSError as error:
            temporary.unlink(missing_ok=True)
            raise TransientInfrastructureError(
                f"Could not write the cron artefact {name}.",
                details={"path": str(destination), "reason": error.strerror or ""},
            ) from error

    def remove(self, name: str) -> None:
        """Remove one file, ignoring a file that is already gone.

        Raises:
            TransientInfrastructureError: If it exists and could not be removed.
        """
        try:
            self._resolve(name).unlink(missing_ok=True)
        except OSError as error:
            raise TransientInfrastructureError(
                f"Could not remove the cron artefact {name}.",
                details={"path": str(self._path / name), "reason": error.strerror or ""},
            ) from error


def _first_line(text: str | None) -> str:
    """Return the first line of command output, for an error detail.

    Only the first line: the rest is rarely informative and may be long.
    """
    if not text:
        return ""
    return text.strip().splitlines()[0] if text.strip() else ""
