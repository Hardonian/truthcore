"""Verdict Aggregator v2 - Weighted Scoring (M6).

Aggregates findings from multiple engines and produces a weighted verdict.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from truthcore.manifest import normalize_timestamp
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


class VerdictAggregator:
    """Aggregates findings from multiple engines into a verdict."""
    
    def __init__(self, thresholds: VerdictThresholds | None = None):
        """Initialize aggregator.
        
        Args:
            thresholds: Threshold configuration (uses mode defaults if None)
        """
        self.thresholds = thresholds
        self.findings: list[WeightedFinding] = []
    
    def add_finding(
        self,
        finding_id: str,
        tool: str,
        severity: SeverityLevel | str,
        category: Category | str,
        message: str,
        location: str | None = None,
        rule_id: str | None = None,
        source_file: str | None = None,
        source_engine: str | None = None,
    ) -> WeightedFinding:
        """Add a finding to the aggregator.
        
        Args:
            finding_id: Unique identifier for this finding
            tool: Tool that reported the finding
            severity: Severity level
            category: Category
            message: Human-readable message
            location: Optional location info
            rule_id: Optional rule identifier
            source_file: Optional source file this came from
            source_engine: Optional source engine this came from
            
        Returns:
            The weighted finding with computed points
        """
        # Convert string enums
        if isinstance(severity, str):
            severity = SeverityLevel(severity.upper())
        if isinstance(category, str):
            category = Category(category.lower())
        
        # Compute weight and points
        category_weight = self.thresholds.get_category_weight(category) if self.thresholds else 1.0
        severity_weight = self.thresholds.get_severity_weight(severity) if self.thresholds else 1.0
        
        weight = category_weight * (1.0 if severity_weight == float('inf') else severity_weight)
        
        # Points: severity weight * category weight
        if severity == SeverityLevel.BLOCKER:
            points = 1000  # Blockers are always fail
        elif severity == SeverityLevel.HIGH:
            points = int(50 * category_weight)
        elif severity == SeverityLevel.MEDIUM:
            points = int(10 * category_weight)
        elif severity == SeverityLevel.LOW:
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
            source_file=source_file,
            source_engine=source_engine,
        )
        
        self.findings.append(finding)
        return finding
    
    def add_findings_from_json(self, data: dict[str, Any], source_file: str | None = None) -> list[WeightedFinding]:
        """Add findings from a JSON data structure.
        
        Supports multiple formats:
        - readiness.json: findings array with severity
        - invariants.json: rule violations
        - policy_findings.json: policy findings
        - Generic: list of findings
        
        Args:
            data: JSON data containing findings
            source_file: Source file path for tracking
            
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
                severity = SeverityLevel(severity_str)
            except ValueError:
                severity = SeverityLevel.INFO
            
            # Determine category
            category_str = item.get("category", "general")
            if isinstance(category_str, str):
                category_str = category_str.lower()
            try:
                category = Category(category_str)
            except ValueError:
                category = Category.GENERAL
            
            # Get message
            message = item.get("message") or item.get("description") or item.get("rule") or "Unknown issue"
            
            # Get location
            location = item.get("location") or item.get("file") or item.get("path")
            if location and item.get("line"):
                location = f"{location}:{item['line']}"
            
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
            )
            added.append(finding)
        
        return added
    
    def add_findings_from_file(self, path: Path) -> list[WeightedFinding]:
        """Add findings from a JSON file.
        
        Args:
            path: Path to JSON file
            
        Returns:
            List of weighted findings added
            
        Raises:
            FileNotFoundError: If file doesn't exist
            json.JSONDecodeError: If file is invalid JSON
        """
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return self.add_findings_from_json(data, source_file=str(path))
    
    def aggregate(
        self,
        mode: Mode | str = Mode.PR,
        profile: str | None = None,
        inputs: list[str] | None = None,
    ) -> VerdictResult:
        """Aggregate all findings and produce a verdict.
        
        Args:
            mode: Execution mode (pr/main/release)
            profile: Optional profile name
            inputs: List of input file paths processed
            
        Returns:
            Complete verdict result
        """
        if isinstance(mode, str):
            mode = Mode(mode)
        
        # Get thresholds for mode
        thresholds = self.thresholds or VerdictThresholds.for_mode(mode)
        
        # Initialize result
        result = VerdictResult(
            verdict=VerdictStatus.SHIP,  # Default to ship, will change if issues found
            timestamp=normalize_timestamp(),
            mode=mode,
            profile=profile,
            inputs=inputs or [],
            thresholds=thresholds,
        )
        
        # Count by severity
        result.total_findings = len(self.findings)
        result.blockers = sum(1 for f in self.findings if f.severity == SeverityLevel.BLOCKER)
        result.highs = sum(1 for f in self.findings if f.severity == SeverityLevel.HIGH)
        result.mediums = sum(1 for f in self.findings if f.severity == SeverityLevel.MEDIUM)
        result.lows = sum(1 for f in self.findings if f.severity == SeverityLevel.LOW)
        
        # Calculate total points
        result.total_points = sum(f.points for f in self.findings)
        
        # Build engine contributions
        engines_map: dict[str, EngineContribution] = {}
        for finding in self.findings:
            engine_id = finding.source_engine or finding.tool or "unknown"
            
            if engine_id not in engines_map:
                engines_map[engine_id] = EngineContribution(engine_id=engine_id)
            
            engine = engines_map[engine_id]
            engine.findings_count += 1
            engine.points_contributed += finding.points
            
            if finding.severity == SeverityLevel.BLOCKER:
                engine.blockers += 1
            elif finding.severity == SeverityLevel.HIGH:
                engine.highs += 1
            elif finding.severity == SeverityLevel.MEDIUM:
                engine.mediums += 1
            elif finding.severity == SeverityLevel.LOW:
                engine.lows += 1
        
        # Determine engine pass/fail status
        for engine in engines_map.values():
            engine.passed = (
                engine.blockers == 0 and
                engine.highs <= thresholds.max_highs and
                engine.points_contributed < thresholds.max_total_points / max(len(engines_map), 1)
            )
        
        result.engines = list(engines_map.values())
        
        # Build category breakdowns
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
        
        result.categories = list(categories_map.values())
        
        # Sort findings by severity and points for top findings
        severity_order = {
            SeverityLevel.BLOCKER: 0,
            SeverityLevel.HIGH: 1,
            SeverityLevel.MEDIUM: 2,
            SeverityLevel.LOW: 3,
            SeverityLevel.INFO: 4,
        }
        sorted_findings = sorted(
            self.findings,
            key=lambda f: (severity_order.get(f.severity, 5), -f.points),
        )
        result.top_findings = sorted_findings
        
        # Determine verdict
        result.verdict, result.ship_reasons, result.no_ship_reasons = self._determine_verdict(
            result, thresholds
        )
        
        return result
    
    def _determine_verdict(
        self,
        result: VerdictResult,
        thresholds: VerdictThresholds,
    ) -> tuple[VerdictStatus, list[str], list[str]]:
        """Determine the final verdict based on findings and thresholds.
        
        Args:
            result: Current result with findings counted
            thresholds: Thresholds to apply
            
        Returns:
            Tuple of (verdict, ship_reasons, no_ship_reasons)
        """
        ship_reasons: list[str] = []
        no_ship_reasons: list[str] = []
        
        # Check blockers - always fail
        if result.blockers > thresholds.max_blockers:
            no_ship_reasons.append(
                f"{result.blockers} blocker(s) found (max allowed: {thresholds.max_blockers})"
            )
        
        # Check high severity
        if result.highs > thresholds.max_highs:
            if result.highs > thresholds.max_highs_with_override:
                no_ship_reasons.append(
                    f"{result.highs} high severity issue(s) found (max allowed without override: {thresholds.max_highs_with_override})"
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
            if cat_breakdown.max_allowed is not None:
                if cat_breakdown.points_contributed > cat_breakdown.max_allowed:
                    no_ship_reasons.append(
                        f"Category '{cat_breakdown.category.value}' points ({cat_breakdown.points_contributed}) "
                        f"exceed limit ({cat_breakdown.max_allowed})"
                    )
        
        # Build ship reasons if no blockers
        if result.blockers == 0:
            ship_reasons.append("No blocker issues found")
            
            if result.highs == 0:
                ship_reasons.append("No high severity issues found")
            elif result.highs <= thresholds.max_highs:
                ship_reasons.append(
                    f"High severity issues ({result.highs}) within tolerance"
                )
            
            if result.total_points <= thresholds.max_total_points:
                ship_reasons.append(
                    f"Total points ({result.total_points}) within threshold ({thresholds.max_total_points})"
                )
        
        # Determine final verdict
        if no_ship_reasons:
            verdict = VerdictStatus.NO_SHIP
        elif result.highs > thresholds.max_highs:
            verdict = VerdictStatus.CONDITIONAL
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
    custom_thresholds: dict[str, Any] | None = None,
) -> VerdictResult:
    """Convenience function to aggregate verdict from input files.
    
    Args:
        input_paths: Paths to JSON files containing findings
        mode: Execution mode (pr/main/release)
        profile: Optional profile name
        custom_thresholds: Optional custom threshold overrides
        
    Returns:
        Verdict result
        
    Example:
        >>> result = aggregate_verdict(
        ...     [Path("readiness.json"), Path("policy_findings.json")],
        ...     mode="main",
        ... )
        >>> print(result.verdict.value)
        'SHIP'
    """
    # Create thresholds
    mode_enum = Mode(mode)
    thresholds = VerdictThresholds.for_mode(mode_enum)
    
    if custom_thresholds:
        for key, value in custom_thresholds.items():
            if hasattr(thresholds, key):
                setattr(thresholds, key, value)
    
    # Create aggregator
    aggregator = VerdictAggregator(thresholds)
    
    # Load findings from each file
    inputs_str = [str(p) for p in input_paths]
    for path in input_paths:
        if path.exists():
            try:
                aggregator.add_findings_from_file(path)
            except (json.JSONDecodeError, FileNotFoundError) as e:
                # Log but continue with other files
                print(f"Warning: Could not load {path}: {e}")
    
    # Aggregate and return
    return aggregator.aggregate(mode=mode_enum, profile=profile, inputs=inputs_str)
