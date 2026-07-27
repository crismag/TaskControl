"""How a capability's activation intent is deployed to a host scheduler.

The domain names the strategies and the rules governing them. It contains no crontab
syntax: rendering belongs to the scheduler adapter (ADR 0026).
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
