"""Configuration resolution: deterministic, and explainable for every key."""

from __future__ import annotations

from itertools import pairwise

import pytest

from taskcontrol.common.errors import DomainRuleViolationError, ValidationError
from taskcontrol.domain.common import ProfileId, SecretReference, Slug
from taskcontrol.domain.configuration import (
    ConfigurationLayer,
    Profile,
    Variable,
    resolve_configuration,
)


def a_profile(name: str, layer: ConfigurationLayer, *variables: Variable) -> Profile:
    """Build a profile at a given layer."""
    return Profile(
        profile_id=ProfileId.generate(),
        name=name,
        slug=Slug.from_display_name(name),
        layer=layer,
        variables=variables,
    )


class TestConfigurationLayer:
    def test_layers_are_ordered_by_precedence(self) -> None:
        assert ConfigurationLayer.PRODUCT_DEFAULT < ConfigurationLayer.TASK_REVISION
        assert ConfigurationLayer.TASK_REVISION < ConfigurationLayer.EXECUTION_OVERRIDE

    def test_execution_override_is_the_ceiling(self) -> None:
        assert max(ConfigurationLayer) is ConfigurationLayer.EXECUTION_OVERRIDE

    def test_product_default_is_the_floor(self) -> None:
        assert min(ConfigurationLayer) is ConfigurationLayer.PRODUCT_DEFAULT

    def test_numbering_leaves_room_for_future_layers(self) -> None:
        """Region and tenant layers must be insertable without renumbering."""
        values = sorted(layer.value for layer in ConfigurationLayer)
        assert all(later - earlier >= 10 for earlier, later in pairwise(values))


class TestVariable:
    def test_holds_a_literal(self) -> None:
        assert not Variable("REGION", value="eu-west-1").is_secret

    def test_holds_a_secret_reference(self) -> None:
        assert Variable("TOKEN", secret=SecretReference.parse("env://TOKEN")).is_secret

    def test_rejects_both(self) -> None:
        with pytest.raises(ValidationError):
            Variable("TOKEN", value="x", secret=SecretReference.parse("env://TOKEN"))

    def test_rejects_neither(self) -> None:
        with pytest.raises(ValidationError):
            Variable("TOKEN")

    def test_rejects_an_empty_name(self) -> None:
        with pytest.raises(ValidationError):
            Variable("  ", value="x")

    def test_round_trips(self) -> None:
        variable = Variable("TOKEN", secret=SecretReference.parse("env://TOKEN"))
        assert Variable.from_primitive(variable.to_primitive()) == variable


class TestProfileValidation:
    def test_rejects_duplicate_names_within_one_profile(self) -> None:
        """Two definitions of one key in one layer have no defined precedence."""
        with pytest.raises(ValidationError) as caught:
            a_profile(
                "conflicted",
                ConfigurationLayer.TASK_REVISION,
                Variable("REGION", value="eu"),
                Variable("REGION", value="us"),
            )
        assert caught.value.details["duplicates"] == ["REGION"]

    def test_finds_a_variable_by_name(self) -> None:
        profile = a_profile(
            "base", ConfigurationLayer.PRODUCT_DEFAULT, Variable("REGION", value="eu")
        )
        assert profile.variable("REGION") is not None
        assert profile.variable("MISSING") is None


