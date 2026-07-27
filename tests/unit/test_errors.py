"""The error taxonomy: stable codes and safe serialisation."""

from __future__ import annotations

import pytest

from taskcontrol.common.errors import (
    ConfigurationError,
    ConflictError,
    DomainRuleViolationError,
    ErrorCode,
    NotAuthorisedError,
    NotFoundError,
    PermanentInfrastructureError,
    TaskControlError,
    TransientInfrastructureError,
    ValidationError,
)

ALL_ERRORS = [
    ValidationError,
    DomainRuleViolationError,
    NotAuthorisedError,
    NotFoundError,
    ConflictError,
    ConfigurationError,
    TransientInfrastructureError,
    PermanentInfrastructureError,
]


@pytest.mark.parametrize("error_type", ALL_ERRORS)
def test_every_error_is_a_taskcontrol_error(error_type: type[TaskControlError]) -> None:
    assert issubclass(error_type, TaskControlError)


@pytest.mark.parametrize("error_type", ALL_ERRORS)
def test_every_error_carries_a_distinct_code(error_type: type[TaskControlError]) -> None:
    assert isinstance(error_type.code, ErrorCode)


def test_codes_are_unique_across_the_taxonomy() -> None:
    codes = [error_type.code for error_type in ALL_ERRORS]
    assert len(codes) == len(set(codes))


def test_every_code_value_is_lower_snake_case() -> None:
    """Matches the serialisation rule ADR 0016 sets for the execution vocabulary."""
    for code in ErrorCode:
        assert code.value == code.value.lower()
        assert " " not in code.value
        assert "-" not in code.value


def test_to_dict_is_transport_neutral() -> None:
    error = ValidationError("schedule is invalid", details={"field": "cron"})
    assert error.to_dict() == {
        "code": "validation_failed",
        "message": "schedule is invalid",
        "details": {"field": "cron"},
    }


def test_message_is_preserved_and_str_is_human_readable() -> None:
    error = NotFoundError("task not found")
    assert str(error) == "task not found"
    assert error.message == "task not found"


def test_details_default_to_an_empty_mapping() -> None:
    assert ConflictError("stale revision").details == {}


def test_cause_is_preserved_when_translating() -> None:
    original = ValueError("underlying")
    try:
        try:
            raise original
        except ValueError as exc:
            raise TransientInfrastructureError("database unavailable") from exc
    except TransientInfrastructureError as translated:
        assert translated.__cause__ is original
