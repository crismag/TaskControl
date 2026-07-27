"""Layered configuration: profiles, variables, and explained resolution."""

from __future__ import annotations

from taskcontrol.domain.configuration.profiles import (
    ConfigurationLayer,
    Profile,
    ResolutionTrace,
    ResolvedValue,
    Variable,
    resolve_configuration,
)

__all__ = [
    "ConfigurationLayer",
    "Profile",
    "ResolutionTrace",
    "ResolvedValue",
    "Variable",
    "resolve_configuration",
]