class TestResolution:
    def test_a_higher_layer_wins(self) -> None:
        trace = resolve_configuration(
            (
                a_profile(
                    "base", ConfigurationLayer.PRODUCT_DEFAULT, Variable("REGION", value="eu")
                ),
                a_profile("task", ConfigurationLayer.TASK_REVISION, Variable("REGION", value="us")),
            )
        )
        assert trace["REGION"].value == "us"
        assert trace["REGION"].layer is ConfigurationLayer.TASK_REVISION

    def test_input_order_does_not_change_the_result(self) -> None:
        """Precedence is the layer, not the order profiles happened to be listed."""
        low = a_profile("base", ConfigurationLayer.PRODUCT_DEFAULT, Variable("REGION", value="eu"))
        high = a_profile("task", ConfigurationLayer.TASK_REVISION, Variable("REGION", value="us"))
        assert resolve_configuration((low, high))["REGION"].value == "us"
        assert resolve_configuration((high, low))["REGION"].value == "us"

    def test_resolution_is_deterministic(self) -> None:
        profiles = (
            a_profile("base", ConfigurationLayer.PRODUCT_DEFAULT, Variable("A", value="1")),
            a_profile("env", ConfigurationLayer.ENVIRONMENT_DEFAULT, Variable("B", value="2")),
        )
        assert (
            resolve_configuration(profiles).to_primitive()
            == resolve_configuration(profiles).to_primitive()
        )

    def test_every_key_reports_its_source(self) -> None:
        trace = resolve_configuration(
            (a_profile("base", ConfigurationLayer.PRODUCT_DEFAULT, Variable("REGION", value="eu")),)
        )
        resolved = trace["REGION"]
        assert resolved.layer is ConfigurationLayer.PRODUCT_DEFAULT
        assert resolved.source_profile == "base"

    def test_overridden_layers_are_recorded_lowest_first(self) -> None:
        trace = resolve_configuration(
            (
                a_profile("base", ConfigurationLayer.PRODUCT_DEFAULT, Variable("R", value="1")),
                a_profile("env", ConfigurationLayer.ENVIRONMENT_DEFAULT, Variable("R", value="2")),
                a_profile("task", ConfigurationLayer.TASK_REVISION, Variable("R", value="3")),
            )
        )
        layers = [layer for layer, _ in trace["R"].overridden]
        assert layers == [
            ConfigurationLayer.PRODUCT_DEFAULT,
            ConfigurationLayer.ENVIRONMENT_DEFAULT,
        ]

    def test_explains_where_a_value_came_from(self) -> None:
        trace = resolve_configuration(
            (
                a_profile("base", ConfigurationLayer.PRODUCT_DEFAULT, Variable("R", value="1")),
                a_profile("task", ConfigurationLayer.TASK_REVISION, Variable("R", value="2")),
            )
        )
        explanation = trace.explain("R")
        assert "task_revision" in explanation
        assert "product_default" in explanation

    def test_explains_an_undefined_key_without_raising(self) -> None:
        assert "not defined" in resolve_configuration(()).explain("MISSING")

    def test_rejects_two_profiles_at_the_same_layer_defining_one_key(self) -> None:
        """Relying on argument order here would make resolution non-deterministic."""
        with pytest.raises(DomainRuleViolationError) as caught:
            resolve_configuration(
                (
                    a_profile("a", ConfigurationLayer.TASK_REVISION, Variable("R", value="1")),
                    a_profile("b", ConfigurationLayer.TASK_REVISION, Variable("R", value="2")),
                )
            )
        assert caught.value.details["profiles"] == ["a", "b"]

    def test_a_pinned_value_cannot_be_overridden(self) -> None:
        with pytest.raises(DomainRuleViolationError) as caught:
            resolve_configuration(
                (
                    a_profile(
                        "org",
                        ConfigurationLayer.ORGANISATION_DEFAULT,
                        Variable("AUDIT_MODE", value="strict", overridable=False),
                    ),
                    a_profile(
                        "task",
                        ConfigurationLayer.TASK_REVISION,
                        Variable("AUDIT_MODE", value="off"),
                    ),
                )
            )
        assert caught.value.details["pinned_by_layer"] == "organisation_default"

    def test_pinning_does_not_affect_other_keys(self) -> None:
        trace = resolve_configuration(
            (
                a_profile(
                    "org",
                    ConfigurationLayer.ORGANISATION_DEFAULT,
                    Variable("AUDIT_MODE", value="strict", overridable=False),
                    Variable("REGION", value="eu"),
                ),
                a_profile("task", ConfigurationLayer.TASK_REVISION, Variable("REGION", value="us")),
            )
        )
        assert trace["REGION"].value == "us"
        assert trace["AUDIT_MODE"].value == "strict"

    def test_resolving_nothing_is_valid(self) -> None:
        assert resolve_configuration(()).values == {}


class TestSecretHandling:
    def test_a_secret_key_resolves_to_a_reference(self) -> None:
        trace = resolve_configuration(
            (
                a_profile(
                    "task",
                    ConfigurationLayer.TASK_REVISION,
                    Variable("TOKEN", secret=SecretReference.parse("env://API_TOKEN")),
                ),
            )
        )
        assert trace["TOKEN"].is_secret
        assert trace.secret_references == (SecretReference.parse("env://API_TOKEN"),)

    def test_secrets_are_excluded_from_environment_literals(self) -> None:
        """They are added at the execution boundary, never through a stored mapping."""
        trace = resolve_configuration(
            (
                a_profile(
                    "task",
                    ConfigurationLayer.TASK_REVISION,
                    Variable("REGION", value="eu"),
                    Variable("TOKEN", secret=SecretReference.parse("env://API_TOKEN")),
                ),
            )
        )
        assert trace.environment_literals() == {"REGION": "eu"}

    def test_display_value_shows_the_reference_not_a_value(self) -> None:
        trace = resolve_configuration(
            (
                a_profile(
                    "task",
                    ConfigurationLayer.TASK_REVISION,
                    Variable("TOKEN", secret=SecretReference.parse("env://API_TOKEN")),
                ),
            )
        )
        displayed = trace["TOKEN"].display_value()
        assert "env://API_TOKEN" in displayed
        assert "secret" in displayed

    def test_the_trace_representation_carries_no_secret_value(self) -> None:
        trace = resolve_configuration(
            (
                a_profile(
                    "task",
                    ConfigurationLayer.TASK_REVISION,
                    Variable("TOKEN", secret=SecretReference.parse("env://API_TOKEN")),
                ),
            )
        )
        rendered = str(trace.to_primitive())
        assert "env://API_TOKEN" in rendered
        assert trace.to_primitive()["values"]["TOKEN"]["is_secret"] is True
