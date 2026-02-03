"""Comprehensive tests for verdict governance system.

Tests all governance mechanisms:
- Unified severity enums
- Category assignment audit trails
- Override tracking and validation
- Temporal awareness
- Engine health checks
- Configurable category weights
"""

import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from truthcore.severity import (
    Category,
    CategoryAssignment,
    CategoryWeightConfig,
    EngineHealth,
    Override,
    Severity,
    TemporalFinding,
)
from truthcore.verdict.aggregator import VerdictAggregator
from truthcore.verdict.models import Mode, VerdictStatus, VerdictThresholds


def test_unified_severity_enum():
    """Test that Severity enum works consistently across all systems."""
    # Test string parsing
    sev1 = Severity.from_string("HIGH")
    sev2 = Severity.from_string("high")
    assert sev1 == sev2 == Severity.HIGH

    # Test comparisons
    assert Severity.BLOCKER > Severity.HIGH
    assert Severity.HIGH > Severity.MEDIUM
    assert Severity.MEDIUM > Severity.LOW
    assert Severity.LOW > Severity.INFO

    # Test ordering
    assert Severity.INFO < Severity.LOW
    assert Severity.LOW <= Severity.MEDIUM
    assert Severity.HIGH >= Severity.MEDIUM


def test_category_assignment_audit_trail():
    """Test that category assignments are tracked with full audit trail."""
    assignment = CategoryAssignment(
        finding_id="test-1",
        category=Category.SECURITY,
        assigned_by="security-scanner",
        assigned_at=datetime.now(UTC).isoformat(),
        reason="File access pattern detected",
        confidence=0.95,
    )

    assert assignment.finding_id == "test-1"
    assert assignment.category == Category.SECURITY
    assert assignment.assigned_by == "security-scanner"
    assert assignment.confidence == 0.95
    assert not assignment.reviewed  # Not reviewed yet

    # Test serialization
    data = assignment.to_dict()
    assert data["category"] == "security"
    assert data["confidence"] == 0.95

    # Test deserialization
    restored = CategoryAssignment.from_dict(data)
    assert restored.category == Category.SECURITY


def test_override_governance():
    """Test override governance with expiration and usage tracking."""
    # Create valid override
    override = Override.create_for_high_severity(
        approved_by="tech-lead@example.com",
        reason="Hotfix deployment for critical bug",
        max_highs_override=10,
        duration_hours=24,
    )

    assert override.is_valid()
    assert not override.is_expired()
    assert not override.used

    # Mark as used
    override.mark_used("verdict-123")
    assert override.used
    assert override.verdict_id == "verdict-123"
    assert not override.is_valid()  # No longer valid after use

    # Test expired override
    expired_override = Override(
        override_id="expired-1",
        approved_by="user@example.com",
        approved_at=(datetime.now(UTC) - timedelta(days=2)).isoformat(),
        expires_at=(datetime.now(UTC) - timedelta(days=1)).isoformat(),
        reason="Test",
        scope="test",
    )
    assert expired_override.is_expired()
    assert not expired_override.is_valid()


def test_temporal_finding_tracking():
    """Test temporal tracking of chronic issues."""
    # Create temporal finding
    temp = TemporalFinding(
        finding_fingerprint="rule-123:file.py:42",
        first_seen=datetime.now(UTC).isoformat(),
        last_seen=datetime.now(UTC).isoformat(),
        occurrences=1,
    )

    # Record occurrences
    temp.record_occurrence("run-1", "HIGH")
    temp.record_occurrence("run-2", "HIGH")
    temp.record_occurrence("run-3", "HIGH")

    assert temp.occurrences == 4  # Initial + 3 more
    assert len(temp.runs_with_finding) == 3
    assert len(temp.severity_history) == 3

    # Test escalation
    assert temp.should_escalate(threshold_occurrences=3)
    temp.escalate("Chronic issue detected")
    assert temp.escalated
    assert temp.escalation_reason == "Chronic issue detected"


