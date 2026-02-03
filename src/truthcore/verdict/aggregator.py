"""Verdict Aggregator v3 - Governance-Enhanced (M7).

Aggregates findings from multiple engines with full governance:
- Category assignment audit trails
- Override tracking and validation
- Temporal awareness for chronic issues
- Engine health checks
- NOT optimistic by default - requires explicit health signals
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

from truthcore.manifest import normalize_timestamp
from truthcore.severity import (
    Category,
    CategoryAssignment,
    EngineHealth,
    Override,
    Severity,
    TemporalFinding,
)
from truthcore.verdict.models import (
    CategoryBreakdown,
    EngineContribution,
    Mode,
    VerdictResult,
    VerdictStatus,
    VerdictThresholds,
    WeightedFinding,
)


class VerdictAggregator:
    """Aggregates findings from multiple engines with full governance."""

    def __init__(
        self,
        thresholds: VerdictThresholds | None = None,
        expected_engines: list[str] | None = None,
        temporal_store_path: Path | None = None,
    ):
        """Initialize aggregator.

        Args:
            thresholds: Threshold configuration (uses PR mode defaults if None)
            expected_engines: List of engine IDs that are expected to run
            temporal_store_path: Path to temporal findings store (for chronicity tracking)
        """
        self.thresholds = thresholds or VerdictThresholds.for_mode(Mode.PR)
        self.findings: list[WeightedFinding] = []
        self.expected_engines = expected_engines or []
        self.engine_health: dict[str, EngineHealth] = {}
        self.overrides: list[Override] = []
        self.temporal_store_path = temporal_store_path
        self.temporal_findings: dict[str, TemporalFinding] = {}
        self.category_assignments: list[CategoryAssignment] = []

        # Load temporal store if provided
        if self.temporal_store_path and self.temporal_store_path.exists():
            self._load_temporal_store()

    def _load_temporal_store(self) -> None:
        """Load temporal findings from store."""
        if not self.temporal_store_path:
            return
        try:
            with open(self.temporal_store_path, encoding="utf-8") as f:
                data = json.load(f)
                for item in data.get("temporal_findings", []):
                    tf = TemporalFinding.from_dict(item)
                    self.temporal_findings[tf.finding_fingerprint] = tf
        except (FileNotFoundError, json.JSONDecodeError):
            pass  # Start fresh if store is missing or corrupt

    def _save_temporal_store(self) -> None:
        """Save temporal findings to store."""
        if not self.temporal_store_path:
            return
        self.temporal_store_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.temporal_store_path, "w", encoding="utf-8") as f:
            json.dump(
                {"temporal_findings": [tf.to_dict() for tf in self.temporal_findings.values()]},
                f,
                indent=2,
            )

    def register_override(self, override: Override) -> None:
        """Register an override for use in verdict computation.

        Args:
            override: The override to register

        Raises:
            ValueError: If override is invalid or expired
        """
        if not override.is_valid():
            raise ValueError(f"Override {override.override_id} is not valid (expired or already used)")
        self.overrides.append(override)

    def register_engine_health(self, health: EngineHealth) -> None:
        """Register health status for an engine.

        Args:
            health: Health check record for the engine
        """
        self.engine_health[health.engine_id] = health

    def compute_finding_fingerprint(self, rule_id: str, location: str | None) -> str:
        """Compute stable fingerprint for temporal tracking.

        Args:
            rule_id: The rule that triggered the finding
            location: Location string

        Returns:
            SHA-256 hash fingerprint
        """
        key = f"{rule_id}:{location or 'unknown'}"
        return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]

    def add_finding(
        self,
        finding_id: str,
        tool: str,
        severity: Severity | str,
        category: Category | str,
        message: str,
        location: str | None = None,
        rule_id: str | None = None,
        source_file: str | None = None,
        source_engine: str | None = None,
        assigned_by: str = "system",
        assignment_reason: str = "auto-categorized",
        run_id: str | None = None,
    ) -> WeightedFinding:
        """Add a finding with governance tracking.

        Args:
            finding_id: Unique identifier for this finding
            tool: Tool that reported the finding
            severity: Severity level
            category: Category (requires governance)
            message: Human-readable message
            location: Optional location info
            rule_id: Optional rule identifier
            source_file: Optional source file
            source_engine: Optional source engine
            assigned_by: Who assigned the category (for audit)
            assignment_reason: Why this category was chosen (for audit)
            run_id: Current run ID for temporal tracking

        Returns:
            The weighted finding with computed points and governance records
        """
        # Convert string enums
        if isinstance(severity, str):
            severity = Severity.from_string(severity)
        if isinstance(category, str):
            category = Category.from_string(category)

        # Create category assignment record
        category_assignment = CategoryAssignment(
            finding_id=finding_id,
            category=category,
            assigned_by=assigned_by,
            assigned_at=datetime.now(UTC).isoformat(),
            reason=assignment_reason,
            confidence=1.0 if assigned_by != "system" else 0.8,
            reviewed=assigned_by != "system",
            reviewer=assigned_by if assigned_by != "system" else None,
            reviewed_at=datetime.now(UTC).isoformat() if assigned_by != "system" else None,
        )
        self.category_assignments.append(category_assignment)

        # Temporal tracking
        fingerprint = self.compute_finding_fingerprint(rule_id or finding_id, location)
        temporal_record = None
        escalated_from = None

        if fingerprint in self.temporal_findings:
            temporal_record = self.temporal_findings[fingerprint]
            temporal_record.record_occurrence(run_id or "unknown", severity.value)

            # Check for escalation
            if (
                temporal_record.should_escalate(self.thresholds.escalation_threshold_occurrences)
                and self.thresholds.escalation_severity_bump
            ):
                escalated_from = severity
                # Escalate severity
                if severity == Severity.LOW:
                    severity = Severity.MEDIUM
                elif severity == Severity.MEDIUM:
                    severity = Severity.HIGH
                elif severity == Severity.HIGH:
                    severity = Severity.BLOCKER

                temporal_record.escalate(
                    f"Chronic issue: appeared {temporal_record.occurrences} times, "
                    f"escalated from {escalated_from.value} to {severity.value}"
                )
        else:
            # First occurrence
            temporal_record = TemporalFinding(
                finding_fingerprint=fingerprint,
                first_seen=datetime.now(UTC).isoformat(),
                last_seen=datetime.now(UTC).isoformat(),
                occurrences=1,
                runs_with_finding=[run_id] if run_id else [],
                severity_history=[(datetime.now(UTC).isoformat(), severity.value)],
            )
            self.temporal_findings[fingerprint] = temporal_record

        # Compute weight and points
        category_weight = self.thresholds.get_category_weight(category) if self.thresholds else 1.0
        severity_weight = self.thresholds.get_severity_weight(severity) if self.thresholds else 1.0

        weight = category_weight * (1.0 if severity_weight == float("inf") else severity_weight)

        # Points: severity weight * category weight
        if severity == Severity.BLOCKER:
            points = 1000  # Blockers always fail
        elif severity == Severity.HIGH:
            points = int(50 * category_weight)
        elif severity == Severity.MEDIUM:
            points = int(10 * category_weight)
        elif severity == Severity.LOW:
            points = int(1 * category_weight)
        else:
            points = 0

        finding = WeightedFinding(
            finding_id=finding_id,
            tool=tool,
            severity=severity,
            category=category,
            message=message,
            location=location,
            rule_id=rule_id,
            weight=weight,
            points=points,
            category_assignment=category_assignment,
            temporal_record=temporal_record,
            escalated_from=escalated_from,
            source_file=source_file,
            source_engine=source_engine,
        )

        self.findings.append(finding)
        return finding

    def add_findings_from_json(
        self, data: dict[str, Any], source_file: str | None = None, run_id: str | None = None
    ) -> list[WeightedFinding]:
        """Add findings from a JSON data structure.

        Supports multiple formats with governance tracking.

        Args:
            data: JSON data containing findings
            source_file: Source file path for tracking
            run_id: Current run ID for temporal tracking

        Returns:
            List of weighted findings added
        """
        added = []

        # Try to extract findings from known formats
        findings_list = self._extract_findings_from_data(data)

        for i, item in enumerate(findings_list):
            finding_id = item.get("id") or item.get("finding_id") or f"finding_{i}"

            # Determine severity
            severity_str = item.get("severity", "INFO")
            if isinstance(severity_str, str):
                severity_str = severity_str.upper()
            try:
                severity = Severity.from_string(severity_str)
            except ValueError:
                severity = Severity.INFO

            # Determine category with audit trail
            category_str = item.get("category", "general")
            if isinstance(category_str, str):
                category_str = category_str.lower()
            try:
                category = Category.from_string(category_str)
            except ValueError:
                category = Category.GENERAL

            # Get message
            message = item.get("message") or item.get("description") or item.get("rule") or "Unknown issue"

            # Get location
            location = item.get("location") or item.get("file") or item.get("path")
            if location and item.get("line"):
                location = f"{location}:{item['line']}"

            # Assignment tracking
            assigned_by = item.get("assigned_by", item.get("tool", "system"))
            assignment_reason = item.get("assignment_reason", f"Auto-categorized by {assigned_by}")

            finding = self.add_finding(
                finding_id=finding_id,
                tool=item.get("tool", "unknown"),
                severity=severity,
                category=category,
                message=message,
                location=location,
                rule_id=item.get("rule_id") or item.get("rule"),
                source_file=source_file,
                source_engine=item.get("engine"),
                assigned_by=assigned_by,
                assignment_reason=assignment_reason,
                run_id=run_id,
            )
            added.append(finding)

        return added

    def add_findings_from_file(self, path: Path, run_id: str | None = None) -> list[WeightedFinding]:
        """Add findings from a JSON file.

        Args:
            path: Path to JSON file
            run_id: Current run ID for temporal tracking

        Returns:
            List of weighted findings added

        Raises:
            FileNotFoundError: If file doesn't exist
            json.JSONDecodeError: If file is invalid JSON
        """
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return self.add_findings_from_json(data, source_file=str(path), run_id=run_id)

    def aggregate(
        self,
        mode: Mode | str = Mode.PR,
        profile: str | None = None,
        inputs: list[str] | None = None,
        run_id: str | None = None,
    ) -> VerdictResult:
        """Aggregate all findings and produce a governed verdict.

        NOT OPTIMISTIC BY DEFAULT - requires explicit engine health signals.

        Args:
            mode: Execution mode (pr/main/release)
            profile: Optional profile name
            inputs: List of input file paths processed
            run_id: Current run ID

        Returns:
            Complete verdict result with full governance
        """
        if isinstance(mode, str):
            mode = Mode(mode)

        # Get thresholds for mode
        thresholds = self.thresholds or VerdictThresholds.for_mode(mode)

        # Initialize result
        result = VerdictResult(
            verdict=VerdictStatus.NO_SHIP,  # NOT OPTIMISTIC - starts as NO_SHIP
            timestamp=normalize_timestamp(),
            mode=mode,
            profile=profile,
            inputs=inputs or [],
            thresholds=thresholds,
        )

        # Engine health check - CRITICAL
        engines_expected = len(self.expected_engines)
        engines_ran = sum(1 for h in self.engine_health.values() if h.ran)
        engines_failed = sum(1 for h in self.engine_health.values() if not h.is_healthy())

        result.engines_expected = engines_expected
        result.engines_ran = engines_ran
        result.engines_failed = engines_failed

        # Check minimum engines requirement
        if engines_ran < thresholds.min_engines_required:
            result.no_ship_reasons.append(
                f"Only {engines_ran} engine(s) ran, but {thresholds.min_engines_required} required"
            )

        # Check for unhealthy engines
        for engine_id in self.expected_engines:
            if engine_id not in self.engine_health:
                result.degradation_reasons.append(f"Engine '{engine_id}' expected but no health signal received")
            elif not self.engine_health[engine_id].is_healthy():
                health = self.engine_health[engine_id]
                error_msg = health.error_message or "Unknown error"
                result.degradation_reasons.append(f"Engine '{engine_id}' failed: {error_msg}")

        # Count by severity
        result.total_findings = len(self.findings)
        result.blockers = sum(1 for f in self.findings if f.severity == Severity.BLOCKER)
        result.highs = sum(1 for f in self.findings if f.severity == Severity.HIGH)
        result.mediums = sum(1 for f in self.findings if f.severity == Severity.MEDIUM)
        result.lows = sum(1 for f in self.findings if f.severity == Severity.LOW)

        # Calculate total points
        result.total_points = sum(f.points for f in self.findings)

        # Build engine contributions
        engines_map: dict[str, EngineContribution] = {}
        for finding in self.findings:
            engine_id = finding.source_engine or finding.tool or "unknown"

            if engine_id not in engines_map:
                engines_map[engine_id] = EngineContribution(
                    engine_id=engine_id, health=self.engine_health.get(engine_id)
                )

            engine = engines_map[engine_id]
            engine.findings_count += 1
            engine.points_contributed += finding.points

            if finding.severity == Severity.BLOCKER:
                engine.blockers += 1
            elif finding.severity == Severity.HIGH:
                engine.highs += 1
            elif finding.severity == Severity.MEDIUM:
                engine.mediums += 1
            elif finding.severity == Severity.LOW:
                engine.lows += 1

        # Determine engine pass/fail status (ACTUALLY USED NOW)
        for engine in engines_map.values():
            engine.passed = (
                engine.blockers == 0
                and engine.highs <= thresholds.max_highs
                and engine.points_contributed < thresholds.max_total_points / max(len(engines_map), 1)
            )

        result.engines = list(engines_map.values())

        # Build category breakdowns with audit trails
        categories_map: dict[Category, CategoryBreakdown] = {}
        for finding in self.findings:
            cat = finding.category

            if cat not in categories_map:
                weight = thresholds.get_category_weight(cat)
                max_allowed = thresholds.category_limits.get(cat)
                categories_map[cat] = CategoryBreakdown(
                    category=cat,
                    weight=weight,
                    max_allowed=max_allowed,
                )

            breakdown = categories_map[cat]
            breakdown.findings_count += 1
            breakdown.points_contributed += finding.points
            if finding.category_assignment:
                breakdown.assignments.append(finding.category_assignment)

        result.categories = list(categories_map.values())

        # Sort findings by severity and points for top findings
        severity_order_map = {
            Severity.BLOCKER: 0,
            Severity.HIGH: 1,
            Severity.MEDIUM: 2,
            Severity.LOW: 3,
            Severity.INFO: 4,
        }
        sorted_findings = sorted(
            self.findings,
            key=lambda f: (severity_order_map.get(f.severity, 5), -f.points),
        )
        result.top_findings = sorted_findings

        # Governance records
        result.category_assignments = self.category_assignments
        result.temporal_escalations = [tf for tf in self.temporal_findings.values() if tf.escalated]

        # Determine verdict with governance
        result.verdict, result.ship_reasons, result.no_ship_reasons = self._determine_verdict(result, thresholds)

        # Save temporal store
        self._save_temporal_store()

        return result

    def _determine_verdict(
        self,
        result: VerdictResult,
        thresholds: VerdictThresholds,
    ) -> tuple[VerdictStatus, list[str], list[str]]:
        """Determine the final verdict with full governance.

        NOT OPTIMISTIC - requires explicit passing criteria.

        Args:
            result: Current result with findings counted
            thresholds: Thresholds to apply

        Returns:
            Tuple of (verdict, ship_reasons, no_ship_reasons)
        """
        ship_reasons: list[str] = []
        no_ship_reasons: list[str] = result.no_ship_reasons.copy()  # Preserve existing reasons
        degraded = bool(result.degradation_reasons)

        # Engine health check (CRITICAL - affects verdict)
        if result.engines_failed > 0:
            if thresholds.require_all_engines_healthy:
                no_ship_reasons.append(f"{result.engines_failed} engine(s) failed health check")
            else:
                degraded = True

        # Check if any engine failed its individual criteria
        failed_engines = [e for e in result.engines if not e.passed]
        if failed_engines and thresholds.require_all_engines_healthy:
            engine_names = ", ".join(e.engine_id for e in failed_engines)
            no_ship_reasons.append(f"Engine(s) failed individual criteria: {engine_names}")

        # Check blockers - always fail
        if result.blockers > thresholds.max_blockers:
            no_ship_reasons.append(f"{result.blockers} blocker(s) found (max allowed: {thresholds.max_blockers})")

        # Check high severity with override support
        if result.highs > thresholds.max_highs:
            # Look for valid override
            override_found = None
            for override in self.overrides:
                if override.is_valid() and "max_highs" in override.scope:
                    # Extract override limit
                    try:
                        override_limit = int(override.scope.split(":")[-1].strip())
                        if result.highs <= override_limit:
                            override_found = override
                            break
                    except (ValueError, IndexError):
                        pass

            if override_found:
                # Apply override
                override_found.mark_used(f"verdict_{datetime.now(UTC).timestamp()}")
                result.overrides_applied.append(override_found)
                ship_reasons.append(
                    f"Override applied for {result.highs} high severity issues "
                    f"(approved by {override_found.approved_by})"
                )
            else:
                no_ship_reasons.append(
                    f"{result.highs} high severity issue(s) found (max allowed: {thresholds.max_highs})"
                )

        # Check total points
        if result.total_points > thresholds.max_total_points:
            no_ship_reasons.append(
                f"Total points ({result.total_points}) exceed threshold ({thresholds.max_total_points})"
            )

        # Check category limits
        for cat_breakdown in result.categories:
            if cat_breakdown.max_allowed is not None and cat_breakdown.points_contributed > cat_breakdown.max_allowed:
                no_ship_reasons.append(
                    f"Category '{cat_breakdown.category.value}' points "
                    f"({cat_breakdown.points_contributed}) exceed limit ({cat_breakdown.max_allowed})"
                )

        # Build ship reasons if no blockers
        if result.blockers == 0:
            ship_reasons.append("No blocker issues found")

            if result.highs == 0:
                ship_reasons.append("No high severity issues found")
            elif result.highs <= thresholds.max_highs:
                ship_reasons.append(f"High severity issues ({result.highs}) within tolerance")

            if result.total_points <= thresholds.max_total_points:
                ship_reasons.append(
                    f"Total points ({result.total_points}) within threshold ({thresholds.max_total_points})"
                )

        # EXPLICIT PASSING CRITERIA
        if result.engines_ran >= thresholds.min_engines_required:
            ship_reasons.append(f"Minimum engines requirement met ({result.engines_ran} ran)")

        # Determine final verdict
        if no_ship_reasons:
            verdict = VerdictStatus.NO_SHIP
        elif degraded:
            verdict = VerdictStatus.DEGRADED
        elif result.highs > thresholds.max_highs:
            # Check if an override was applied for high severity issues
            high_override_applied = any(
                "max_highs" in override.scope for override in result.overrides_applied
            )
            verdict = VerdictStatus.SHIP if high_override_applied else VerdictStatus.CONDITIONAL
        else:
            verdict = VerdictStatus.SHIP

        return verdict, ship_reasons, no_ship_reasons

    def _extract_findings_from_data(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract findings list from various JSON formats."""
        # Direct findings array
        if "findings" in data and isinstance(data["findings"], list):
            return data["findings"]

        # Invariants violations
        if "violations" in data and isinstance(data["violations"], list):
            violations = data["violations"]
            return [
                {
                    "id": v.get("rule_id", f"violation_{i}"),
                    "severity": v.get("severity", "HIGH"),
                    "category": v.get("category", "general"),
                    "message": v.get("message", v.get("description", "Invariant violation")),
                    "location": v.get("location") or v.get("file"),
                    "rule_id": v.get("rule_id"),
                    "tool": v.get("tool", "invariants"),
                }
                for i, v in enumerate(violations)
            ]

        # Policy findings
        if "policy_findings" in data and isinstance(data["policy_findings"], list):
            return data["policy_findings"]

        # Provenance verification results
        if "files_tampered" in data:
            tampered = data.get("files_tampered", [])
            return [
                {
                    "id": f"tampered_{i}",
                    "severity": "BLOCKER",
                    "category": "security",
                    "message": f"File tampered: {item.get('path', 'unknown')}",
                    "location": item.get("path"),
                    "tool": "provenance",
                }
                for i, item in enumerate(tampered)
            ]

        # Intelligence scorecards
        if "anomalies" in data and isinstance(data["anomalies"], list):
            return [
                {
                    "id": a.get("id", f"anomaly_{i}"),
                    "severity": a.get("severity", "MEDIUM"),
                    "category": a.get("category", "general"),
                    "message": a.get("description", "Anomaly detected"),
                    "tool": a.get("tool", "intel"),
                }
                for i, a in enumerate(data["anomalies"])
            ]

        # If data is a list itself, assume it's findings
        if isinstance(data, list):
            return data

        # Empty default
        return []


