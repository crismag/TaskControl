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
from taskcontrol.infrastructure.database import create_database_engine, database_url
from taskcontrol.infrastructure.migrations import is_up_to_date
from taskcontrol.infrastructure.settings import Settings

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


def _database_check(settings: Settings) -> ReadinessCheck:
    """Check that the database is reachable and at the expected schema revision.

    Deliberately cheap: one connection and one query against the version table. Readiness
    is polled frequently and must not become a load source of its own.

    Args:
        settings: Validated settings.

    Returns:
        The check result, naming the problem when there is one.
    """
    engine = create_database_engine(database_url(settings))
    try:
        if not is_up_to_date(engine):
            return ReadinessCheck(
                name="database",
                ready=False,
                detail="The database schema is missing or out of date. Run 'taskctl init'.",
            )
    except Exception as exc:  # noqa: BLE001 - any failure here means not ready
        # The exception type is reported; the message is not, because a driver error can
        # echo the connection URL, which may embed a password.
        return ReadinessCheck(
            name="database",
            ready=False,
            detail=f"The database is not reachable ({type(exc).__name__}).",
        )
    finally:
        engine.dispose()

    return ReadinessCheck(name="database", ready=True, detail=None)


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

    A process serving against a missing or out-of-date schema fails in confusing ways, so
    it reports itself not ready instead. The scheduler joins this list in Wave 5.

    Args:
        response: Injected so the status code can be set to 503 when not ready.
        settings: Injected application settings.

    Returns:
        Aggregate readiness and the individual check results.
    """
    # Settings validate at startup, so reaching this point means configuration is sound.
    checks = [ReadinessCheck(name="configuration", ready=True, detail=None)]
    checks.append(_database_check(settings.value))

    all_ready = all(check.ready for check in checks)
    if not all_ready:
        response.status_code = HTTP_SERVICE_UNAVAILABLE

    return ReadinessResponse(ready=all_ready, version=__version__, checks=checks)