def test_engine_health_checks():
    """Test engine health check system."""
    # Healthy engine
    healthy = EngineHealth(
        engine_id="policy-scanner",
        expected=True,
        ran=True,
        succeeded=True,
        timestamp=datetime.now(UTC).isoformat(),
        findings_reported=5,
    )
    assert healthy.is_healthy()

    # Engine that didn't run
    missing = EngineHealth(
        engine_id="missing-engine",
        expected=True,
        ran=False,
        succeeded=False,
        timestamp=datetime.now(UTC).isoformat(),
    )
    assert not missing.is_healthy()

    # Engine that failed
    failed = EngineHealth(
        engine_id="broken-engine",
        expected=True,
        ran=True,
        succeeded=False,
        timestamp=datetime.now(UTC).isoformat(),
        error_message="Timeout after 30s",
    )
    assert not failed.is_healthy()


def test_category_weight_config_governance():
    """Test category weight configuration with review cycles."""
    config = CategoryWeightConfig.create_default()

    assert config.get_weight(Category.SECURITY) == 2.0
    assert config.get_weight(Category.GENERAL) == 1.0
    assert config.reviewed_by == "system"

    # Update weights
    new_weights = config.weights.copy()
    new_weights[Category.SECURITY] = 3.0
    config.update_weights(new_weights, "security-team@example.com", "Increased security weight after audit")

    assert config.get_weight(Category.SECURITY) == 3.0
    assert config.reviewed_by == "security-team@example.com"
    assert not config.is_review_overdue()

    # Test review overdue
    old_config = CategoryWeightConfig(
        weights={Category.GENERAL: 1.0},
        last_reviewed=(datetime.now(UTC) - timedelta(days=100)).isoformat(),
        review_frequency_days=90,
    )
    assert old_config.is_review_overdue()


def test_not_optimistic_by_default():
    """Test that aggregator is NOT optimistic by default."""
    aggregator = VerdictAggregator(expected_engines=["engine1", "engine2"])

    # No findings, no health signals -> should be NO_SHIP
    result = aggregator.aggregate(mode=Mode.PR)

    assert result.verdict == VerdictStatus.NO_SHIP
    assert any("engine" in reason.lower() for reason in result.no_ship_reasons)
    assert result.engines_expected == 2
    assert result.engines_ran == 0


def test_engine_health_required():
    """Test that missing engine health signals cause failure."""
    thresholds = VerdictThresholds.for_mode(Mode.MAIN)
    aggregator = VerdictAggregator(thresholds=thresholds, expected_engines=["engine1", "engine2", "engine3"])

    # Only one engine reports health
    aggregator.register_engine_health(
        EngineHealth(
            engine_id="engine1",
            expected=True,
            ran=True,
            succeeded=True,
            timestamp=datetime.now(UTC).isoformat(),
        )
    )

    result = aggregator.aggregate(mode=Mode.MAIN)  # Requires 2 engines

    assert result.verdict == VerdictStatus.NO_SHIP
    assert "1 engine(s) ran, but 2 required" in str(result.no_ship_reasons)
    assert len(result.degradation_reasons) >= 2  # Two engines missing signals


def test_engine_pass_fail_honored():
    """Test that individual engine pass/fail affects verdict."""
    thresholds = VerdictThresholds.for_mode(Mode.MAIN)
    thresholds.require_all_engines_healthy = True

    aggregator = VerdictAggregator(thresholds=thresholds, expected_engines=["engine1", "engine2"])

    # Register healthy engines
    aggregator.register_engine_health(
        EngineHealth(
            engine_id="engine1",
            expected=True,
            ran=True,
            succeeded=True,
            timestamp=datetime.now(UTC).isoformat(),
        )
    )
    aggregator.register_engine_health(
        EngineHealth(
            engine_id="engine2",
            expected=True,
            ran=True,
            succeeded=False,  # Failed!
            timestamp=datetime.now(UTC).isoformat(),
            error_message="Parse error",
        )
    )

    # Add some findings from engine1 (within limits)
    aggregator.add_finding(
        finding_id="f1",
        tool="engine1",
        severity=Severity.LOW,
        category=Category.GENERAL,
        message="Minor issue",
        source_engine="engine1",
    )

    result = aggregator.aggregate(mode=Mode.MAIN)

    # Should fail because engine2 is unhealthy
    assert result.verdict == VerdictStatus.NO_SHIP
    assert "failed health check" in str(result.no_ship_reasons).lower()


