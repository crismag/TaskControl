"""Guards for the R1 compatibility findings.

These exist so a correction made once is not quietly undone. Each maps to a finding in
`development/reviews/R1_WAVE3_COMPATIBILITY.md`.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from taskcontrol.adapters.locking import NoOverlapProtection, ProcessLocalOverlapLock
from taskcontrol.domain.common import TaskId
from taskcontrol.domain.tasks import ActivationPolicy, ExecutionControls
from taskcontrol.ports.lock import OverlapLock

SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src" / "taskcontrol"


class TestNoProductionOverlapClaim:
    """Finding 1 — the process-local lock guards nothing across activations."""

    def test_no_production_module_constructs_the_process_local_lock(self) -> None:
        """Wiring it would let a caller believe FORBID was honoured when it is not."""
        offenders: list[str] = []
        for path in sorted(SOURCE_ROOT.rglob("*.py")):
            if path.parent.name == "locking":
                continue  # The adapter package defines and exports it; that is its job.
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and ast.unparse(node.func).endswith(
                    "ProcessLocalOverlapLock"
                ):
                    offenders.append(f"{path.relative_to(SOURCE_ROOT)}:{node.lineno}")

        assert not offenders, (
            "ProcessLocalOverlapLock is a test double and provides no protection between "
            "cron activations. Constructed at: " + ", ".join(offenders)
        )

    def test_the_wired_implementation_states_it_protects_nothing(self) -> None:
        assert "not yet implemented" in NoOverlapProtection().scope_description

    def test_the_wired_implementation_never_refuses(self) -> None:
        """Honest: it grants and says so, rather than pretending to guard."""
        lock = NoOverlapProtection()
        task_id = TaskId.generate()
        assert lock.try_acquire(task_id, owner="a") is not None
        assert lock.try_acquire(task_id, owner="b") is not None

    def test_it_satisfies_the_port(self) -> None:
        assert isinstance(NoOverlapProtection(), OverlapLock)

    def test_the_test_double_still_satisfies_the_port(self) -> None:
        """It remains useful for in-process port tests; only production use is barred."""
        assert isinstance(ProcessLocalOverlapLock(), OverlapLock)


class TestNoInternalSchedulerLanguage:
    """The superseded direction must not survive in source documentation."""

    def test_no_module_claims_an_internal_scheduler(self) -> None:
        offenders = [
            str(path.relative_to(SOURCE_ROOT))
            for path in sorted(SOURCE_ROOT.rglob("*.py"))
            if "internal scheduler" in path.read_text(encoding="utf-8").lower()
        ]
        assert not offenders, f"superseded direction still asserted in: {offenders}"


class TestActivationPolicy:
    """Finding from ADR 0024 — the behaviour must never be accidental."""

    def test_the_default_is_strict(self) -> None:
        """An operator who has not considered this gets the auditable behaviour."""
        assert ExecutionControls().activation_policy is ActivationPolicy.REQUIRE_CONTROL_STATE

    def test_strict_does_not_execute_without_control_state(self) -> None:
        assert not ActivationPolicy.REQUIRE_CONTROL_STATE.executes_without_control_state

    def test_journal_mode_executes_without_control_state(self) -> None:
        assert ActivationPolicy.CONTINUE_WITH_LOCAL_JOURNAL.executes_without_control_state

    def test_it_round_trips(self) -> None:
        controls = ExecutionControls(activation_policy=ActivationPolicy.CONTINUE_WITH_LOCAL_JOURNAL)
        restored = ExecutionControls.from_primitive(controls.to_primitive())
        assert restored.activation_policy is ActivationPolicy.CONTINUE_WITH_LOCAL_JOURNAL

    def test_an_older_bundle_without_the_field_gets_the_strict_default(self) -> None:
        """Schema 1.0 bundles predate the field and must not silently gain availability."""
        restored = ExecutionControls.from_primitive({"overlap": "forbid", "max_concurrent": 1})
        assert restored.activation_policy is ActivationPolicy.REQUIRE_CONTROL_STATE

    @pytest.mark.parametrize("policy", list(ActivationPolicy))
    def test_every_policy_serialises_lower_snake_case(self, policy: ActivationPolicy) -> None:
        assert policy.value == policy.value.lower()
        assert " " not in policy.value
