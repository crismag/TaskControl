"""Where installed revisions live on a host.

One file per capability, written atomically at deploy time, read by the wrapper cron wakes.
Owner-readable only: a manifest carries no secret values, but it does carry the exact
command a privileged job will run, and that is not something to leave world-readable.

The store is deliberately dumb. It writes bytes and reads them back; every judgement about
what a manifest *means* — whether it is intact, whether it may run — belongs to
:class:`~taskcontrol.domain.deployment.manifest.InstalledRevision`.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from taskcontrol.common.errors import (
    NotFoundError,
    TransientInfrastructureError,
    ValidationError,
)
from taskcontrol.domain.common.values import Slug
from taskcontrol.domain.deployment.manifest import InstalledRevision

MANIFEST_SUFFIX = ".json"
MANIFEST_MODE = 0o600
DIRECTORY_MODE = 0o700


class InstalledRevisionStore:
    """Reads and writes installed revision manifests.

    Args:
        directory: Where manifests live. Created on first write, owner-only.
    """

    def __init__(self, directory: Path) -> None:
        """Store the directory."""
        self._directory = directory

    @property
    def directory(self) -> Path:
        """Where manifests are kept."""
        return self._directory

    def path_for(self, slug: Slug) -> Path:
        """Return the manifest path for a capability.

        Args:
            slug: The capability's slug.

        Returns:
            The path.
        """
        return self._directory / f"{slug.to_primitive()}{MANIFEST_SUFFIX}"

    def install(self, manifest: InstalledRevision) -> Path:
        """Write a manifest, replacing any earlier one.

        Written to a temporary file and renamed over the target, so a crash mid-write
        cannot leave a wrapper reading half a manifest — which it would then refuse as
        corrupt, turning a partial write into a stopped job.

        Args:
            manifest: What to install.

        Returns:
            Where it was written.

        Raises:
            TransientInfrastructureError: If it could not be written.
        """
        destination = self.path_for(manifest.slug)
        temporary = destination.with_name(f".{destination.name}.tmp")

        try:
            self._directory.mkdir(parents=True, exist_ok=True)
            os.chmod(self._directory, DIRECTORY_MODE)  # noqa: PTH101 - mode on an existing dir
            temporary.write_text(
                json.dumps(manifest.to_primitive(), indent=2, sort_keys=False) + "\n",
                encoding="utf-8",
            )
            temporary.chmod(MANIFEST_MODE)
            temporary.replace(destination)
        except OSError as error:
            temporary.unlink(missing_ok=True)
            raise TransientInfrastructureError(
                f"Could not install the revision manifest for '{manifest.slug}'.",
                details={"path": str(destination), "reason": error.strerror or ""},
            ) from error

        return destination

    def load(self, slug: Slug) -> InstalledRevision:
        """Read and verify an installed manifest.

        Integrity is checked here rather than left to the caller. Every caller is about to
        run something as a consequence, and a check that can be forgotten is a check that
        will be.

        Args:
            slug: The capability to load.

        Returns:
            The installed revision, verified against its own digest.

        Raises:
            NotFoundError: If nothing is installed for this capability.
            ValidationError: If the file is malformed, written by a newer TaskControl, or
                has been modified since installation.
            TransientInfrastructureError: If it exists and could not be read.
        """
        path = self.path_for(slug)
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError as error:
            raise NotFoundError(
                f"No installed revision for '{slug}' on this host. Run "
                "'taskctl schedule apply' to install it.",
                details={"path": str(path)},
            ) from error
        except OSError as error:
            raise TransientInfrastructureError(
                f"Could not read the installed revision for '{slug}'.",
                details={"path": str(path), "reason": error.strerror or ""},
            ) from error

        try:
            data = json.loads(text)
        except json.JSONDecodeError as error:
            raise ValidationError(
                f"The installed manifest for '{slug}' is not valid JSON, so it was "
                "truncated or edited. Refusing to run it.",
                details={"path": str(path)},
            ) from error

        manifest = InstalledRevision.from_primitive(data)
        manifest.verify_integrity()
        return manifest

    def installed_slugs(self) -> tuple[str, ...]:
        """Return every capability with a manifest on this host, sorted."""
        if not self._directory.is_dir():
            return ()
        return tuple(
            sorted(
                path.stem
                for path in self._directory.iterdir()
                if path.is_file() and path.suffix == MANIFEST_SUFFIX
            )
        )

    def remove(self, slug: Slug) -> None:
        """Remove an installed manifest, ignoring one that is already gone.

        Args:
            slug: The capability to uninstall.

        Raises:
            TransientInfrastructureError: If it exists and could not be removed.
        """
        try:
            self.path_for(slug).unlink(missing_ok=True)
        except OSError as error:
            raise TransientInfrastructureError(
                f"Could not remove the installed revision for '{slug}'.",
                details={"reason": error.strerror or ""},
            ) from error
