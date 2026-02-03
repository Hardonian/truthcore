"""Verdict Aggregator v3 - Governance-Enhanced (M7).

Multi-engine weighted ship/no-ship decision system with full governance.

Example:
    >>> from truthcore.verdict import aggregate_verdict
    >>> from pathlib import Path
    >>> result = aggregate_verdict(
    ...     [Path("readiness.json"), Path("policy_findings.json")],
    ...     mode="main",
    ...     expected_engines=["readiness", "policy"],
    ...     run_id="build-123",
    ... )
    >>> print(result.verdict.value)
    'NO_SHIP'  # Not optimistic by default!
"""

# Import unified enums from severity module
from truthcore.severity import Category, Severity
from truthcore.verdict.aggregator import VerdictAggregator, aggregate_verdict
from truthcore.verdict.models import (
    CategoryBreakdown,
    EngineContribution,
    Mode,
    VerdictResult,
    VerdictStatus,
    VerdictThresholds,
    WeightedFinding,
)

# Backwards compatibility alias
SeverityLevel = Severity

__all__ = [
    # Models
    "VerdictResult",
    "VerdictStatus",
    "VerdictThresholds",
    "WeightedFinding",
    "EngineContribution",
    "CategoryBreakdown",
    "Mode",
    # Unified enums (from severity module)
    "Severity",
    "SeverityLevel",  # Backwards compatibility
    "Category",
    # Aggregator
    "VerdictAggregator",
    "aggregate_verdict",
]

# Optional CLI imports (requires click)
try:
    from truthcore.verdict.cli import generate_verdict_for_judge, register_verdict_commands

    __all__.extend(["register_verdict_commands", "generate_verdict_for_judge"])
except ImportError:
    pass  # CLI not available without click