def test_temporal_escalation():
    """Test that chronic issues escalate in severity."""
    with tempfile.TemporaryDirectory() as tmpdir:
        temporal_path = Path(tmpdir) / "temporal.json"

        # First run
        thresholds = VerdictThresholds.for_mode(Mode.PR)
        thresholds.min_engines_required = 0
        agg1 = VerdictAggregator(thresholds=thresholds, temporal_store_path=temporal_path, expected_engines=["test"])
        agg1.register_engine_health(
            EngineHealth(
                engine_id="test", expected=True, ran=True, succeeded=True, timestamp=datetime.now(UTC).isoformat()
            )
        )

        finding1 = agg1.add_finding(
            finding_id="f1",
            tool="test",
            severity=Severity.LOW,
            category=Category.GENERAL,
            message="Test issue",
            rule_id="test-rule",
            location="file.py:10",
            run_id="run-1",
        )
        assert finding1.severity == Severity.LOW
        assert finding1.escalated_from is None

        agg1.aggregate(mode=Mode.PR, run_id="run-1")

        # Second run (same issue)
        thresholds = VerdictThresholds.for_mode(Mode.PR)
        thresholds.min_engines_required = 0
        agg2 = VerdictAggregator(thresholds=thresholds, temporal_store_path=temporal_path, expected_engines=["test"])
        agg2.register_engine_health(
            EngineHealth(
                engine_id="test", expected=True, ran=True, succeeded=True, timestamp=datetime.now(UTC).isoformat()
            )
        )

        finding2 = agg2.add_finding(
            finding_id="f2",
            tool="test",
            severity=Severity.LOW,
            category=Category.GENERAL,
            message="Test issue",
            rule_id="test-rule",
            location="file.py:10",
            run_id="run-2",
        )
        assert finding2.severity == Severity.LOW  # Not yet escalated

        agg2.aggregate(mode=Mode.PR, run_id="run-2")  # Save temporal state

        # Third run (should escalate)
        thresholds = VerdictThresholds.for_mode(Mode.PR)
        thresholds.min_engines_required = 0
        agg3 = VerdictAggregator(thresholds=thresholds, temporal_store_path=temporal_path, expected_engines=["test"])
        agg3.register_engine_health(
            EngineHealth(
                engine_id="test", expected=True, ran=True, succeeded=True, timestamp=datetime.now(UTC).isoformat()
            )
        )

        finding3 = agg3.add_finding(
            finding_id="f3",
            tool="test",
            severity=Severity.LOW,
            category=Category.GENERAL,
            message="Test issue",
            rule_id="test-rule",
            location="file.py:10",
            run_id="run-3",
        )

        # Should escalate to MEDIUM after 3 occurrences
        assert finding3.severity == Severity.MEDIUM
        assert finding3.escalated_from == Severity.LOW

        result = agg3.aggregate(mode=Mode.PR, run_id="run-3")
        assert len(result.temporal_escalations) > 0


def test_override_application():
    """Test that overrides are properly applied and tracked."""
    thresholds = VerdictThresholds.for_mode(Mode.PR)
    thresholds.min_engines_required = 0
    aggregator = VerdictAggregator(thresholds=thresholds, expected_engines=["test"])
    aggregator.register_engine_health(
        EngineHealth(
            engine_id="test", expected=True, ran=True, succeeded=True, timestamp=datetime.now(UTC).isoformat()
        )
    )

    # Add 8 high severity findings (exceeds PR mode limit of 5)
    for i in range(8):
        aggregator.add_finding(
            finding_id=f"high-{i}",
            tool="test",
            severity=Severity.HIGH,
            category=Category.GENERAL,
            message=f"High severity issue {i}",
            source_engine="test",
        )

    # Without override -> NO_SHIP
    result_no_override = aggregator.aggregate(mode=Mode.PR)
    assert result_no_override.verdict == VerdictStatus.NO_SHIP

    # Reset and add override
    thresholds = VerdictThresholds.for_mode(Mode.PR)
    thresholds.min_engines_required = 0
    thresholds.max_total_points = 500  # Increase to accommodate 8 HIGH findings (8 * 50 = 400)
    aggregator2 = VerdictAggregator(thresholds=thresholds, expected_engines=["test"])
    aggregator2.register_engine_health(
        EngineHealth(
            engine_id="test", expected=True, ran=True, succeeded=True, timestamp=datetime.now(UTC).isoformat()
        )
    )

    for i in range(8):
        aggregator2.add_finding(
            finding_id=f"high-{i}",
            tool="test",
            severity=Severity.HIGH,
            category=Category.GENERAL,
            message=f"High severity issue {i}",
            source_engine="test",
        )

    # Register override for up to 10 highs
    override = Override.create_for_high_severity(
        approved_by="manager@example.com", reason="Acceptable for hotfix", max_highs_override=10, duration_hours=24
    )
    aggregator2.register_override(override)

    result_with_override = aggregator2.aggregate(mode=Mode.PR)

    # Should now SHIP with override applied
    assert result_with_override.verdict == VerdictStatus.SHIP
    assert len(result_with_override.overrides_applied) == 1
    assert result_with_override.overrides_applied[0].approved_by == "manager@example.com"
    assert result_with_override.overrides_applied[0].used


