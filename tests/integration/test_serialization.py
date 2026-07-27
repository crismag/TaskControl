"""Portable bundles: exact round-trips, schema conformance, and secret safety.

Wave 1's acceptance criterion is that ``YAML -> domain -> YAML`` is stable and
byte-identical for the shipped examples. A definition kept in version control must produce
a clean diff when, and only when, it actually changed.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

from taskcontrol.adapters.serialization import (
    TaskBundle,
    dump_schema,
    dump_yaml,
    load_yaml,
    task_bundle_schema,
)
from taskcontrol.common.errors import ValidationError
from taskcontrol.domain.common import (
    Duration,
    OwnerId,
    RevisionNumber,
    SecretReference,
    TaskId,
    TaskRevisionId,
    UtcTimestamp,
)
from taskcontrol.domain.execution import TimeoutPolicy
from taskcontrol.domain.tasks import (
    ActionSpecification,
    EnvironmentBinding,
    ExecutionControls,
    ExecutorType,
    Task,
    TaskRevision,
)

pytestmark = pytest.mark.integration

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = REPOSITORY_ROOT / "examples"
EXPORTED_SCHEMA = REPOSITORY_ROOT / "schemas" / "task-bundle-v1.json"

EXAMPLE_FILES = sorted(EXAMPLES.glob("*.yaml"))

CREATED = UtcTimestamp(datetime(2026, 7, 27, 9, 0, tzinfo=UTC))
OWNER = OwnerId.generate()


def a_bundle(*, publish: bool = False, secret: bool = False) -> TaskBundle:
    """Build a bundle for tests."""
    task = Task.create(name="Daily Report", owner_id=OWNER, created_by=OWNER, created_at=CREATED)
    environment = (
        (EnvironmentBinding("TOKEN", secret=SecretReference.parse("env://API_TOKEN")),)
        if secret
        else (EnvironmentBinding("REGION", value="eu-west-1"),)
    )
    revision = TaskRevision(
        revision_id=TaskRevisionId.generate(),
        task_id=task.task_id,
        revision_number=RevisionNumber.first(),
        action=ActionSpecification(
            executor_type=ExecutorType.SHELL,
            entrypoint="/usr/bin/bash",
            arguments=("/opt/tasks/report.sh",),
            environment=environment,
        ),
        created_at=CREATED,
        created_by=OWNER,
        controls=ExecutionControls(timeout=TimeoutPolicy(run_timeout=Duration(600))),
    )
    if publish:
        revision = revision.publish(published_by=OWNER, published_at=CREATED)
        task = task.activate_revision(revision.revision_id, updated_by=OWNER, updated_at=CREATED)
    return TaskBundle(task=task, revision=revision)


class TestExamplesExist:
    def test_two_examples_are_shipped(self) -> None:
        assert len(EXAMPLE_FILES) >= 2, "Wave 1 ships at least two runnable examples"

    def test_the_schema_is_exported(self) -> None:
        assert EXPORTED_SCHEMA.is_file()


class TestRoundTrip:
    @pytest.mark.parametrize("path", EXAMPLE_FILES, ids=lambda path: path.name)
    def test_examples_round_trip_byte_identically(self, path: Path) -> None:
        """The acceptance criterion: re-serialising an example changes nothing."""
        original = path.read_text(encoding="utf-8")
        assert dump_yaml(load_yaml(original)) == original

    @pytest.mark.parametrize("path", EXAMPLE_FILES, ids=lambda path: path.name)
    def test_examples_load_into_equal_domain_objects(self, path: Path) -> None:
        bundle = load_yaml(path.read_text(encoding="utf-8"))
        assert load_yaml(dump_yaml(bundle)) == bundle

    def test_a_draft_round_trips(self) -> None:
        bundle = a_bundle()
        assert load_yaml(dump_yaml(bundle)) == bundle

    def test_a_published_bundle_round_trips_with_its_digest(self) -> None:
        bundle = a_bundle(publish=True)
        restored = load_yaml(dump_yaml(bundle))
        assert restored.revision.content_digest == bundle.revision.content_digest

    def test_the_digest_survives_serialisation(self) -> None:
        """A digest that changed on a round-trip would break deployment integrity."""
        bundle = a_bundle(publish=True)
        restored = load_yaml(dump_yaml(bundle))
        assert restored.revision.compute_digest() == bundle.revision.compute_digest()

    def test_a_secret_reference_round_trips(self) -> None:
        bundle = a_bundle(secret=True)
        restored = load_yaml(dump_yaml(bundle))
        assert restored.revision.action.secret_references == (
            SecretReference.parse("env://API_TOKEN"),
        )


class TestSecretSafety:
    def test_no_example_contains_a_plausible_secret_value(self) -> None:
        """Examples are copied by users. A secret in one would be copied too."""
        for path in EXAMPLE_FILES:
            text = path.read_text(encoding="utf-8")
            for line in text.splitlines():
                lowered = line.lower()
                if any(marker in lowered for marker in ("password", "token", "secret", "api_key")):
                    assert "secret:" in line or "name:" in line, (
                        f"{path.name} may embed a secret value: {line.strip()!r}"
                    )

    def test_a_secret_bundle_carries_only_the_reference(self) -> None:
        rendered = dump_yaml(a_bundle(secret=True))
        assert "env://API_TOKEN" in rendered
        assert "value:" not in rendered.split("environment:")[1].split("stdin_policy")[0]


class TestSchemaConformance:
    def test_the_schema_itself_is_valid(self) -> None:
        Draft202012Validator.check_schema(task_bundle_schema())

    @pytest.mark.parametrize("path", EXAMPLE_FILES, ids=lambda path: path.name)
    def test_examples_conform_to_the_schema(self, path: Path) -> None:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        errors = sorted(
            Draft202012Validator(task_bundle_schema()).iter_errors(data),
            key=lambda error: error.path,
        )
        assert not errors, "\n".join(f"{list(error.path)}: {error.message}" for error in errors)

    def test_the_exported_schema_matches_the_code(self) -> None:
        """Guards against the published contract drifting from what the code accepts."""
        assert EXPORTED_SCHEMA.read_text(encoding="utf-8") == dump_schema()

    def test_the_schema_enumerates_current_executor_types(self) -> None:
        schema = task_bundle_schema()
        executors = schema["properties"]["revision"]["properties"]["action"]["properties"][
            "executor_type"
        ]["enum"]
        assert "shell" in executors
        assert "python" in executors

    def test_the_schema_is_exported_deterministically(self) -> None:
        assert dump_schema() == dump_schema()

    def test_the_schema_rejects_an_unknown_field(self) -> None:
        """`additionalProperties: false` is what makes a typo visible."""
        data = yaml.safe_load(EXAMPLE_FILES[0].read_text(encoding="utf-8"))
        data["task"]["nonsense_field"] = "x"
        assert list(Draft202012Validator(task_bundle_schema()).iter_errors(data))


class TestLoadingErrors:
    def test_rejects_invalid_yaml(self) -> None:
        with pytest.raises(ValidationError) as caught:
            load_yaml("kind: [unclosed")
        assert "parser_error" in caught.value.details

    def test_rejects_empty_input(self) -> None:
        with pytest.raises(ValidationError):
            load_yaml("")

    def test_rejects_a_document_of_the_wrong_kind(self) -> None:
        with pytest.raises(ValidationError) as caught:
            load_yaml("kind: SomethingElse\nschema_version: '1.0'\n")
        assert caught.value.details["expected_kind"] == "TaskBundle"

    def test_rejects_an_unsupported_schema_version(self) -> None:
        text = dump_yaml(a_bundle()).replace("schema_version: '1.0'", "schema_version: '9.0'")
        with pytest.raises(ValidationError) as caught:
            load_yaml(text)
        assert caught.value.details["bundle_schema_version"] == "9.0"

    def test_rejects_a_missing_section(self) -> None:
        with pytest.raises(ValidationError) as caught:
            load_yaml("kind: TaskBundle\nschema_version: '1.0'\n")
        assert caught.value.details["missing_key"] == "task"

    def test_rejects_a_revision_belonging_to_another_task(self) -> None:
        bundle = a_bundle()
        with pytest.raises(ValidationError):
            TaskBundle(
                task=bundle.task,
                revision=TaskRevision(
                    revision_id=TaskRevisionId.generate(),
                    task_id=TaskId.generate(),
                    revision_number=RevisionNumber.first(),
                    action=bundle.revision.action,
                    created_at=CREATED,
                    created_by=OWNER,
                ),
            )

    def test_yaml_loading_is_safe(self) -> None:
        """A task definition is untrusted input; the full loader constructs objects."""
        dangerous = (
            "kind: TaskBundle\n"
            "schema_version: '1.0'\n"
            "task: !!python/object/apply:os.system ['echo pwned']\n"
        )
        with pytest.raises(ValidationError):
            load_yaml(dangerous)


class TestExportedArtefacts:
    def test_the_exported_schema_is_valid_json(self) -> None:
        json.loads(EXPORTED_SCHEMA.read_text(encoding="utf-8"))

    @pytest.mark.parametrize("path", EXAMPLE_FILES, ids=lambda path: path.name)
    def test_every_example_publishes_or_explains_itself(self, path: Path) -> None:
        """An example is documentation: it must carry a change summary."""
        bundle = load_yaml(path.read_text(encoding="utf-8"))
        assert bundle.revision.change_summary
        assert bundle.task.description
