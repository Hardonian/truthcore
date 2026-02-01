"""Verdict Aggregator v2 - Models (M6).

Unified verdict model for multi-engine weighted ship/no-ship decisions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class VerdictStatus(Enum):
    """Final verdict status."""
    SHIP = "SHIP"
    NO_SHIP = "NO_SHIP"
    CONDITIONAL = "CONDITIONAL"


class SeverityLevel(Enum):
    """Severity levels for findings."""
    BLOCKER = "BLOCKER"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class Category(Enum):
    """Finding categories."""
    UI = "ui"
    BUILD = "build"
    TYPES = "types"
    SECURITY = "security"
    PRIVACY = "privacy"
    FINANCE = "finance"
    AGENT = "agent"
    KNOWLEDGE = "knowledge"
    GENERAL = "general"


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
    severity: SeverityLevel
    category: Category
    message: str
    location: str | None = None
    rule_id: str | None = None

    # Weighted scoring
    weight: float = 1.0
    points: int = 0

    # Source info
    source_file: str | None = None
    source_engine: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
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


@dataclass
class EngineContribution:
    """Contribution from a single engine."""

    engine_id: str
    findings_count: int = 0
    blockers: int = 0
    highs: int = 0
    mediums: int = 0
    lows: int = 0
    points_contributed: int = 0
    passed: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine_id": self.engine_id,
            "findings_count": self.findings_count,
            "blockers": self.blockers,
            "highs": self.highs,
            "mediums": self.mediums,
            "lows": self.lows,
            "points_contributed": self.points_contributed,
            "passed": self.passed,
        }


@dataclass
class CategoryBreakdown:
    """Breakdown by category."""

    category: Category
    weight: float
    findings_count: int = 0
    points_contributed: int = 0
    max_allowed: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category.value,
            "weight": self.weight,
            "findings_count": self.findings_count,
            "points_contributed": self.points_contributed,
            "max_allowed": self.max_allowed,
        }


@dataclass
class VerdictThresholds:
    """Thresholds for verdict determination.
    
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
    max_highs_with_override: int = 3

    # Points-based thresholds
    max_total_points: int = 100

    # Category-specific limits (points)
    category_limits: dict[Category, int] = field(default_factory=dict)

    # Weight multipliers per severity
    severity_weights: dict[SeverityLevel, float] = field(default_factory=lambda: {
        SeverityLevel.BLOCKER: float('inf'),
        SeverityLevel.HIGH: 50.0,
        SeverityLevel.MEDIUM: 10.0,
        SeverityLevel.LOW: 1.0,
        SeverityLevel.INFO: 0.0,
    })

    # Default category weights
    category_weights: dict[Category, float] = field(default_factory=lambda: {
        Category.SECURITY: 2.0,
        Category.PRIVACY: 2.0,
        Category.FINANCE: 1.5,
        Category.BUILD: 1.5,
        Category.TYPES: 1.2,
        Category.UI: 1.0,
        Category.AGENT: 1.0,
        Category.KNOWLEDGE: 1.0,
        Category.GENERAL: 1.0,
    })

    @classmethod
    def for_mode(cls, mode: Mode | str) -> "VerdictThresholds":
        """Create thresholds for a specific mode."""
        if isinstance(mode, str):
            mode = Mode(mode)

        if mode == Mode.PR:
            # PR mode: lenient, allows some issues
            return cls(
                mode=mode,
                max_blockers=0,
                max_highs=5,
                max_highs_with_override=10,
                max_total_points=150,
                category_limits={
                    Category.SECURITY: 100,
                    Category.BUILD: 50,
                },
            )

        elif mode == Mode.MAIN:
            # Main mode: balanced
            return cls(
                mode=mode,
                max_blockers=0,
                max_highs=2,
                max_highs_with_override=5,
                max_total_points=75,
                category_limits={
                    Category.SECURITY: 50,
                    Category.BUILD: 25,
                    Category.TYPES: 30,
                },
            )

        else:  # RELEASE
            # Release mode: strict
            return cls(
                mode=mode,
                max_blockers=0,
                max_highs=0,
                max_highs_with_override=1,
                max_total_points=20,
                category_limits={
                    Category.SECURITY: 0,
                    Category.PRIVACY: 0,
                    Category.BUILD: 10,
                    Category.TYPES: 10,
                },
            )

    def get_category_weight(self, category: Category) -> float:
        """Get weight for a category."""
        return self.category_weights.get(category, 1.0)

    def get_severity_weight(self, severity: SeverityLevel) -> float:
        """Get weight for a severity level."""
        return self.severity_weights.get(severity, 1.0)

    def to_dict(self) -> dict[str, Any]:
        """Convert thresholds to dictionary."""
        return {
            "mode": self.mode.value,
            "max_blockers": self.max_blockers,
            "max_highs": self.max_highs,
            "max_highs_with_override": self.max_highs_with_override,
            "max_total_points": self.max_total_points,
            "category_limits": {k.value: v for k, v in self.category_limits.items()},
            "severity_weights": {k.value: v for k, v in self.severity_weights.items()},
            "category_weights": {k.value: v for k, v in self.category_weights.items()},
        }