def test_category_assignment_audit():
    """Test that all category assignments are audited."""
    thresholds = VerdictThresholds.for_mode(Mode.PR)
    thresholds.min_engines_required = 0
    aggregator = VerdictAggregator(thresholds=thresholds, expected_engines=["test"])
    aggregator.register_engine_health(
        EngineHealth(
            engine_id="test", expected=True, ran=True, succeeded=True, timestamp=datetime.now(UTC).isoformat()
        )
    )

    # Add findings with different categories
    aggregator.add_finding(
        finding_id="sec-1",
        tool="security-scanner",
        severity=Severity.HIGH,
        category=Category.SECURITY,
        message="SQL injection",
        assigned_by="security-scanner",
        assignment_reason="Pattern match: SQL keywords in user input",
    )

    aggregator.add_finding(
        finding_id="gen-1",
        tool="linter",
        severity=Severity.LOW,
        category=Category.GENERAL,
        message="Unused variable",
        assigned_by="system",
        assignment_reason="Auto-categorized by system",
    )

    result = aggregator.aggregate(mode=Mode.PR)

    # Check audit trail
    assert len(result.category_assignments) == 2

    sec_assignment = next(a for a in result.category_assignments if a.finding_id == "sec-1")
    assert sec_assignment.category == Category.SECURITY
    assert sec_assignment.assigned_by == "security-scanner"
    assert "Pattern match" in sec_assignment.reason
    assert sec_assignment.confidence == 1.0  # Not system

    gen_assignment = next(a for a in result.category_assignments if a.finding_id == "gen-1")
    assert gen_assignment.category == Category.GENERAL
    assert gen_assignment.assigned_by == "system"
    assert gen_assignment.confidence == 0.8  # System assignment


def test_category_multipliers_in_use():
    """Test that category multipliers actually affect scoring."""
    thresholds = VerdictThresholds.for_mode(Mode.PR)
    thresholds.min_engines_required = 0
    aggregator = VerdictAggregator(thresholds=thresholds, expected_engines=["test"])
    aggregator.register_engine_health(
        EngineHealth(
            engine_id="test", expected=True, ran=True, succeeded=True, timestamp=datetime.now(UTC).isoformat()
        )
    )

    # Add HIGH security finding (2x multiplier)
    sec_finding = aggregator.add_finding(
        finding_id="sec",
        tool="test",
        severity=Severity.HIGH,
        category=Category.SECURITY,
        message="Security issue",
        source_engine="test",
    )

    # Add HIGH general finding (1x multiplier)
    gen_finding = aggregator.add_finding(
        finding_id="gen",
        tool="test",
        severity=Severity.HIGH,
        category=Category.GENERAL,
        message="General issue",
        source_engine="test",
    )

    # Security finding should have higher points due to multiplier
    assert sec_finding.points > gen_finding.points
    assert sec_finding.points == 100  # 50 * 2.0
    assert gen_finding.points == 50  # 50 * 1.0


def test_zero_input_files_fails():
    """Test that zero input files results in NO_SHIP."""
    aggregator = VerdictAggregator(expected_engines=["engine1"])

    # No findings, no health signals
    result = aggregator.aggregate(mode=Mode.PR)

    assert result.verdict == VerdictStatus.NO_SHIP
    assert result.total_findings == 0
    assert len(result.no_ship_reasons) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
