"""The local journal — what a run records when the control plane is unreachable.

ADR 0027 settled the shape by settling a prior question: TaskControl logs **dispatch**, and
the runnable logs its own work. So a journal entry is small and fixed — identity, revision,
timing, how the process ended, and the classified outcome. **No captured output.** That is
precisely what makes it writable when things are already degraded; a journal that had to
carry arbitrary application output would be least likely to succeed exactly when it matters.

Two decisions here are load-bearing.

**The execution identity is allocated by the wrapper, before the work runs.** Reconciliation
then keys on that identity rather than on the shape of the entry, which makes ingestion
idempotent by primary key: replaying a journal ten times produces one execution record. The
alternative — matching on task and timestamp — turns a clock adjustment into a duplicate.

**There is no pre-write gate.** Nothing is journalled before the runnable executes. Writing
first would mean a full disk stops the backups, which is the precise failure availability-
first mode exists to survive.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path

from taskcontrol.common.errors import TransientInfrastructureError, ValidationError
from taskcontrol.domain.execution.journal import JournalEntry

JOURNAL_FILENAME = "activations.jsonl"
JOURNAL_MODE = 0o600
DIRECTORY_MODE = 0o700


class ActivationJournal:
    """Append-only local record of activations that could not reach the control plane.

    Args:
        directory: Where the journal lives. Created on first write, owner-only.
    """

    def __init__(self, directory: Path) -> None:
        """Store the directory."""
        self._directory = directory

    @property
    def path(self) -> Path:
        """The journal file."""
        return self._directory / JOURNAL_FILENAME

    def append(self, entry: JournalEntry) -> None:
        """Record one activation.

        Appended as a single line with an explicit flush and fsync. A journal entry that
        reached the page cache and not the disk is exactly the entry lost to the power
        failure that made the database unreachable in the first place.

        Args:
            entry: What to record.

        Raises:
            TransientInfrastructureError: If it could not be written. The caller must treat
                this as critical: the runnable has already run, its side effects exist, and
                nothing now records that they happened.
        """
        line = json.dumps(entry.to_primitive(), sort_keys=False) + "\n"

        try:
            self._directory.mkdir(parents=True, exist_ok=True)
            os.chmod(self._directory, DIRECTORY_MODE)  # noqa: PTH101 - mode on an existing dir
            existed = self.path.exists()
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line)
                handle.flush()
                os.fsync(handle.fileno())
            if not existed:
                self.path.chmod(JOURNAL_MODE)
        except OSError as error:
            raise TransientInfrastructureError(
                "Could not write the local activation journal.",
                details={"path": str(self.path), "reason": error.strerror or ""},
            ) from error

    def entries(self) -> Iterator[JournalEntry]:
        """Read every recorded activation, oldest first.

        A malformed line does not stop the read. One corrupt entry — a torn write from a
        power loss — must not make every later entry unreconcilable, which is the whole
        reason the format is one self-contained record per line.

        Yields:
            Each parseable entry.

        Raises:
            TransientInfrastructureError: If the journal exists and cannot be read.
        """
        try:
            text = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return
        except OSError as error:
            raise TransientInfrastructureError(
                "Could not read the local activation journal.",
                details={"path": str(self.path), "reason": error.strerror or ""},
            ) from error

        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                yield JournalEntry.from_primitive(json.loads(line))
            except (json.JSONDecodeError, ValidationError):
                continue

    def unreadable_line_count(self) -> int:
        """Return how many lines could not be parsed.

        Reported rather than silently skipped: an operator reconciling a journal needs to
        know that something was lost, even when nothing can be done about it.

        Returns:
            The count of lines the reader had to skip.
        """
        try:
            text = self.path.read_text(encoding="utf-8")
        except (FileNotFoundError, OSError):
            return 0

        skipped = 0
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                JournalEntry.from_primitive(json.loads(line))
            except (json.JSONDecodeError, ValidationError):
                skipped += 1
        return skipped

    def truncate(self) -> None:
        """Discard the journal after its entries have been reconciled.

        Only safe once every entry has been durably recorded in the control plane, which is
        why reconciliation does this itself rather than exposing it as an operator command.

        Raises:
            TransientInfrastructureError: If it could not be removed.
        """
        try:
            self.path.unlink(missing_ok=True)
        except OSError as error:
            raise TransientInfrastructureError(
                "Could not clear the local activation journal after reconciling it.",
                details={"path": str(self.path), "reason": error.strerror or ""},
            ) from error