@dataclass
class VerdictResult:
    """Complete verdict result."""

    # Basic info
    verdict: VerdictStatus
    version: str = "2.0"
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

    # Engine contributions
    engines: list[EngineContribution] = field(default_factory=list)

    # Category breakdowns
    categories: list[CategoryBreakdown] = field(default_factory=list)

    # Top findings (for explainability)
    top_findings: list[WeightedFinding] = field(default_factory=list)

    # Reasons for decision
    ship_reasons: list[str] = field(default_factory=list)
    no_ship_reasons: list[str] = field(default_factory=list)

    # Configuration used
    thresholds: VerdictThresholds | None = None

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
            "inputs": self.inputs,
            "engines": [e.to_dict() for e in self.engines],
            "categories": [c.to_dict() for c in self.categories],
            "top_findings": [f.to_dict() for f in self.top_findings[:10]],
            "reasoning": {
                "ship_reasons": self.ship_reasons,
                "no_ship_reasons": self.no_ship_reasons,
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
        ]

        # Engine breakdown
        if self.engines:
            lines.extend([
                "## Engine Contributions",
                "",
                "| Engine | Findings | Blockers | Highs | Points | Status |",
                "|--------|----------|----------|-------|--------|--------|",
            ])
            for engine in sorted(self.engines, key=lambda e: -e.points_contributed):
                status = "✅ Pass" if engine.passed else "❌ Fail"
                lines.append(
                    f"| {engine.engine_id} | {engine.findings_count} | "
                    f"{engine.blockers} | {engine.highs} | "
                    f"{engine.points_contributed} | {status} |"
                )
            lines.append("")

        # Category breakdown
        if self.categories:
            lines.extend([
                "## Category Breakdown",
                "",
                "| Category | Weight | Findings | Points | Limit |",
                "|----------|--------|----------|--------|-------|",
            ])
            for cat in sorted(self.categories, key=lambda c: -c.points_contributed):
                limit_str = str(cat.max_allowed) if cat.max_allowed is not None else "∞"
                lines.append(
                    f"| {cat.category.value} | {cat.weight:.1f} | "
                    f"{cat.findings_count} | {cat.points_contributed} | {limit_str} |"
                )
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
                    f"{i}. {severity_emoji} **[{finding.severity.value}]** "
                    f"{finding.message}"
                )
                if finding.location:
                    lines.append(f"   - Location: `{finding.location}`")
                if finding.rule_id:
                    lines.append(f"   - Rule: `{finding.rule_id}`")
                lines.append(f"   - Points: {finding.points} (weight: {finding.weight:.1f})")
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

        # Add SVG chart if there are findings
        if self.total_findings > 0:
            lines.extend([
                "## Visual Breakdown",
                "",
                self._generate_svg_chart(),
                "",
            ])

        lines.append("---")
        lines.append(f"*Generated by Truth Core v{self.version}*")

        return "\n".join(lines)

    def _format_verdict(self) -> str:
        """Format verdict with emoji."""
        if self.verdict == VerdictStatus.SHIP:
            return "🚢 SHIP"
        elif self.verdict == VerdictStatus.NO_SHIP:
            return "🚫 NO_SHIP"
        else:
            return "⚠️ CONDITIONAL"

    def _severity_emoji(self, severity: SeverityLevel) -> str:
        """Get emoji for severity."""
        return {
            SeverityLevel.BLOCKER: "🔴",
            SeverityLevel.HIGH: "🟠",
            SeverityLevel.MEDIUM: "🟡",
            SeverityLevel.LOW: "🔵",
            SeverityLevel.INFO: "⚪",
        }.get(severity, "⚪")

    def _generate_svg_chart(self) -> str:
        """Generate simple inline SVG pie chart of findings by severity."""
        total = self.blockers + self.highs + self.mediums + self.lows
        if total == 0:
            return "No findings to display."

        # Colors for each severity
        colors = {
            "blockers": "#dc2626",  # red
            "highs": "#ea580c",     # orange
            "mediums": "#ca8a04",   # yellow
            "lows": "#2563eb",      # blue
        }

        # Calculate angles
        angles = {}
        start_angle = 0
        for key, count in [
            ("blockers", self.blockers),
            ("highs", self.highs),
            ("mediums", self.mediums),
            ("lows", self.lows),
        ]:
            if count > 0:
                angle = (count / total) * 360
                angles[key] = (start_angle, start_angle + angle)
                start_angle += angle

        # Generate SVG
        svg_parts = [
            '<svg width="400" height="200" xmlns="http://www.w3.org/2000/svg">',
            '  <!-- Legend -->',
            '  <text x="220" y="30" font-family="sans-serif" font-size="14" font-weight="bold">Findings by Severity</text>',
        ]

        legend_y = 55
        legend_items = [
            ("Blockers", self.blockers, colors["blockers"]),
            ("High", self.highs, colors["highs"]),
            ("Medium", self.mediums, colors["mediums"]),
            ("Low", self.lows, colors["lows"]),
        ]

        for label, count, color in legend_items:
            if count > 0:
                svg_parts.extend([
                    f'  <rect x="220" y="{legend_y}" width="12" height="12" fill="{color}"/>',
                    f'  <text x="238" y="{legend_y + 10}" font-family="sans-serif" font-size="12">{label}: {count}</text>',
                ])
                legend_y += 20

        svg_parts.extend([
            '</svg>',
        ])

        return "\n".join(svg_parts)

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
