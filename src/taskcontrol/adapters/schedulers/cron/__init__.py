"""The cron scheduler management adapter.

Cron owns recurring activation; TaskControl owns the artefact that tells cron what to run
(ADR 0022). This package writes that artefact, in whichever of the four shapes the task's
deployment strategy calls for (ADR 0026).
"""

from taskcontrol.adapters.schedulers.cron.manager import (
    CronLayout,
    CronSchedulerManagement,
)
from taskcontrol.adapters.schedulers.cron.rendering import (
    AmbiguousManagedContentError,
    ManagedRegion,
    find_managed_regions,
    render_artefact,
)
from taskcontrol.adapters.schedulers.cron.stores import (
    FileCrontab,
    FilesystemDirectory,
    UserCrontab,
)

__all__ = [
    "AmbiguousManagedContentError",
    "CronLayout",
    "CronSchedulerManagement",
    "FileCrontab",
    "FilesystemDirectory",
    "ManagedRegion",
    "UserCrontab",
    "find_managed_regions",
    "render_artefact",
]
