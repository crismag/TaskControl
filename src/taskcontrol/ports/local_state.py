"""Ports for the local state a cron-woken wrapper depends on.

The wrapper's whole purpose is to work without the control plane, which makes *where* it
reads from an infrastructure decision — a file today, a package payload or a read-only
mount tomorrow. So the application depends on these two protocols and never on a path.

The architecture test caught this the moment the import existed, which is the point of
having it.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Protocol, runtime_checkable

from taskcontrol.domain.common.values import Slug
from taskcontrol.domain.deployment.manifest import InstalledRevision
from taskcontrol.domain.execution.journal import JournalEntry


@runtime_checkable
class InstalledRevisionReader(Protocol):
    """Reads the locally installed definition of a capability."""

    def load(self, slug: Slug) -> InstalledRevision:
        """Return the installed revision, verified against its own digest.

        An implementation **must** verify integrity before returning. Every caller is
        about to run something as a consequence, and a check that can be forgotten is a
        check that will be.

        Args:
            slug: Which capability.

        Returns:
            The installed revision.

        Raises:
            NotFoundError: If nothing is installed for this capability.
            ValidationError: If the manifest is malformed, written by a newer TaskControl,
                or has been modified since it was installed.
        """
        ...


@runtime_checkable
class ActivationJournalPort(Protocol):
    """Records activations that could not reach the control plane.

    An implementation must be append-only and must make each entry durable before
    returning. An entry that reached a buffer and not the disk is exactly the entry lost
    to the power failure that made the control plane unreachable.
    """

    def append(self, entry: JournalEntry) -> None:
        """Record one activation.

        Args:
            entry: The journal entry.

        Raises:
            Exception: If it could not be recorded. The caller must treat this as
                critical: the work has already run and nothing now says so.
        """
        ...

    def entries(self) -> Iterator[JournalEntry]:
        """Read every recorded activation, oldest first.

        A malformed entry must be skipped rather than allowed to stop the read: one torn
        write must not make every later entry unreconcilable.

        Yields:
            Each readable entry.
        """
        ...

    def unreadable_line_count(self) -> int:
        """Return how many records could not be read.

        Reported rather than silently skipped: an operator reconciling a journal needs to
        know something was lost, even when nothing can be done about it.
        """
        ...

    def truncate(self) -> None:
        """Discard the journal once every entry is durably recorded elsewhere."""
        ...


@runtime_checkable
class InstalledRevisionWriter(Protocol):
    """Installs and removes the local definitions a wrapper reads.

    Separate from the reader because the wrapper only ever reads. A cron-woken process that
    could rewrite its own definition would defeat the point of installing one.
    """

    def install(self, manifest: InstalledRevision) -> Path:
        """Write a manifest, replacing any earlier one.

        Must be atomic: a crash mid-write cannot leave a wrapper reading half a manifest,
        which it would refuse as corrupt — turning a partial write into a stopped job.

        Args:
            manifest: What to install.

        Returns:
            Where it was written.
        """
        ...

    def remove(self, slug: Slug) -> None:
        """Remove an installed manifest. Removing an absent one is not an error."""
        ...

    def installed_slugs(self) -> tuple[str, ...]:
        """Return every capability with a manifest on this host, sorted."""
        ...
