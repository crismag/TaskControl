"""Local host state a cron-woken wrapper can read without the control plane.

Installed revision manifests say what to run; the activation journal records what ran when
the control plane could not be told. Together they are what makes ADR 0024's
availability-first mode implementable at all (R1 Finding 2).
"""

from taskcontrol.adapters.local.journal import ActivationJournal
from taskcontrol.adapters.local.manifests import InstalledRevisionStore

__all__ = ["ActivationJournal", "InstalledRevisionStore"]
