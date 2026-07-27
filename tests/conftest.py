"""Shared fixtures.

Tests must not inherit configuration from the developer's shell, so the environment is
cleared of TaskControl variables for every test.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator

import pytest

from taskcontrol.infrastructure.logging import clear_registered_secrets
from taskcontrol.infrastructure.settings import ENV_PREFIX, Settings, load_settings


@pytest.fixture(autouse=True)
def _isolated_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove TaskControl environment variables and disable .env discovery.

    Results must not depend on the developer's shell or on a local `.env`.
    """
    for key in [k for k in os.environ if k.startswith(ENV_PREFIX)]:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setitem(Settings.model_config, "env_file", None)


@pytest.fixture(autouse=True)
def _clean_secret_registry() -> Iterator[None]:
    """Ensure a secret registered by one test cannot affect another."""
    clear_registered_secrets()
    yield
    clear_registered_secrets()


@pytest.fixture
def settings() -> Settings:
    """Return default settings built without touching the environment."""
    return load_settings()


@pytest.fixture(autouse=True)
def _reset_root_logger() -> Iterator[None]:
    """Remove TaskControl's log handler after each test.

    Several suites call `configure_logging`. Without this, a handler installed by one test
    keeps emitting during the next, and captured output stops being trustworthy.
    """
    yield
    root = logging.getLogger()
    for handler in [h for h in root.handlers if h.get_name() == "taskcontrol"]:
        root.removeHandler(handler)
