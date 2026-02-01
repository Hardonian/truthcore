"""Verdict Aggregator v3 - Governance-Enhanced Models.

Unified verdict model with full governance:
- Type-safe severity levels (unified with findings)
- Category assignment audit trails
- Override governance with expiration
- Temporal tracking for chronic issues
- Engine health checks
- Configurable category weights with review cycles
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from truthcore.severity import (
    Category,
    CategoryAssignment,
    CategoryWeightConfig,
    EngineHealth,
    Override,
    Severity,
    TemporalFinding,
)


class VerdictStatus(Enum):
    """Final verdict status."""

    SHIP = "SHIP"
    NO_SHIP = "NO_SHIP"
    CONDITIONAL = "CONDITIONAL"
    DEGRADED = "DEGRADED"  # New: Some engines failed health checks


class Mode(Enum):
    """Execution modes."""

    PR = "pr"
    MAIN = "main"
    RELEASE = "release"


@dataclass
class WeightedFinding:
    """A finding with weight and scoring info."""

    finding_id: str
    tool: str
    severity: Severity  # Now using unified Severity
    category: Category  # Now using unified Category
    message: str
    location: str | None = None
    rule_id: str | None = None

    # Weighted scoring
    weight: float = 1.0
    points: int = 0

    # Governance tracking
    category_assignment: CategoryAssignment | None = None
    temporal_record: TemporalFinding | None = None
    escalated_from: Severity | None = None  # If escalated due to chronicity

    # Source info
    source_file: str | None = None
    source_engine: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "finding_id": self.finding_id,
            "tool": self.tool,
            "severity": self.severity.value,
            "category": self.category.value,
            "message": self.message,
            "location": self.location,
            "rule_id": self.rule_id,
            "weight": self.weight,
            "points": self.points,
            "source_file": self.source_file,
            "source_engine": self.source_engine,
        }
        if self.category_assignment:
            result["category_assignment"] = self.category_assignment.to_dict()
        if self.temporal_record:
            result["temporal_record"] = self.temporal_record.to_dict()
        if self.escalated_from:
            result["escalated_from"] = self.escalated_from.value
        return result


@dataclass
class EngineContribution:
    """Contribution from a single engine with health status."""

    engine_id: str
    findings_count: int = 0
    blockers: int = 0
    highs: int = 0
    mediums: int = 0
    lows: int = 0
    points_contributed: int = 0
    passed: bool = True  # Engine-level pass/fail
    health: EngineHealth | None = None  # Health check status

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "engine_id": self.engine_id,
            "findings_count": self.findings_count,
            "blockers": self.blockers,
            "highs": self.highs,
            "mediums": self.mediums,
            "lows": self.lows,
            "points_contributed": self.points_contributed,
            "passed": self.passed,
        }
        if self.health:
            result["health"] = self.health.to_dict()
        return result


@dataclass
class CategoryBreakdown:
    """Breakdown by category with governance."""

    category: Category
    weight: float
    findings_count: int = 0
    points_contributed: int = 0
    max_allowed: int | None = None
    assignments: list[CategoryAssignment] = field(default_factory=list)  # Audit trail

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "category": self.category.value,
            "weight": self.weight,
            "findings_count": self.findings_count,
            "points_contributed": self.points_contributed,
            "max_allowed": self.max_allowed,
            "assignments": [a.to_dict() for a in self.assignments],
        }


@dataclass
class VerdictThresholds:
    """Thresholds for verdict determination with governance.

    Different modes have different thresholds:
    - PR: More lenient, allows some issues
    - MAIN: Balanced, moderate tolerance
    - RELEASE: Strict, minimal issues allowed
    """

    mode: Mode

    # Blockers are always immediate fail
    max_blockers: int = 0

    # High severity limits
    max_highs: int = 0

    # Points-based thresholds
    max_total_points: int = 100

    # Category-specific limits (points)
    category_limits: dict[Category, int] = field(default_factory=dict)

    # Weight configuration (governed, not frozen)
    category_weight_config: CategoryWeightConfig = field(default_factory=CategoryWeightConfig.create_default)

    # Severity weights
    severity_weights: dict[Severity, float] = field(
        default_factory=lambda: {
            Severity.BLOCKER: float("inf"),
            Severity.HIGH: 50.0,
            Severity.MEDIUM: 10.0,
            Severity.LOW: 1.0,
            Severity.INFO: 0.0,
        }
    )

    # Engine health requirements
    require_all_engines_healthy: bool = True  # Fail if any expected engine is unhealthy
    min_engines_required: int = 1  # Minimum number of engines that must run

    # Temporal escalation settings
    escalation_threshold_occurrences: int = 3  # Escalate after N occurrences
    escalation_severity_bump: bool = True  # Bump severity when escalating

    @classmethod
    def for_mode(cls, mode: Mode | str) -> VerdictThresholds:
        """Create thresholds for a specific mode."""
        if isinstance(mode, str):
            mode = Mode(mode)

        if mode == Mode.PR:
            # PR mode: lenient, allows some issues
            return cls(
                mode=mode,
                max_blockers=0,
                max_highs=5,
                max_total_points=150,
                category_limits={
                    Category.SECURITY: 100,
                    Category.BUILD: 50,
                },
                require_all_engines_healthy=False,  # More lenient
                min_engines_required=1,
            )

        elif mode == Mode.MAIN:
            # Main mode: balanced
            return cls(
                mode=mode,
                max_blockers=0,
                max_highs=2,
                max_total_points=75,
                category_limits={
                    Category.SECURITY: 50,
                    Category.BUILD: 25,
                    Category.TYPES: 30,
                },
                require_all_engines_healthy=True,
                min_engines_required=2,
            )

        else:  # RELEASE
            # Release mode: strict
            return cls(
                mode=mode,
                max_blockers=0,
                max_highs=0,
                max_total_points=20,
                category_limits={
                    Category.SECURITY: 0,
                    Category.PRIVACY: 0,
                    Category.BUILD: 10,
                    Category.TYPES: 10,
                },
                require_all_engines_healthy=True,
                min_engines_required=3,
            )

    def get_category_weight(self, category: Category) -> float:
        """Get weight for a category from governed config."""
        return self.category_weight_config.get_weight(category)

    def get_severity_weight(self, severity: Severity) -> float:
        """Get weight for a severity level."""
        return self.severity_weights.get(severity, 1.0)

    def to_dict(self) -> dict[str, Any]:
        """Convert thresholds to dictionary."""
        return {
            "mode": self.mode.value,
            "max_blockers": self.max_blockers,
            "max_highs": self.max_highs,
            "max_total_points": self.max_total_points,
            "category_limits": {k.value: v for k, v in self.category_limits.items()},
            "severity_weights": {k.value: v for k, v in self.severity_weights.items()},
            "category_weight_config": self.category_weight_config.to_dict(),
            "require_all_engines_healthy": self.require_all_engines_healthy,
            "min_engines_required": self.min_engines_required,
            "escalation_threshold_occurrences": self.escalation_threshold_occurrences,
            "escalation_severity_bump": self.escalation_severity_bump,
        }


@dataclass
class VerdictResult:
    """Complete verdict result with full governance.

    REVERSIBILITY GUARANTEES:
    - Stores category_weights_used snapshot for point-in-time reconciliation
    - Links to weight_version to identify when weights changed
    - Enables accurate comparison of verdicts across time
    """

    # Basic info
    verdict: VerdictStatus
    version: str = "3.1"  # Bumped for reversibility enhancements
    timestamp: str = ""
    mode: Mode = Mode.PR

    # Inputs processed
    inputs: list[str] = field(default_factory=list)

    # Summary counts
    total_findings: int = 0
    blockers: int = 0
    highs: int = 0
    mediums: int = 0
    lows: int = 0
    total_points: int = 0

    # Engine contributions with health
    engines: list[EngineContribution] = field(default_factory=list)
    engines_failed: int = 0
    engines_expected: int = 0
    engines_ran: int = 0

    # Category breakdowns with audit trails
    categories: list[CategoryBreakdown] = field(default_factory=list)

    # Top findings (for explainability)
    top_findings: list[WeightedFinding] = field(default_factory=list)

    # Reasons for decision
    ship_reasons: list[str] = field(default_factory=list)
    no_ship_reasons: list[str] = field(default_factory=list)
    degradation_reasons: list[str] = field(default_factory=list)

    # Configuration used
    thresholds: VerdictThresholds | None = None

    # Governance records
    overrides_applied: list[Override] = field(default_factory=list)
    temporal_escalations: list[TemporalFinding] = field(default_factory=list)
    category_assignments: list[CategoryAssignment] = field(default_factory=list)

    # REVERSIBILITY: Point-in-time weight tracking
    category_weights_used: dict[str, float] = field(default_factory=dict)  # Snapshot of weights at verdict time
    weight_version: str = "1.0.0"  # Links to CategoryWeightConfig.config_version

    # Optional: profile used
    profile: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "verdict": self.verdict.value,
            "version": self.version,
            "timestamp": self.timestamp,
            "mode": self.mode.value,
            "profile": self.profile,
            "summary": {
                "total_findings": self.total_findings,
                "blockers": self.blockers,
                "highs": self.highs,
                "mediums": self.mediums,
                "lows": self.lows,
                "total_points": self.total_points,
            },
            "engine_health": {
                "engines_expected": self.engines_expected,
                "engines_ran": self.engines_ran,
                "engines_failed": self.engines_failed,
            },
            "inputs": self.inputs,
            "engines": [e.to_dict() for e in self.engines],
            "categories": [c.to_dict() for c in self.categories],
            "top_findings": [f.to_dict() for f in self.top_findings[:10]],
            "reasoning": {
                "ship_reasons": self.ship_reasons,
                "no_ship_reasons": self.no_ship_reasons,
                "degradation_reasons": self.degradation_reasons,
            },
            "governance": {
                "overrides_applied": [o.to_dict() for o in self.overrides_applied],
                "temporal_escalations": [t.to_dict() for t in self.temporal_escalations],
                "category_assignments": [c.to_dict() for c in self.category_assignments],
                "category_weights_used": self.category_weights_used,
                "weight_version": self.weight_version,
            },
            "thresholds": self.thresholds.to_dict() if self.thresholds else None,
        }

    def to_markdown(self) -> str:
        """Generate markdown report."""
        lines = [
            "# Verdict Report",
            "",
            f"**Verdict:** {self._format_verdict()}",
            f"**Mode:** {self.mode.value}",
            f"**Profile:** {self.profile or 'default'}",
            f"**Timestamp:** {self.timestamp}",
            f"**Version:** {self.version}",
            "",
            "## Summary",
            "",
            f"- **Total Findings:** {self.total_findings}",
            f"- **Blockers:** {self.blockers}",
            f"- **High Severity:** {self.highs}",
            f"- **Medium Severity:** {self.mediums}",
            f"- **Low Severity:** {self.lows}",
            f"- **Total Points:** {self.total_points}",
            "",
            "## Engine Health",
            "",
            f"- **Expected:** {self.engines_expected}",
            f"- **Ran:** {self.engines_ran}",
            f"- **Failed:** {self.engines_failed}",
            "",
        ]

        # Engine breakdown with health
        if self.engines:
            lines.extend([
                "## Engine Contributions",
                "",
                "| Engine | Findings | Blockers | Highs | Points | Pass | Health |",
                "|--------|----------|----------|-------|--------|------|--------|",
            ])
            for engine in sorted(self.engines, key=lambda e: -e.points_contributed):
                status = "✅" if engine.passed else "❌"
                health = "✅" if engine.health and engine.health.is_healthy() else "❌"
                lines.append(
                    f"| {engine.engine_id} | {engine.findings_count} | "
                    f"{engine.blockers} | {engine.highs} | "
                    f"{engine.points_contributed} | {status} | {health} |"
                )
            lines.append("")

        # Category breakdown
        if self.categories:
            lines.extend([
                "## Category Breakdown",
                "",
                "| Category | Weight | Findings | Points | Limit | Assignments |",
                "|----------|--------|----------|--------|-------|-------------|",
            ])
            for cat in sorted(self.categories, key=lambda c: -c.points_contributed):
                limit_str = str(cat.max_allowed) if cat.max_allowed is not None else "∞"
                lines.append(
                    f"| {cat.category.value} | {cat.weight:.1f} | "
                    f"{cat.findings_count} | {cat.points_contributed} | "
                    f"{limit_str} | {len(cat.assignments)} |"
                )
            lines.append("")

        # Governance section
        if self.overrides_applied or self.temporal_escalations:
            lines.extend([
                "## Governance",
                "",
            ])

            if self.overrides_applied:
                lines.extend([
                    "### Overrides Applied",
                    "",
                ])
                for override in self.overrides_applied:
                    lines.append(f"- **{override.scope}** (approved by {override.approved_by})")
                    lines.append(f"  - Reason: {override.reason}")
                    lines.append(f"  - Expires: {override.expires_at}")
                lines.append("")

            if self.temporal_escalations:
                lines.extend([
                    "### Chronic Issues Escalated",
                    "",
                ])
                for temp in self.temporal_escalations:
                    lines.append(
                        f"- **{temp.finding_fingerprint}** "
                        f"({temp.occurrences} occurrences)"
                    )
                    lines.append(f"  - First seen: {temp.first_seen}")
                    lines.append(f"  - Escalation: {temp.escalation_reason}")
                lines.append("")

        # Top findings
        if self.top_findings:
            lines.extend([
                "## Top Findings",
                "",
            ])
            for i, finding in enumerate(self.top_findings[:10], 1):
                severity_emoji = self._severity_emoji(finding.severity)
                lines.append(
                    f"{i}. {severity_emoji} **[{finding.severity.value}]** " f"{finding.message}"
                )
                if finding.location:
                    lines.append(f"   - Location: `{finding.location}`")
                if finding.rule_id:
                    lines.append(f"   - Rule: `{finding.rule_id}`")
                lines.append(f"   - Points: {finding.points} (weight: {finding.weight:.1f})")
                if finding.escalated_from:
                    lines.append(
                        f"   - ⬆️ Escalated from {finding.escalated_from.value} (chronic issue)"
                    )
                lines.append("")

        # Reasons
        if self.ship_reasons and self.verdict == VerdictStatus.SHIP:
            lines.extend([
                "## Ship Reasons",
                "",
            ])
            for reason in self.ship_reasons:
                lines.append(f"- ✅ {reason}")
            lines.append("")

        if self.no_ship_reasons:
            lines.extend([
                "## No-Ship Reasons",
                "",
            ])
            for reason in self.no_ship_reasons:
                lines.append(f"- ❌ {reason}")
            lines.append("")

        if self.degradation_reasons:
            lines.extend([
                "## Degradation Reasons",
                "",
            ])
            for reason in self.degradation_reasons:
                lines.append(f"- ⚠️ {reason}")
            lines.append("")

        lines.append("---")
        lines.append(f"*Generated by Truth Core v{self.version}*")

        return "\n".join(lines)

    def _format_verdict(self) -> str:
        """Format verdict with emoji."""
        if self.verdict == VerdictStatus.SHIP:
            return "🚢 SHIP"
        elif self.verdict == VerdictStatus.NO_SHIP:
            return "🚫 NO_SHIP"
        elif self.verdict == VerdictStatus.DEGRADED:
            return "⚠️ DEGRADED"
        else:
            return "⚠️ CONDITIONAL"

    def _severity_emoji(self, severity: Severity) -> str:
        """Get emoji for severity."""
        return {
            Severity.BLOCKER: "🔴",
            Severity.HIGH: "🟠",
            Severity.MEDIUM: "🟡",
            Severity.LOW: "🔵",
            Severity.INFO: "⚪",
        }.get(severity, "⚪")

    def write_json(self, path: Path) -> None:
        """Write verdict to JSON file."""
        import json

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, sort_keys=True)

    def write_markdown(self, path: Path) -> None:
        """Write verdict to Markdown file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_markdown())
