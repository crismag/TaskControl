"""Liveness and readiness endpoints.

Liveness answers "is this process alive". Readiness answers "can it serve its advertised
capability". They are separate on purpose: a process may be alive while a dependency it
needs is not yet reachable, and a load balancer must be able to tell the difference.

Readiness must stay cheap. It validates only what is required to serve, and never
performs expensive work.
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field

from taskcontrol import __version__
from taskcontrol.api.dependencies import SettingsDependency
from taskcontrol.api.errors import HTTP_SERVICE_UNAVAILABLE

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Process liveness."""

    status: Literal["ok"] = Field(description="Always 'ok' when the process is serving.")
    version: str = Field(description="Running TaskControl version.")
    environment: str = Field(description="Environment this process believes it is in.")


class ReadinessCheck(BaseModel):
    """The result of one readiness check."""

    name: str = Field(description="Identifier of the checked dependency.")
    ready: bool = Field(description="Whether the dependency is usable.")
    detail: str | None = Field(default=None, description="Explanation when not ready.")


class ReadinessResponse(BaseModel):
    """Aggregate readiness across every checked dependency."""

    ready: bool = Field(description="True only when every check passed.")
    version: str = Field(description="Running TaskControl version.")
    checks: list[ReadinessCheck] = Field(description="Individual dependency results.")


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness probe",
    response_description="The process is alive and serving requests.",
)
async def health(settings: Annotated[SettingsDependency, Depends()]) -> HealthResponse:
    """Report that the process is alive.

    This endpoint performs no I/O and touches no dependency. If it can be reached, the
    answer is yes.

    Args:
        settings: Injected application settings.

    Returns:
        Liveness, version, and environment.
    """
    return HealthResponse(
        status="ok",
        version=__version__,
        environment=str(settings.value.environment),
    )


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Readiness probe",
    responses={503: {"description": "At least one dependency is not ready."}},
)
async def ready(
    response: Response,
    settings: Annotated[SettingsDependency, Depends()],
) -> ReadinessResponse:
    """Report whether the process can serve its advertised capability.

    Wave 0 advertises only configuration validity, so exactly one check runs. Persistence
    joins this list in Wave 2 and the scheduler in Wave 5.

    Args:
        response: Injected so the status code can be set to 503 when not ready.
        settings: Injected application settings.

    Returns:
        Aggregate readiness and the individual check results.
    """
    checks = [
        ReadinessCheck(
            name="configuration",
            ready=True,
            detail=None,
        )
    ]

    # Settings validate at startup, so reaching this point means configuration is sound.
    # The check exists so the response shape is correct before real dependencies arrive.
    _ = settings

    all_ready = all(check.ready for check in checks)
    if not all_ready:
        response.status_code = HTTP_SERVICE_UNAVAILABLE

    return ReadinessResponse(ready=all_ready, version=__version__, checks=checks)
