"""Verdict Aggregator v2 (M6).

Multi-engine weighted ship/no-ship decision system.

Example:
    >>> from truthcore.verdict import aggregate_verdict
    >>> from pathlib import Path
    >>> result = aggregate_verdict(
    ...     [Path("readiness.json"), Path("policy_findings.json")],
    ...     mode="main",
    ... )
    >>> print(result.verdict.value)
    'SHIP'
"""

from truthcore.verdict.aggregator import VerdictAggregator, aggregate_verdict
from truthcore.verdict.cli import generate_verdict_for_judge, register_verdict_commands
from truthcore.verdict.models import (
    Category,
    CategoryBreakdown,
    EngineContribution,
    Mode,
    SeverityLevel,
    VerdictResult,
    VerdictStatus,
    VerdictThresholds,
    WeightedFinding,
)

__all__ = [
    # Models
    "VerdictResult",
    "VerdictStatus",
    "VerdictThresholds",
    "WeightedFinding",
    "EngineContribution",
    "CategoryBreakdown",
    "SeverityLevel",
    "Category",
    "Mode",
    # Aggregator
    "VerdictAggregator",
    "aggregate_verdict",
    # CLI
    "register_verdict_commands",
    "generate_verdict_for_judge",
]
