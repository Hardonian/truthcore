"""Deterministic historical anomaly scoring for intelligence modules.

Provides deterministic anomaly detection without stochastic methods.
Uses threshold-based detection, trend analysis, and regression detection.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class AnomalyScore:
    """Score for a specific anomaly detection."""
    metric: str
    current_value: float
    expected_range: tuple[float, float]
    severity: str  # low, medium, high, critical
    delta: float
    trend: str  # increasing, decreasing, stable
    explanation: str


class DeterministicAnomalyScorer:
    """Base class for deterministic anomaly scoring.
    
    All scoring methods must be deterministic - same inputs always
    produce same outputs. No random sampling or probabilistic methods.
    """

    def __init__(self, history: list[dict[str, Any]]) -> None:
        """Initialize with historical data.
        
        Args:
            history: List of historical reports, sorted newest first
        """
        self.history = history

    def compute_regression_density(
        self,
        window_size: int = 10,
        threshold: float = 0.2,
    ) -> dict[str, Any]:
        """Compute regression density - ratio of failing to total runs.
        
        Args:
            window_size: Number of recent runs to consider
            threshold: Failure ratio threshold for alert
        
        Returns:
            Regression density score and details
        """
        recent = self.history[:window_size]
        if not recent:
            return {"score": 0.0, "failures": 0, "total": 0}

        failures = sum(1 for r in recent if not r.get("passed", True))
        ratio = failures / len(recent)

        return {
            "score": ratio,
            "failures": failures,
            "total": len(recent),
            "threshold": threshold,
            "alert": ratio > threshold,
        }

    def compute_flake_probability(
        self,
        min_transitions: int = 3,
    ) -> dict[str, Any]:
        """Compute flake indicator based on pass/fail transitions.
        
        High transition count indicates flaky behavior.
        
        Args:
            min_transitions: Minimum transitions to consider flaky
        
        Returns:
            Flake indicator and transition count
        """
        if len(self.history) < 2:
            return {"flake_indicator": 0.0, "transitions": 0}

        transitions = 0
        for i in range(1, len(self.history)):
            prev_pass = self.history[i-1].get("passed", True)
            curr_pass = self.history[i].get("passed", True)
            if prev_pass != curr_pass:
                transitions += 1

        # Flake indicator: transitions per run
        indicator = transitions / (len(self.history) - 1)

        return {
            "flake_indicator": round(indicator, 4),
            "transitions": transitions,
            "is_flaky": transitions >= min_transitions,
        }

    def compute_trend_delta(
        self,
        metric_path: str,
        window_size: int = 5,
    ) -> dict[str, Any]:
        """Compute trend delta for a metric.
        
        Args:
            metric_path: Dot-separated path to metric (e.g., "summary.total")
            window_size: Number of recent runs to compare
        
        Returns:
            Trend analysis
        """
        if len(self.history) < window_size * 2:
            return {"trend": "insufficient_data", "delta": 0.0}

        recent = self.history[:window_size]
        older = self.history[window_size:window_size*2]

        def get_metric(report: dict) -> float:
            parts = metric_path.split(".")
            value = report
            for part in parts:
                if isinstance(value, dict):
                    value = value.get(part, 0)
                else:
                    return 0.0
            return float(value) if value else 0.0

        recent_avg = sum(get_metric(r) for r in recent) / len(recent)
        older_avg = sum(get_metric(r) for r in older) / len(older)

        delta = recent_avg - older_avg

        if abs(delta) < 0.01:
            trend = "stable"
        elif delta > 0:
            trend = "increasing"
        else:
            trend = "decreasing"

        return {
            "trend": trend,
            "delta": round(delta, 4),
            "recent_avg": round(recent_avg, 4),
            "older_avg": round(older_avg, 4),
        }

    def compute_drift_score(
        self,
        metric_path: str,
        threshold_std: float = 2.0,
    ) -> dict[str, Any]:
        """Compute drift score using statistical distance.
        
        Detects when recent values deviate significantly from historical.
        
        Args:
            metric_path: Path to metric
            threshold_std: Standard deviation threshold for drift alert
        
        Returns:
            Drift analysis
        """
        if len(self.history) < 10:
            return {"drift_detected": False, "reason": "insufficient_history"}

        def get_metric(report: dict) -> float:
            parts = metric_path.split(".")
            value = report
            for part in parts:
                if isinstance(value, dict):
                    value = value.get(part, 0)
                else:
                    return 0.0
            return float(value) if value else 0.0

        # Historical baseline (older 70%)
        baseline_size = int(len(self.history) * 0.7)
        baseline = [get_metric(r) for r in self.history[baseline_size:]]
        recent = [get_metric(r) for r in self.history[:5]]

        if not baseline:
            return {"drift_detected": False, "reason": "no_baseline"}

        # Compute statistics
        mean = sum(baseline) / len(baseline)
        variance = sum((x - mean) ** 2 for x in baseline) / len(baseline)
        std = variance ** 0.5

        # Check recent values
        recent_avg = sum(recent) / len(recent) if recent else 0
        distance = abs(recent_avg - mean) / std if std > 0 else 0

        return {
            "drift_detected": distance > threshold_std,
            "distance_std": round(distance, 4),
            "threshold": threshold_std,
            "baseline_mean": round(mean, 4),
            "baseline_std": round(std, 4),
            "recent_avg": round(recent_avg, 4),
        }


class ReadinessAnomalyScorer(DeterministicAnomalyScorer):
    """Anomaly scorer for readiness data."""

    def score(self) -> dict[str, Any]:
        """Generate comprehensive anomaly scorecard."""
        scores = {
            "regression_density": self.compute_regression_density(),
            "flake_probability": self.compute_flake_probability(),
            "finding_trend": self.compute_trend_delta("summary.total"),
            "drift": self.compute_drift_score("summary.total"),
        }

        # Overall health score (0-100)
        health = 100
        if scores["regression_density"]["alert"]:
            health -= 30
        if scores["flake_probability"]["is_flaky"]:
            health -= 25
        if scores["drift"]["drift_detected"]:
            health -= 20

        scores["overall_health"] = max(0, health)
        scores["assessment"] = self._assess_health(health)

        return scores

    def _assess_health(self, score: int) -> str:
        if score >= 90:
            return "healthy"
        elif score >= 70:
            return "degraded"
        elif score >= 50:
            return "at_risk"
        else:
            return "critical"


class ReconciliationAnomalyScorer(DeterministicAnomalyScorer):
    """Anomaly scorer for reconciliation data."""

    def score(self) -> dict[str, Any]:
        """Generate reconciliation anomaly scorecard."""
        scores = {
            "balance_drift": self.compute_drift_score("summary.balance_check"),
            "exception_trend": self.compute_trend_delta("summary.exception_count"),
            "regression_density": self.compute_regression_density(),
        }

        # Rule health: percentage of balanced reconciliations
        balanced = sum(
            1 for r in self.history[:20]
            if r.get("summary", {}).get("balance_check", False)
        )
        scores["rule_health"] = (balanced / min(20, len(self.history))) * 100 if self.history else 0

        return scores


class AgentBehaviorScorer(DeterministicAnomalyScorer):
    """Scorer for agent behavior trust analysis."""

    def score(self) -> dict[str, Any]:
        """Generate agent trust scorecard."""
        scores = {
            "validity_regression": self.compute_regression_density(),
            "trust_trend": self.compute_trend_delta("metrics.tool_success_rate"),
            "latency_drift": self.compute_drift_score("metrics.avg_latency_ms"),
            "flake_indicator": self.compute_flake_probability(),
        }

        # Compute trust score based on success rate stability
        if len(self.history) >= 5:
            recent = self.history[:5]
            success_rates = [
                r.get("metrics", {}).get("tool_success_rate", 0)
                for r in recent
            ]
            avg_success = sum(success_rates) / len(success_rates)
            scores["trust_score"] = avg_success * 100
        else:
            scores["trust_score"] = 50.0

        return scores


class KnowledgeHealthScorer(DeterministicAnomalyScorer):
    """Scorer for knowledge base health."""

    def score(self) -> dict[str, Any]:
        """Generate knowledge health scorecard."""
        scores = {
            "stale_doc_trend": self.compute_trend_delta("stats.stale_count"),
            "coverage_drift": self.compute_drift_score("stats.total"),
            "freshness_regression": self.compute_regression_density(
                window_size=5,
                threshold=0.4,
            ),
        }

        # Decay detection
        if len(self.history) >= 2:
            recent_stale = self.history[0].get("stats", {}).get("stale_count", 0)
            older_stale = self.history[-1].get("stats", {}).get("stale_count", 0)
            scores["decay_detected"] = recent_stale > older_stale * 1.2
        else:
            scores["decay_detected"] = False

        return scores


class ScorecardWriter:
    """Write scorecards to output files."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir

    def write(self, scorecard: dict[str, Any], prefix: str = "intel") -> tuple[Path, Path]:
        """Write scorecard as JSON and Markdown."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # JSON
        json_path = self.output_dir / f"{prefix}_scorecard.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(scorecard, f, indent=2, sort_keys=True)

        # Markdown
        md_path = self.output_dir / f"{prefix}_scorecard.md"
        md_content = self._format_markdown(scorecard, prefix)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        return json_path, md_path

    def _format_markdown(self, scorecard: dict[str, Any], title: str) -> str:
        """Format scorecard as markdown."""
        lines = [
            f"# {title.replace('_', ' ').title()} Scorecard",
            "",
            f"**Generated:** {datetime.now().isoformat()}",
            "",
        ]

        for key, value in scorecard.items():
            if isinstance(value, dict):
                lines.append(f"## {key.replace('_', ' ').title()}")
                lines.append("")
                lines.append("```json")
                lines.append(json.dumps(value, indent=2))
                lines.append("```")
                lines.append("")
            else:
                lines.append(f"- **{key.replace('_', ' ').title()}:** {value}")

        return "\n".join(lines)
