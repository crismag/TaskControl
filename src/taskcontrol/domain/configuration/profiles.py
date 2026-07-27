"""Layered configuration, resolved deterministically and explained.

Two properties define this module, and both come from the engineering laws:

* **Deterministic.** The same profiles resolve to the same values in the same order, every
  time. Ambiguity is an error, not a coin flip.
* **Explainable.** Every resolved key reports which layer supplied it and which layers were
  overridden. "Why did this task run with the wrong region?" must be answerable from the
  record, not by re-reading files.

Secret values never enter resolution. A secret-bearing key resolves to a
:class:`SecretReference`, which the execution boundary materialises through an adapter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Self

from taskcontrol.common.errors import DomainRuleViolationError, ValidationError
from taskcontrol.domain.common.identifiers import ProfileId
from taskcontrol.domain.common.values import SecretReference, Slug

MAX_VARIABLE_NAME_LENGTH = 200
MAX_VARIABLES_PER_PROFILE = 500


class ConfigurationLayer(IntEnum):
    """Where a configuration value came from, ordered lowest to highest precedence.

    An :class:`enum.IntEnum` because precedence *is* the ordering — comparing two layers
    must answer "which wins" directly.

    The handbook lists ten layers for the full product. Phase 1 implements the subset that
    a local installation can actually populate; the gaps are deliberate and numbered so
    that inserting region or tenant defaults later does not renumber anything.
    """

    PRODUCT_DEFAULT = 10
    "Shipped defaults. The floor."

    ORGANISATION_DEFAULT = 20
    "Installation-wide defaults."

    ENVIRONMENT_DEFAULT = 40
    "Per-environment defaults, such as staging versus production."

    COLLECTION_DEFAULT = 50
    "Defaults inherited from a task collection."

    TARGET_DEFAULT = 60
    "Defaults for the target the task runs on."

    TASK_REVISION = 80
    "Bound by the task revision itself."

    TRIGGER_PARAMETER = 90
    "Supplied with the trigger that started this execution."

    EXECUTION_OVERRIDE = 100
    "An authorised one-time override for a single run. The ceiling."

    @property
    def label(self) -> str:
        """A readable name for display and for the resolution trace."""
        return self.name.lower()


@dataclass(frozen=True, slots=True)
class Variable:
    """One configuration value, which may be a literal or a secret reference.

    Attributes:
        name: The key.
        value: A literal value, when not secret.
        secret: A reference resolved at the execution boundary, when secret.
        overridable: Whether a higher layer may replace this value. A layer can pin a
            value that policy says must not be changed downstream.
    """

    name: str
    value: str | None = None
    secret: SecretReference | None = None
    overridable: bool = True

    def __post_init__(self) -> None:
        """Validate the variable.

        Raises:
            ValidationError: If the name is unusable, or the variable is neither or both.
        """
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValidationError("A configuration variable requires a name.")
        if len(self.name) > MAX_VARIABLE_NAME_LENGTH:
            raise ValidationError(
                "Variable name is too long.", details={"maximum": MAX_VARIABLE_NAME_LENGTH}
            )
        if (self.value is None) == (self.secret is None):
            raise ValidationError(
                "A variable must hold exactly one of a literal value or a secret reference.",
                details={"name": self.name},
            )

    @property
    def is_secret(self) -> bool:
        """Whether this variable resolves a secret at the execution boundary."""
        return self.secret is not None

    def to_primitive(self) -> dict[str, Any]:
        """Return a representation safe to store, digest, and display."""
        rendered: dict[str, Any] = {"name": self.name, "overridable": self.overridable}
        if self.secret is not None:
            rendered["secret"] = self.secret.to_primitive()
        else:
            rendered["value"] = self.value
        return rendered

    @classmethod
    def from_primitive(cls, data: dict[str, Any]) -> Self:
        """Rebuild from a stored representation.

        Args:
            data: A mapping with ``name`` and one of ``value`` or ``secret``.

        Returns:
            The variable.

        Raises:
            ValidationError: If the mapping is malformed.
        """
        if not isinstance(data, dict):
            raise ValidationError("A configuration variable must be a mapping.")
        secret = data.get("secret")
        return cls(
            name=data.get("name", ""),
            value=data.get("value"),
            secret=SecretReference.parse(secret) if secret is not None else None,
            overridable=bool(data.get("overridable", True)),
        )


@dataclass(frozen=True, slots=True)
class Profile:
    """A named set of configuration variables bound at one layer.

    Attributes:
        profile_id: Stable identifier.
        name: Human-readable name.
        slug: Stable reference name.
        layer: Which precedence layer this profile contributes at.
        variables: The variables it supplies.
        description: What this profile is for.
    """

    profile_id: ProfileId
    name: str
    slug: Slug
    layer: ConfigurationLayer
    variables: tuple[Variable, ...] = ()
    description: str = ""

    def __post_init__(self) -> None:
        """Validate the profile.

        Raises:
            ValidationError: If names collide or the profile is oversized.
        """
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValidationError("A profile requires a name.")
        if len(self.variables) > MAX_VARIABLES_PER_PROFILE:
            raise ValidationError(
                "Too many variables in one profile.",
                details={"count": len(self.variables), "maximum": MAX_VARIABLES_PER_PROFILE},
            )

        names = [variable.name for variable in self.variables]
        if len(names) != len(set(names)):
            duplicates = sorted({name for name in names if names.count(name) > 1})
            raise ValidationError(
                "Variable names must be unique within a profile. Two definitions of the "
                "same key in one layer have no defined precedence.",
                details={"profile": self.name, "duplicates": duplicates},
            )

    def variable(self, name: str) -> Variable | None:
        """Return a variable by name, or ``None`` when absent."""
        return next((item for item in self.variables if item.name == name), None)

    def to_primitive(self) -> dict[str, Any]:
        """Return a stable representation."""
        return {
            "profile_id": self.profile_id.to_primitive(),
            "name": self.name,
            "slug": self.slug.to_primitive(),
            "layer": self.layer.label,
            "description": self.description,
            "variables": [variable.to_primitive() for variable in self.variables],
        }


@dataclass(frozen=True, slots=True)
class ResolvedValue:
    """One resolved configuration key, with its provenance.

    Attributes:
        name: The key.
        value: The winning literal value, when not secret.
        secret: The winning secret reference, when secret.
        layer: The layer that supplied the winning value.
        source_profile: The profile that supplied it.
        overridden: Layers that also defined this key and lost, lowest first.
    """

    name: str
    layer: ConfigurationLayer
    source_profile: str
    value: str | None = None
    secret: SecretReference | None = None
    overridden: tuple[tuple[ConfigurationLayer, str], ...] = ()

    @property
    def is_secret(self) -> bool:
        """Whether this key resolves to a secret reference."""
        return self.secret is not None

    def display_value(self) -> str:
        """Return a value safe to show a user or write to a log.

        Returns:
            The literal value, or the secret's *reference* when the key is secret. A
            secret value is never available here, because the domain never holds one.
        """
        if self.secret is not None:
            return f"<secret {self.secret}>"
        return self.value or ""

    def to_primitive(self) -> dict[str, Any]:
        """Return a representation safe to store and display."""
        rendered: dict[str, Any] = {
            "name": self.name,
            "layer": self.layer.label,
            "source_profile": self.source_profile,
            "is_secret": self.is_secret,
            "overridden_by_layers": [layer.label for layer, _ in self.overridden],
        }
        if self.secret is not None:
            rendered["secret"] = self.secret.to_primitive()
        else:
            rendered["value"] = self.value
        return rendered


@dataclass(frozen=True, slots=True)
class ResolutionTrace:
    """The complete, explainable result of resolving configuration.

    Attributes:
        values: Resolved keys, by name.
        profiles_applied: Profiles that took part, in precedence order.
    """

    values: dict[str, ResolvedValue] = field(default_factory=dict)
    profiles_applied: tuple[str, ...] = ()

    def __getitem__(self, name: str) -> ResolvedValue:
        """Return a resolved key.

        Args:
            name: The key.

        Returns:
            The resolved value.

        Raises:
            KeyError: If the key was not defined by any layer.
        """
        return self.values[name]

    def get(self, name: str) -> ResolvedValue | None:
        """Return a resolved key, or ``None`` when it was never defined."""
        return self.values.get(name)

    @property
    def secret_references(self) -> tuple[SecretReference, ...]:
        """Every secret the execution boundary must materialise."""
        return tuple(
            resolved.secret for resolved in self.values.values() if resolved.secret is not None
        )

    def environment_literals(self) -> dict[str, str]:
        """Return only the non-secret values, ready to become process environment.

        Secrets are excluded deliberately. They are added at the execution boundary after
        an adapter resolves them, so they never pass through a stored or logged mapping.

        Returns:
            A mapping of key to literal value.
        """
        return {
            name: resolved.value
            for name, resolved in self.values.items()
            if resolved.value is not None
        }

    def explain(self, name: str) -> str:
        """Explain where one key's value came from.

        Args:
            name: The key.

        Returns:
            A human-readable sentence naming the winning layer and what it overrode.
        """
        resolved = self.values.get(name)
        if resolved is None:
            return f"{name!r} was not defined by any layer."

        explanation = (
            f"{name!r} resolved from the {resolved.layer.label} layer "
            f"(profile {resolved.source_profile!r})."
        )
        if resolved.overridden:
            losers = ", ".join(
                f"{layer.label} ({profile!r})" for layer, profile in resolved.overridden
            )
            explanation += f" It overrode: {losers}."
        return explanation

    def to_primitive(self) -> dict[str, Any]:
        """Return a representation safe to store and display."""
        return {
            "profiles_applied": list(self.profiles_applied),
            "values": {
                name: resolved.to_primitive() for name, resolved in sorted(self.values.items())
            },
        }


def resolve_configuration(profiles: tuple[Profile, ...]) -> ResolutionTrace:
    """Resolve ordered profile layers into explained values.

    Profiles are sorted by layer, then applied lowest first so higher layers override. The
    sort is stable, so two profiles at the same layer apply in the order given — which is
    why defining the same key twice at one layer is rejected rather than silently
    last-one-wins.

    Args:
        profiles: The profiles to resolve. Order matters only within a single layer.

    Returns:
        The resolution trace, with provenance for every key.

    Raises:
        DomainRuleViolationError: If two profiles at the same layer define the same key,
            or a higher layer tries to override a value pinned as non-overridable.
    """
    ordered = sorted(profiles, key=lambda profile: profile.layer)
    resolved: dict[str, ResolvedValue] = {}
    pinned: dict[str, tuple[ConfigurationLayer, str]] = {}
    claimed_at_layer: dict[tuple[ConfigurationLayer, str], str] = {}

    for profile in ordered:
        for variable in profile.variables:
            key = (profile.layer, variable.name)
            if key in claimed_at_layer:
                raise DomainRuleViolationError(
                    "Two profiles at the same layer define the same key, so which one "
                    "wins is undefined. Resolve the conflict rather than relying on order.",
                    details={
                        "variable": variable.name,
                        "layer": profile.layer.label,
                        "profiles": sorted([claimed_at_layer[key], profile.name]),
                    },
                )
            claimed_at_layer[key] = profile.name

            if variable.name in pinned:
                pinned_layer, pinned_profile = pinned[variable.name]
                raise DomainRuleViolationError(
                    "This value is pinned by a lower layer and must not be overridden.",
                    details={
                        "variable": variable.name,
                        "pinned_by_layer": pinned_layer.label,
                        "pinned_by_profile": pinned_profile,
                        "attempted_by_layer": profile.layer.label,
                        "attempted_by_profile": profile.name,
                    },
                )

            previous = resolved.get(variable.name)
            overridden = (
                (*previous.overridden, (previous.layer, previous.source_profile))
                if previous is not None
                else ()
            )

            resolved[variable.name] = ResolvedValue(
                name=variable.name,
                value=variable.value,
                secret=variable.secret,
                layer=profile.layer,
                source_profile=profile.name,
                overridden=overridden,
            )

            if not variable.overridable:
                pinned[variable.name] = (profile.layer, profile.name)

    return ResolutionTrace(
        values=resolved,
        profiles_applied=tuple(profile.name for profile in ordered),
    )