def aggregate_verdict(
    input_paths: list[Path],
    mode: str = "pr",
    profile: str | None = None,
    expected_engines: list[str] | None = None,
    temporal_store_path: Path | None = None,
    run_id: str | None = None,
) -> VerdictResult:
    """Convenience function to aggregate verdict with governance.

    Args:
        input_paths: Paths to JSON files containing findings
        mode: Execution mode (pr/main/release)
        profile: Optional profile name
        expected_engines: List of engine IDs expected to run
        temporal_store_path: Path to temporal findings store
        run_id: Current run ID for temporal tracking

    Returns:
        Verdict result with full governance

    Example:
        >>> result = aggregate_verdict(
        ...     [Path("readiness.json"), Path("policy_findings.json")],
        ...     mode="main",
        ...     expected_engines=["readiness", "policy", "invariants"],
        ...     run_id="build-12345",
        ... )
        >>> print(result.verdict.value)
        'NO_SHIP'  # NOT optimistic by default!
    """
    # Create thresholds
    mode_enum = Mode(mode)
    thresholds = VerdictThresholds.for_mode(mode_enum)

    # Create aggregator with governance
    aggregator = VerdictAggregator(
        thresholds=thresholds,
        expected_engines=expected_engines,
        temporal_store_path=temporal_store_path,
    )

    # Load findings from each file
    inputs_str = [str(p) for p in input_paths]
    for path in input_paths:
        if path.exists():
            try:
                aggregator.add_findings_from_file(path, run_id=run_id)
            except (json.JSONDecodeError, FileNotFoundError) as e:
                # Log but continue with other files
                print(f"Warning: Could not load {path}: {e}")

    # Aggregate and return
    return aggregator.aggregate(mode=mode_enum, profile=profile, inputs=inputs_str, run_id=run_id)
