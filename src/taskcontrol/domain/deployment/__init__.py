"""How a capability's activation intent is deployed to a host scheduler.

The domain names the strategies and the rules governing them. It contains no crontab
syntax: rendering belongs to the scheduler adapter (ADR 0026).

``InstalledRevision`` deliberately is **not** re-exported here. It is built from a
``TaskRevision``, which itself carries a ``DeploymentSpecification`` from this package, so
re-exporting it makes importing a task revision import the manifest and back again. Import
it from ``taskcontrol.domain.deployment.manifest`` directly.
"""

from taskcontrol.domain.deployment.strategies import (
    DeploymentSpecification,
    DeploymentStrategy,
    DeploymentTarget,
    PeriodicClassification,
)

__all__ = [
    "DeploymentSpecification",
    "DeploymentStrategy",
    "DeploymentTarget",
    "PeriodicClassification",
]
