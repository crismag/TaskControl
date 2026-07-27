"""Identifiers: opaque, typed, time-ordered."""

from __future__ import annotations

import uuid

import pytest

from taskcontrol.common.errors import ValidationError
from taskcontrol.domain.common import ExecutionId, ProfileId, TaskId, generate_uuid7


class TestUuid7:
    def test_generates_version_7(self) -> None:
        assert generate_uuid7().version == 7

    def test_embeds_the_timestamp_so_ids_sort_by_creation(self) -> None:
        earlier = generate_uuid7(timestamp_ms=1_000_000_000_000)
        later = generate_uuid7(timestamp_ms=1_000_000_001_000)
        assert earlier < later

    def test_values_are_unique_within_the_same_millisecond(self) -> None:
        stamp = 1_700_000_000_000
        generated = {generate_uuid7(timestamp_ms=stamp) for _ in range(1000)}
        assert len(generated) == 1000

    def test_rejects_a_timestamp_that_does_not_fit(self) -> None:
        with pytest.raises(ValidationError):
            generate_uuid7(timestamp_ms=1 << 48)


class TestEntityId:
    def test_generates_a_prefixed_identifier(self) -> None:
        assert str(TaskId.generate()).startswith("task_")

    def test_accepts_its_own_string_form(self) -> None:
        original = TaskId.generate()
        assert TaskId(str(original)) == original

    def test_accepts_a_bare_uuid(self) -> None:
        value = uuid.uuid4()
        assert TaskId(value).value == value

    def test_accepts_a_bare_uuid_string(self) -> None:
        value = uuid.uuid4()
        assert TaskId(str(value)).value == value

    def test_rejects_the_wrong_prefix(self) -> None:
        """A profile id must never be silently accepted where a task id is required."""
        profile = ProfileId.generate()
        with pytest.raises(ValidationError) as caught:
            TaskId(str(profile))
        assert caught.value.details["expected_prefix"] == "task"

    @pytest.mark.parametrize("value", ["", "   ", "task_not-a-uuid", "garbage"])
    def test_rejects_malformed_values(self, value: str) -> None:
        with pytest.raises(ValidationError):
            TaskId(value)

    def test_rejects_a_non_string_non_uuid(self) -> None:
        with pytest.raises(ValidationError):
            TaskId(42)  # type: ignore[arg-type]

    def test_different_kinds_are_never_equal(self) -> None:
        """Types carry meaning: the same UUID as a task and an execution are different things."""
        shared = uuid.uuid4()
        assert TaskId(shared) != ExecutionId(shared)

    def test_different_kinds_do_not_collide_in_a_set(self) -> None:
        shared = uuid.uuid4()
        assert len({TaskId(shared), ExecutionId(shared)}) == 2

    def test_equality_with_an_unrelated_type_is_not_an_error(self) -> None:
        assert TaskId.generate() != "some string"

    def test_orders_by_creation_time(self) -> None:
        earlier = TaskId.generate(timestamp_ms=1_000_000_000_000)
        later = TaskId.generate(timestamp_ms=1_000_000_001_000)
        assert earlier < later

    def test_exposes_the_embedded_creation_hint(self) -> None:
        stamp = 1_700_000_000_000
        assert TaskId.generate(timestamp_ms=stamp).created_at_ms == stamp

    def test_creation_hint_is_absent_for_other_uuid_versions(self) -> None:
        """A v4 identifier carries no timestamp, and must not pretend otherwise."""
        assert TaskId(uuid.uuid4()).created_at_ms is None

    def test_round_trips_through_primitive(self) -> None:
        original = TaskId.generate()
        assert TaskId.from_primitive(original.to_primitive()) == original

    def test_repr_is_unambiguous(self) -> None:
        identifier = TaskId.generate()
        assert repr(identifier) == f"TaskId({str(identifier)!r})"

    def test_identifiers_encode_no_hierarchy(self) -> None:
        """Encoding owner or environment would make those attributes unchangeable."""
        identifier = str(TaskId.generate())
        assert identifier.count("_") == 1
