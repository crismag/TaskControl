"""Value objects: every rule has a negative case.

A value object that accepts an invalid value is worse than no value object, because
downstream code stops checking.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from taskcontrol.common.errors import ErrorCode, ValidationError
from taskcontrol.domain.common import (
    ContentDigest,
    Duration,
    RevisionNumber,
    SchemaVersion,
    SecretReference,
    Slug,
    TimeZoneName,
    UtcTimestamp,
)
from taskcontrol.domain.common.values import MAX_DURATION_SECONDS, SLUG_MAX_LENGTH


class TestUtcTimestamp:
    def test_accepts_an_aware_datetime(self) -> None:
        moment = datetime(2026, 7, 27, 6, 0, tzinfo=UTC)
        assert UtcTimestamp(moment).value == moment

    def test_normalises_other_offsets_to_utc(self) -> None:
        tokyo = datetime(2026, 7, 27, 15, 0, tzinfo=timezone(timedelta(hours=9)))
        assert UtcTimestamp(tokyo).value == datetime(2026, 7, 27, 6, 0, tzinfo=UTC)

    def test_rejects_a_naive_datetime(self) -> None:
        """A naive datetime has no defined instant; assuming UTC is how DST bugs start."""
        with pytest.raises(ValidationError) as caught:
            UtcTimestamp(datetime(2026, 7, 27, 6, 0))  # noqa: DTZ001
        assert caught.value.code is ErrorCode.VALIDATION_FAILED

    def test_rejects_a_non_datetime(self) -> None:
        with pytest.raises(ValidationError):
            UtcTimestamp("2026-07-27T06:00:00Z")  # type: ignore[arg-type]

    def test_round_trips_through_primitive(self) -> None:
        original = UtcTimestamp(datetime(2026, 7, 27, 6, 0, tzinfo=UTC))
        assert UtcTimestamp.from_primitive(original.to_primitive()) == original

    def test_from_primitive_rejects_unparseable_text(self) -> None:
        with pytest.raises(ValidationError):
            UtcTimestamp.from_primitive("not-a-timestamp")

    def test_from_primitive_rejects_a_string_without_an_offset(self) -> None:
        with pytest.raises(ValidationError):
            UtcTimestamp.from_primitive("2026-07-27T06:00:00")

    def test_from_primitive_rejects_a_non_string(self) -> None:
        with pytest.raises(ValidationError):
            UtcTimestamp.from_primitive(1753588800)

    def test_orders_chronologically(self) -> None:
        earlier = UtcTimestamp(datetime(2026, 7, 27, 6, 0, tzinfo=UTC))
        later = UtcTimestamp(datetime(2026, 7, 27, 7, 0, tzinfo=UTC))
        assert earlier < later


class TestDuration:
    def test_holds_whole_seconds(self) -> None:
        assert Duration(90).seconds == 90

    def test_builds_from_parts(self) -> None:
        assert Duration.of(hours=1, minutes=30).seconds == 5400

    def test_rejects_a_negative_span(self) -> None:
        with pytest.raises(ValidationError):
            Duration(-1)

    def test_rejects_a_float(self) -> None:
        """Sub-second precision would imply an accuracy the scheduler does not offer."""
        with pytest.raises(ValidationError):
            Duration(1.5)  # type: ignore[arg-type]

    def test_rejects_a_bool(self) -> None:
        """bool is a subclass of int; accepting True as one second would be nonsense."""
        with pytest.raises(ValidationError):
            Duration(True)

    def test_rejects_an_implausibly_large_span(self) -> None:
        with pytest.raises(ValidationError):
            Duration(MAX_DURATION_SECONDS + 1)

    def test_zero_is_valid_and_flagged(self) -> None:
        assert Duration(0).is_zero

    def test_converts_to_timedelta(self) -> None:
        assert Duration(90).as_timedelta() == timedelta(seconds=90)

    @pytest.mark.parametrize(
        ("seconds", "rendered"),
        [(0, "0s"), (45, "45s"), (90, "1m30s"), (3600, "1h"), (5430, "1h30m30s")],
    )
    def test_renders_readably(self, seconds: int, rendered: str) -> None:
        assert str(Duration(seconds)) == rendered

    def test_from_primitive_rejects_a_non_integer(self) -> None:
        with pytest.raises(ValidationError):
            Duration.from_primitive("60")


class TestTimeZoneName:
    def test_accepts_a_known_zone(self) -> None:
        assert TimeZoneName("Europe/London").name == "Europe/London"

    def test_rejects_an_unknown_zone(self) -> None:
        with pytest.raises(ValidationError) as caught:
            TimeZoneName("Mars/Olympus_Mons")
        assert caught.value.details["timezone"] == "Mars/Olympus_Mons"

    def test_rejects_an_empty_name(self) -> None:
        with pytest.raises(ValidationError):
            TimeZoneName("   ")

    def test_rejects_a_fixed_offset_string(self) -> None:
        """An offset cannot survive a DST transition, so it is not a time zone."""
        with pytest.raises(ValidationError):
            TimeZoneName("+01:00")

    def test_loads_zone_info_for_conversion(self) -> None:
        london = TimeZoneName("Europe/London")
        summer = datetime(2026, 7, 27, 12, 0, tzinfo=london.zone_info())
        winter = datetime(2026, 1, 27, 12, 0, tzinfo=london.zone_info())
        assert summer.utcoffset() != winter.utcoffset(), "DST must actually apply"

    def test_from_primitive_rejects_a_non_string(self) -> None:
        with pytest.raises(ValidationError):
            TimeZoneName.from_primitive(0)


class TestSlug:
    @pytest.mark.parametrize("value", ["daily-report", "sync", "a1-b2-c3"])
    def test_accepts_valid_slugs(self, value: str) -> None:
        assert Slug(value).value == value

    @pytest.mark.parametrize(
        "value",
        [
            "",
            "Daily-Report",
            "daily_report",
            "daily report",
            "-leading",
            "trailing-",
            "double--hyphen",
            "../etc/passwd",
            "report;rm -rf /",
            "réport",
        ],
    )
    def test_rejects_unsafe_or_malformed_slugs(self, value: str) -> None:
        """Slugs reach URLs, filenames, and CLI arguments, so the bar is deliberately high."""
        with pytest.raises(ValidationError):
            Slug(value)

    def test_rejects_an_over_long_slug(self) -> None:
        with pytest.raises(ValidationError):
            Slug("a" * (SLUG_MAX_LENGTH + 1))

    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("Daily Settlement Report", "daily-settlement-report"),
            ("  Sync   Reference Data!  ", "sync-reference-data"),
            ("Report (v2)", "report-v2"),
        ],
    )
    def test_derives_from_a_display_name(self, name: str, expected: str) -> None:
        assert Slug.from_display_name(name).value == expected

    def test_derivation_fails_when_nothing_usable_remains(self) -> None:
        with pytest.raises(ValidationError):
            Slug.from_display_name("!!! ???")


class TestRevisionNumber:
    def test_starts_at_one(self) -> None:
        assert RevisionNumber.first().value == 1

    def test_increments(self) -> None:
        assert RevisionNumber(3).next().value == 4

    def test_rejects_zero_and_below(self) -> None:
        """There is no revision zero: an uncreated revision has no number."""
        for value in (0, -1):
            with pytest.raises(ValidationError):
                RevisionNumber(value)

    def test_rejects_a_non_integer(self) -> None:
        with pytest.raises(ValidationError):
            RevisionNumber("2")  # type: ignore[arg-type]

    def test_orders_numerically(self) -> None:
        assert RevisionNumber(2) < RevisionNumber(10)


class TestContentDigest:
    def test_computes_a_digest_over_canonical_content(self) -> None:
        digest = ContentDigest.of_canonical({"b": 1, "a": 2})
        assert digest.value.startswith("sha256:")
        assert len(digest.value) == len("sha256:") + 64

    def test_key_order_does_not_change_the_digest(self) -> None:
        """Reproducibility across machines is the whole purpose of the digest."""
        assert ContentDigest.of_canonical({"a": 1, "b": 2}) == ContentDigest.of_canonical(
            {"b": 2, "a": 1}
        )

    def test_different_content_produces_a_different_digest(self) -> None:
        assert ContentDigest.of_canonical({"a": 1}) != ContentDigest.of_canonical({"a": 2})

    def test_rejects_unserialisable_content(self) -> None:
        with pytest.raises(ValidationError):
            ContentDigest.of_canonical({"when": object()})

    def test_rejects_nan_which_is_not_canonical(self) -> None:
        with pytest.raises(ValidationError):
            ContentDigest.of_canonical({"value": float("nan")})

    @pytest.mark.parametrize("value", ["", "sha256:short", "md5:" + "a" * 64, "a" * 64])
    def test_rejects_a_malformed_digest(self, value: str) -> None:
        with pytest.raises(ValidationError):
            ContentDigest(value)

    def test_short_form_is_for_display(self) -> None:
        assert len(ContentDigest.of_canonical({"a": 1}).short) == 12


class TestSchemaVersion:
    def test_parses_major_minor(self) -> None:
        assert SchemaVersion.parse("1.4") == SchemaVersion(1, 4)

    @pytest.mark.parametrize("text", ["1", "1.2.3", "v1.2", "", "x.y"])
    def test_rejects_malformed_versions(self, text: str) -> None:
        with pytest.raises(ValidationError):
            SchemaVersion.parse(text)

    def test_rejects_negative_parts(self) -> None:
        with pytest.raises(ValidationError):
            SchemaVersion(-1, 0)

    def test_same_major_and_older_minor_is_compatible(self) -> None:
        assert SchemaVersion(1, 0).is_compatible_with(SchemaVersion(1, 3))

    def test_newer_minor_is_not_compatible(self) -> None:
        """A consumer cannot read content that uses fields it does not know about."""
        assert not SchemaVersion(1, 4).is_compatible_with(SchemaVersion(1, 3))

    def test_different_major_is_never_compatible(self) -> None:
        assert not SchemaVersion(2, 0).is_compatible_with(SchemaVersion(1, 9))

    def test_orders_by_major_then_minor(self) -> None:
        assert SchemaVersion(1, 9) < SchemaVersion(2, 0)


class TestSecretReference:
    def test_parses_a_reference(self) -> None:
        reference = SecretReference.parse("env://DATABASE_PASSWORD")
        assert reference.provider == "env"
        assert reference.path == "DATABASE_PASSWORD"
        assert reference.version is None

    def test_parses_a_versioned_reference(self) -> None:
        assert SecretReference.parse("vault://prod/db#7").version == "7"

    @pytest.mark.parametrize(
        "text",
        [
            "",
            "DATABASE_PASSWORD",
            "env:/DATABASE_PASSWORD",
            "://path",
            "env://",
            "env://path#",
            "ENV://PATH",
            "env://path with spaces",
        ],
    )
    def test_rejects_malformed_references(self, text: str) -> None:
        with pytest.raises(ValidationError):
            SecretReference.parse(text)

    def test_rejects_a_non_string(self) -> None:
        with pytest.raises(ValidationError):
            SecretReference.parse(None)  # type: ignore[arg-type]

    def test_round_trips(self) -> None:
        for text in ("env://TOKEN", "vault://prod/db#7"):
            assert SecretReference.parse(text).to_primitive() == text

    def test_holds_no_secret_value(self) -> None:
        """The type exists so it is safe to persist, log, digest, and display."""
        reference = SecretReference.parse("env://DATABASE_PASSWORD")
        rendered = f"{reference} {reference.to_primitive()} {reference!r}"
        assert "DATABASE_PASSWORD" in rendered, "the locator is not secret"
        assert not hasattr(reference, "resolve"), "the domain never resolves a secret"
