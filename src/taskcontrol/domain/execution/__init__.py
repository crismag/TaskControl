"""The execution domain: lifecycle, outcomes, results, and control policies.

ADR 0016 fixes the vocabulary here. Nothing outside this package may define an execution
status vocabulary.
"""

from __future__ import annotations

from taskcontrol.domain.execution.results import (
    BackoffStrategy,
    OverlapPolicy,
    ProcessResult,
    RetryPolicy,
    TerminationCause,
    TerminationMode,
    TimeoutPolicy,
)
from taskcontrol.domain.execution.vocabulary import (
    ExecutionOutcome,
    ExecutionState,
    ReasonCode,
    ReasonCodes,
    RetryEligibility,
    assert_legal_transition,
    is_legal_transition,
)

__all__ = [
    "BackoffStrategy",
    "ExecutionOutcome",
    "ExecutionState",
    "OverlapPolicy",
    "ProcessResult",
    "ReasonCode",
    "ReasonCodes",
    "RetryEligibility",
    "RetryPolicy",
    "TerminationCause",
    "TerminationMode",
    "TimeoutPolicy",
    "assert_legal_transition",
    "is_legal_transition",
]
