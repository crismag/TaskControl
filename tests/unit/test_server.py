"""Server startup: the configured address is the address actually bound.

These tests exist because of a defect found by running the application rather than by
running the suite. ``api_host`` and ``api_port`` were validated, displayed by
``taskctl health``, and logged at startup, but never used to bind — the address came from
uvicorn's command line instead. Configuration that reports one thing and does another is
the failure mode this product exists to remove.
"""

from __future__ import annotations

from typing import Any

import pytest

from taskcontrol.infrastructure.logging import uvicorn_log_config
from taskcontrol.infrastructure.server import ASGI_FACTORY, run_api
from taskcontrol.infrastructure.settings import load_settings


@pytest.fixture
def captured_run(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Capture the arguments ``run_api`` passes to uvicorn without starting a server."""
    captured: dict[str, Any] = {}

    def _fake_run(target: str, **kwargs: Any) -> None:
        captured["target"] = target
        captured.update(kwargs)

    uvicorn = pytest.importorskip("uvicorn")
    monkeypatch.setattr(uvicorn, "run", _fake_run)
    return captured


def test_binds_to_the_configured_address(captured_run: dict[str, Any]) -> None:
    settings = load_settings(api_host="0.0.0.0", api_port=9321)  # noqa: S104
    run_api(settings)

    assert captured_run["host"] == "0.0.0.0"  # noqa: S104
    assert captured_run["port"] == 9321


def test_starts_the_asgi_factory(captured_run: dict[str, Any]) -> None:
    run_api(load_settings())

    assert captured_run["target"] == ASGI_FACTORY
    assert captured_run["factory"] is True


def test_uvicorn_access_log_is_disabled(captured_run: dict[str, Any]) -> None:
    """TaskControl emits its own correlated access log; uvicorn's would be duplicative."""
    run_api(load_settings())

    assert captured_run["access_log"] is False


def test_uvicorn_uses_taskcontrol_log_config(captured_run: dict[str, Any]) -> None:
    settings = load_settings()
    run_api(settings)

    assert captured_run["log_config"] == uvicorn_log_config(settings)


def test_reload_defaults_to_off(captured_run: dict[str, Any]) -> None:
    """Reload spawns a supervisor process and must never be the production default."""
    run_api(load_settings())

    assert captured_run["reload"] is False


def test_reload_is_passed_through_when_requested(captured_run: dict[str, Any]) -> None:
    run_api(load_settings(), reload=True)

    assert captured_run["reload"] is True


def test_asgi_factory_string_resolves() -> None:
    """The import string must name something that exists, or startup fails at runtime."""
    module_path, _, attribute = ASGI_FACTORY.partition(":")
    module = pytest.importorskip(module_path)

    assert callable(getattr(module, attribute))
