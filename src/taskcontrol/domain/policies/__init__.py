"""Pure decision policies.

Functions here take stored inputs and return a decision. No I/O, no clock, no randomness —
so a decision made today can be re-derived and explained from the same record tomorrow.
"""

from __future__ import annotations

from taskcontrol.domain.policies.classification import (
    Classification,
    ExpectationEvidence,
    RetryDecision,
    classify_process_result,
    decide_retry,
)

__all__ = [
    "Classification",
    "ExpectationEvidence",
    "RetryDecision",
    "classify_process_result",
    "decide_retry",
]
