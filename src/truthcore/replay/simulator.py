"""Counterfactual simulation engine for "what-if" analysis.

Allows running simulations with modified policies, thresholds, invariants,
and other configuration without changing the raw inputs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from truthcore.manifest import normalize_timestamp
from truthcore.replay.bundle import ReplayBundle
from truthcore.replay.diff import DeterministicDiff, DiffComputer
from truthcore.verdict import SeverityLevel
from truthcore.verdict.aggregator import VerdictAggregator
from truthcore.verdict.models import (
    Category,
    Mode,
    VerdictResult,
    VerdictStatus,
    VerdictThresholds,
)


@dataclass
class SimulationChanges:
    """Changes to apply for counterfactual simulation.
    
    Attributes:
        thresholds: Threshold overrides (e.g., {"max_highs": 10})
        severity_weights: Weight overrides (e.g., {"HIGH": 100.0})
        category_weights: Category weight overrides
        category_limits: Category point limits
        disabled_engines: List of engine IDs to disable
        disabled_rules: List of rule IDs to disable
        suppressions: Findings to suppress with reason and expiry
    """
    thresholds: dict[str, Any] = field(default_factory=dict)
    severity_weights: dict[str, float] = field(default_factory=dict)
    category_weights: dict[str, float] = field(default_factory=dict)
    category_limits: dict[str, int] = field(default_factory=dict)
    disabled_engines: list[str] = field(default_factory=list)
    disabled_rules: list[str] = field(default_factory=list)
    suppressions: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_yaml(cls, path: Path) -> SimulationChanges:
        """Load changes from YAML file.
        
        Example YAML:
            thresholds:
              max_highs: 10
              max_total_points: 200
            severity_weights:
              HIGH: 75.0
            category_weights:
              security: 3.0
            disabled_engines:
              - "ui_geometry"
            suppressions:
              - rule_id: "UI_001"
                reason: "Known issue, fix in progress"
                expiry: "2026-02-01T00:00:00Z"
        """
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return cls(
            thresholds=data.get("thresholds", {}),
            severity_weights=data.get("severity_weights", {}),
            category_weights=data.get("category_weights", {}),
            category_limits=data.get("category_limits", {}),
            disabled_engines=data.get("disabled_engines", []),
            disabled_rules=data.get("disabled_rules", []),
            suppressions=data.get("suppressions", []),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "thresholds": self.thresholds,
            "severity_weights": self.severity_weights,
            "category_weights": self.category_weights,
            "category_limits": self.category_limits,
            "disabled_engines": self.disabled_engines,
            "disabled_rules": self.disabled_rules,
            "suppressions": self.suppressions,
        }


@dataclass
class SimulationResult:
    """Result of a counterfactual simulation.
    
    Attributes:
        success: Whether simulation completed successfully
        bundle: The replay bundle used
        output_dir: Directory containing simulation outputs
        changes: The changes applied
        original_verdict: Original verdict (if available)
        simulated_verdict: New verdict with changes applied
        diff: Diff between original and simulated
        timestamp: When simulation occurred
        errors: Any errors encountered
    """
    success: bool
    bundle: ReplayBundle
    output_dir: Path
    changes: SimulationChanges
    original_verdict: VerdictResult | None = None
    simulated_verdict: VerdictResult | None = None
    diff: DeterministicDiff | None = None
    timestamp: str = field(default_factory=lambda: normalize_timestamp())
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "timestamp": self.timestamp,
            "bundle": self.bundle.to_dict(),
            "output_dir": str(self.output_dir),
            "changes": self.changes.to_dict(),
            "original_verdict": self.original_verdict.to_dict() if self.original_verdict else None,
            "simulated_verdict": self.simulated_verdict.to_dict() if self.simulated_verdict else None,
            "verdict_changed": (
                self.original_verdict.verdict != self.simulated_verdict.verdict
                if self.original_verdict and self.simulated_verdict
                else None
            ),
            "errors": self.errors,
        }

    def to_markdown(self) -> str:
        """Generate markdown report."""
        status = "✅ SUCCESS" if self.success else "❌ FAILED"

        lines = [
            "# Simulation Report",
            "",
            f"**Status:** {status}",
            f"**Timestamp:** {self.timestamp}",
            "",
        ]

        # Changes applied
        lines.extend([
            "## Changes Applied",
            "",
        ])

        if self.changes.thresholds:
            lines.append("### Thresholds")
            for key, value in self.changes.thresholds.items():
                lines.append(f"- `{key}`: `{value}`")
            lines.append("")

        if self.changes.severity_weights:
            lines.extend(["### Severity Weights", ""])
            for key, value in self.changes.severity_weights.items():
                lines.append(f"- `{key}`: `{value}`")
            lines.append("")

        if self.changes.category_weights:
            lines.extend(["### Category Weights", ""])
            for key, value in self.changes.category_weights.items():
                lines.append(f"- `{key}`: `{value}`")
            lines.append("")

        if self.changes.disabled_engines:
            lines.extend(["### Disabled Engines", ""])
            for engine in self.changes.disabled_engines:
                lines.append(f"- `{engine}`")
            lines.append("")

        if self.changes.disabled_rules:
            lines.extend(["### Disabled Rules", ""])
            for rule in self.changes.disabled_rules:
                lines.append(f"- `{rule}`")
            lines.append("")

        if self.changes.suppressions:
            lines.extend(["### Suppressions", ""])
            for sup in self.changes.suppressions:
                lines.append(f"- `{sup['rule_id']}`: {sup['reason']}")
            lines.append("")

        # Verdict comparison
        if self.original_verdict and self.simulated_verdict:
            lines.extend([
                "## Verdict Comparison",
                "",
                "| Metric | Original | Simulated |",
                "|--------|----------|-----------|",
            ])

            orig = self.original_verdict
            sim = self.simulated_verdict

            lines.append(f"| Verdict | {orig.verdict.value} | {sim.verdict.value} |")
            lines.append(f"| Total Findings | {orig.total_findings} | {sim.total_findings} |")
            lines.append(f"| Blockers | {orig.blockers} | {sim.blockers} |")
            lines.append(f"| Highs | {orig.highs} | {sim.highs} |")
            lines.append(f"| Total Points | {orig.total_points} | {sim.total_points} |")
            lines.append("")

            if orig.verdict != sim.verdict:
                lines.extend([
                    f"**⚠️ VERDICT CHANGED: {orig.verdict.value} → {sim.verdict.value}**",
                    "",
                ])

        if self.errors:
            lines.extend(["## Errors", ""])
            for error in self.errors:
                lines.append(f"- ❌ {error}")
            lines.append("")

        return "\n".join(lines)


class SimulationEngine:
    """Engine for counterfactual simulation.
    
    This runs "what-if" scenarios by modifying thresholds, weights,
    and other configuration without changing the raw inputs.
    """

    def __init__(self):
        """Initialize simulation engine."""
        pass

    def simulate(
        self,
        bundle: ReplayBundle,
        output_dir: Path,
        changes: SimulationChanges,
        mode: str | None = None,
        profile: str | None = None,
    ) -> SimulationResult:
        """Run a counterfactual simulation.
        
        Args:
            bundle: The replay bundle to simulate
            output_dir: Directory for simulation outputs
            changes: Changes to apply for the simulation
            mode: Override mode (uses bundle mode if None)
            profile: Override profile (uses bundle profile if None)
            
        Returns:
            SimulationResult with comparison details
        """
        output_dir = Path(output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        result = SimulationResult(
            success=True,
            bundle=bundle,
            output_dir=output_dir,
            changes=changes,
        )

        try:
            # Determine mode and profile
            sim_mode = mode or bundle.manifest.profile or "pr"
            sim_profile = profile or bundle.manifest.profile or "default"

            # Load original verdict if available
            result.original_verdict = self._load_original_verdict(bundle)

            # Run simulation with changes
            result.simulated_verdict = self._run_simulation(
                bundle, output_dir, sim_mode, sim_profile, changes
            )

            # Compute diff
            if result.original_verdict:
                diff_computer = DiffComputer()
                result.diff = diff_computer.compute(
                    result.original_verdict.to_dict(),
                    result.simulated_verdict.to_dict(),
                )

            # Write outputs
            result.simulated_verdict.write_json(output_dir / "verdict.json")
            result.simulated_verdict.write_markdown(output_dir / "verdict.md")

        except Exception as e:
            result.success = False
            result.errors.append(str(e))

        return result

    def _load_original_verdict(self, bundle: ReplayBundle) -> VerdictResult | None:
        """Load the original verdict from bundle outputs."""
        verdict_path = bundle.outputs_dir / "verdict.json"
        if not verdict_path.exists():
            return None

        try:
            with open(verdict_path, encoding="utf-8") as f:
                data = json.load(f)

            # Reconstruct VerdictResult from dict
            verdict = VerdictResult(
                verdict=VerdictStatus(data["verdict"]),
                version=data.get("version", "2.0"),
                timestamp=data.get("timestamp", ""),
                mode=Mode(data.get("mode", "pr")),
                profile=data.get("profile"),
                total_findings=data.get("summary", {}).get("total_findings", 0),
                blockers=data.get("summary", {}).get("blockers", 0),
                highs=data.get("summary", {}).get("highs", 0),
                mediums=data.get("summary", {}).get("mediums", 0),
                lows=data.get("summary", {}).get("lows", 0),
                total_points=data.get("summary", {}).get("total_points", 0),
                inputs=data.get("inputs", []),
            )

            return verdict
        except Exception:
            return None

    def _run_simulation(
        self,
        bundle: ReplayBundle,
        output_dir: Path,
        mode: str,
        profile: str,
        changes: SimulationChanges,
    ) -> VerdictResult:
        """Run simulation with applied changes."""
        # Create modified thresholds
        mode_enum = Mode(mode)
        thresholds = VerdictThresholds.for_mode(mode_enum)

        # Apply threshold changes
        for key, value in changes.thresholds.items():
            if hasattr(thresholds, key):
                setattr(thresholds, key, value)

        # Apply severity weight changes
        for key, value in changes.severity_weights.items():
            try:
                severity = SeverityLevel(key.upper())
                thresholds.severity_weights[severity] = value
            except ValueError:
                pass

        # Apply category weight changes
        for key, value in changes.category_weights.items():
            try:
                category = Category(key.lower())
                thresholds.category_weights[category] = value
            except ValueError:
                pass

        # Apply category limit changes
        for key, value in changes.category_limits.items():
            try:
                category = Category(key.lower())
                thresholds.category_limits[category] = value
            except ValueError:
                pass

        # Create aggregator with modified thresholds
        aggregator = VerdictAggregator(thresholds=thresholds)

        # Load findings from bundle
        input_files: list[Path] = []
        for output_file in bundle.get_output_files():
            if output_file.suffix == ".json":
                # Skip if from disabled engine
                if any(engine in str(output_file) for engine in changes.disabled_engines):
                    continue
                input_files.append(output_file)

        for input_file in bundle.get_input_files():
            if input_file.suffix == ".json":
                input_files.append(input_file)

        # Add findings
        for path in input_files:
            try:
                aggregator.add_findings_from_file(path)
            except Exception:
                pass

        # Filter out suppressed findings
        if changes.suppressions:
            suppressed_rules = {s["rule_id"] for s in changes.suppressions}
            aggregator.findings = [
                f for f in aggregator.findings
                if f.rule_id not in suppressed_rules
            ]

        # Filter out findings from disabled engines
        if changes.disabled_engines:
            aggregator.findings = [
                f for f in aggregator.findings
                if f.source_engine not in changes.disabled_engines
                and f.tool not in changes.disabled_engines
            ]

        # Filter out findings from disabled rules
        if changes.disabled_rules:
            aggregator.findings = [
                f for f in aggregator.findings
                if f.rule_id not in changes.disabled_rules
            ]

        # Aggregate with modified thresholds
        return aggregator.aggregate(mode=mode_enum, profile=profile)


class SimulationReporter:
    """Generates reports from simulation results."""

    def write_reports(
        self,
        result: SimulationResult,
        output_dir: Path,
    ) -> dict[str, Path]:
        """Write simulation reports.
        
        Args:
            result: Simulation result to report
            output_dir: Directory for report files
            
        Returns:
            Dict of report type to path
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        paths = {}

        # Write JSON report
        json_path = output_dir / "simulation_report.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, indent=2, sort_keys=True)
        paths["json"] = json_path

        # Write Markdown report
        md_path = output_dir / "simulation_report.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(result.to_markdown())
        paths["markdown"] = md_path

        # Write simulation diff JSON
        if result.diff:
            diff_path = output_dir / "simulation_diff.json"
            with open(diff_path, "w", encoding="utf-8") as f:
                json.dump(result.diff.to_dict(), f, indent=2, sort_keys=True)
            paths["diff"] = diff_path

        return paths
