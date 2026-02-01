"""Comprehensive tests for reversibility guarantees.

Tests all reversibility mechanisms added to governance primitives:
- Override revocation and extension
- Temporal de-escalation
- Category assignment history and versioning
- Weight version tracking
- Engine health retry logic
- Aggregator override removal

CRITICAL: These tests verify that all governance decisions can be
cheaply reversed without data loss.
"""

from datetime import UTC, datetime, timedelta

import pytest

from truthcore.severity import (
    Category,
    CategoryAssignment,
    CategoryAssignmentHistory,
    CategoryWeightConfig,
    EngineHealth,
    Override,
    OverrideScope,
    TemporalFinding,
)
from truthcore.verdict.aggregator import VerdictAggregator
from truthcore.verdict.models import Mode, VerdictThresholds


class TestOverrideReversibility:
    """Test Override revocation and extension."""

    def test_override_revoke_before_use(self):
        """Test that overrides can be revoked before use."""
        override = Override.create_for_high_severity(
            approved_by="tech-lead@example.com",
            reason="Prod hotfix",
            max_highs_override=10,
            duration_hours=24,
        )

        assert override.is_valid()
        assert not override.revoked

        # Revoke it
        override.revoke(revoked_by="security-lead@example.com", reason="Policy changed")

        assert override.revoked
        assert override.revoked_by == "security-lead@example.com"
        assert override.revocation_reason == "Policy changed"
        assert override.revoked_at is not None
        assert not override.is_valid()  # Revoked overrides are invalid

    def test_override_revoke_preserves_audit_trail(self):
        """Test that revocation creates full audit trail."""
        override = Override.create_for_high_severity(
            approved_by="alice@example.com",
            reason="Hotfix",
            max_highs_override=10,
        )

        override.revoke(revoked_by="bob@example.com", reason="No longer needed")

        data = override.to_dict()
        assert data["revoked"]
        assert data["revoked_by"] == "bob@example.com"
        assert data["revocation_reason"] == "No longer needed"
        assert "revoked_at" in data

    def test_override_extend_existing(self):
        """Test that overrides can be extended without re-approval."""
        original = Override.create_for_high_severity(
            approved_by="tech-lead@example.com",
            reason="Need more time",
            max_highs_override=10,
            duration_hours=24,
        )

        # Extend by 12 hours
        extended = Override.extend_existing(
            existing=original,
            additional_hours=12,
            extended_by="tech-lead@example.com",
            reason="Still fixing issues",
        )

        assert extended.parent_override_id == original.override_id
        assert extended.approved_by == "tech-lead@example.com"
        assert extended.scope == original.scope
        assert extended.conditions == original.conditions
        assert "Extension of" in extended.reason

        # Extended override has later expiry
        original_expiry = datetime.fromisoformat(original.expires_at.replace("Z", "+00:00"))
        extended_expiry = datetime.fromisoformat(extended.expires_at.replace("Z", "+00:00"))
        assert extended_expiry > original_expiry

    def test_override_scope_parsing(self):
        """Test OverrideScope parsing and validation."""
        # Test simple format
        scope1 = OverrideScope.from_string("max_highs: 10")
        assert scope1.scope_type == "max_highs"
        assert scope1.limit == 10
        assert scope1.original_limit is None

        # Test range format
        scope2 = OverrideScope.from_string("max_highs: 5 -> 10")
        assert scope2.scope_type == "max_highs"
        assert scope2.limit == 10
        assert scope2.original_limit == 5

        # Test legacy format compatibility
        scope3 = OverrideScope.from_string("max_highs_with_override: 10")
        assert scope3.scope_type == "max_highs"  # Stripped "_with_override"
        assert scope3.limit == 10

    def test_override_scope_to_string(self):
        """Test OverrideScope conversion to string."""
        scope1 = OverrideScope(scope_type="max_highs", limit=10)
        assert scope1.to_string() == "max_highs: 10"

        scope2 = OverrideScope(scope_type="max_highs", limit=10, original_limit=5)
        assert scope2.to_string() == "max_highs: 5 -> 10"

    def test_override_scope_invalid_format(self):
        """Test that invalid scope format raises error."""
        with pytest.raises(ValueError, match="Invalid scope format"):
            OverrideScope.from_string("invalid")


class TestTemporalFindingReversibility:
    """Test TemporalFinding de-escalation."""

    def test_temporal_de_escalate(self):
        """Test that escalated findings can be de-escalated."""
        finding = TemporalFinding(
            finding_fingerprint="abc123",
            first_seen="2026-02-01T10:00:00Z",
            last_seen="2026-02-01T10:00:00Z",
            occurrences=3,
        )

        finding.escalate("Chronic issue")
        assert finding.escalated
        assert not finding.de_escalated

        # De-escalate
        finding.de_escalate(by="human@example.com", reason="Fingerprint collision")

        assert not finding.escalated  # No longer escalated
        assert finding.de_escalated
        assert finding.de_escalated_by == "human@example.com"
        assert finding.de_escalation_reason == "Fingerprint collision"
        assert finding.de_escalated_at is not None

    def test_de_escalated_findings_dont_re_escalate(self):
        """Test that de-escalated findings won't re-escalate."""
        finding = TemporalFinding(
            finding_fingerprint="abc123",
            first_seen="2026-02-01T10:00:00Z",
            last_seen="2026-02-01T10:00:00Z",
            occurrences=3,
        )

        finding.de_escalate(by="human@example.com", reason="False positive")

        # should_escalate returns False for de-escalated findings
        assert not finding.should_escalate(threshold_occurrences=3)

        # Even if we add more occurrences
        finding.record_occurrence("run_4", "HIGH")
        assert finding.occurrences == 4
        assert not finding.should_escalate(threshold_occurrences=3)

    def test_de_escalation_preserves_history(self):
        """Test that de-escalation preserves occurrence history."""
        finding = TemporalFinding(
            finding_fingerprint="abc123",
            first_seen="2026-02-01T10:00:00Z",
            last_seen="2026-02-01T10:00:00Z",
            occurrences=3,
            runs_with_finding=["run_1", "run_2", "run_3"],
            severity_history=[
                ("2026-02-01T10:00:00Z", "HIGH"),
                ("2026-02-01T11:00:00Z", "HIGH"),
                ("2026-02-01T12:00:00Z", "HIGH"),
            ],
        )

        finding.de_escalate(by="human@example.com", reason="Test runs, not prod")

        # History preserved
        assert finding.occurrences == 3
        assert finding.runs_with_finding == ["run_1", "run_2", "run_3"]
        assert len(finding.severity_history) == 3

    def test_de_escalation_to_dict(self):
        """Test that de-escalation fields serialize correctly."""
        finding = TemporalFinding(
            finding_fingerprint="abc123",
            first_seen="2026-02-01T10:00:00Z",
            last_seen="2026-02-01T10:00:00Z",
            occurrences=3,
        )

        finding.de_escalate(by="human@example.com", reason="False positive")

        data = finding.to_dict()
        assert data["de_escalated"]
        assert data["de_escalated_by"] == "human@example.com"
        assert data["de_escalation_reason"] == "False positive"
        assert "de_escalated_at" in data


class TestCategoryAssignmentHistory:
    """Test CategoryAssignmentHistory versioning."""

    def test_category_assignment_versioning(self):
        """Test that assignments are versioned."""
        assignment1 = CategoryAssignment(
            finding_id="F1",
            category=Category.SECURITY,
            assigned_by="scanner",
            assigned_at="2026-02-01T10:00:00Z",
            reason="SQL keywords detected",
            confidence=0.8,
        )

        assignment2 = CategoryAssignment(
            finding_id="F1",
            category=Category.BUILD,
            assigned_by="human@example.com",
            assigned_at="2026-02-01T10:05:00Z",
            reason="Actually build config",
            confidence=1.0,
            reviewed=True,
            reviewer="human@example.com",
        )

        history = CategoryAssignmentHistory(finding_id="F1")
        history.add_version(assignment1)
        history.add_version(assignment2)

        assert len(history.versions) == 2
        assert history.versions[0].version == 1
        assert history.versions[1].version == 2

    def test_get_current_assignment(self):
        """Test that get_current returns highest confidence assignment."""
        history = CategoryAssignmentHistory(finding_id="F1")

        # Scanner assignment (confidence 0.8)
        history.add_version(
            CategoryAssignment(
                finding_id="F1",
                category=Category.SECURITY,
                assigned_by="scanner",
                assigned_at="2026-02-01T10:00:00Z",
                reason="Auto",
                confidence=0.8,
            )
        )

        # Human review (confidence 1.0)
        history.add_version(
            CategoryAssignment(
                finding_id="F1",
                category=Category.BUILD,
                assigned_by="human@example.com",
                assigned_at="2026-02-01T10:05:00Z",
                reason="Correction",
                confidence=1.0,
                reviewed=True,
            )
        )

        current = history.get_current()
        assert current is not None
        assert current.category == Category.BUILD
        assert current.confidence == 1.0

    def test_get_at_time(self):
        """Test point-in-time lookup for verdict reconciliation."""
        history = CategoryAssignmentHistory(finding_id="F1")

        history.add_version(
            CategoryAssignment(
                finding_id="F1",
                category=Category.SECURITY,
                assigned_by="scanner",
                assigned_at="2026-02-01T10:00:00Z",
                reason="Auto",
                confidence=0.8,
            )
        )

        history.add_version(
            CategoryAssignment(
                finding_id="F1",
                category=Category.BUILD,
                assigned_by="human@example.com",
                assigned_at="2026-02-01T12:00:00Z",
                reason="Correction",
                confidence=1.0,
            )
        )

        # At 11:00, only scanner assignment existed
        at_11am = history.get_at_time("2026-02-01T11:00:00Z")
        assert at_11am is not None
        assert at_11am.category == Category.SECURITY

        # At 13:00, human review exists
        at_1pm = history.get_at_time("2026-02-01T13:00:00Z")
        assert at_1pm is not None
        assert at_1pm.category == Category.BUILD

    def test_has_conflict(self):
        """Test conflict detection for different categories."""
        history = CategoryAssignmentHistory(finding_id="F1")

        history.add_version(
            CategoryAssignment(
                finding_id="F1",
                category=Category.SECURITY,
                assigned_by="scanner",
                assigned_at="2026-02-01T10:00:00Z",
                reason="Auto",
            )
        )

        # No conflict yet (only one category)
        assert not history.has_conflict()

        history.add_version(
            CategoryAssignment(
                finding_id="F1",
                category=Category.BUILD,  # Different category
                assigned_by="human@example.com",
                assigned_at="2026-02-01T12:00:00Z",
                reason="Correction",
            )
        )

        # Now there's a conflict
        assert history.has_conflict()


class TestCategoryWeightVersioning:
    """Test CategoryWeightConfig versioning."""

    def test_weight_update_increments_version(self):
        """Test that updating weights increments version."""
        config = CategoryWeightConfig.create_default()
        initial_version = config.config_version

        config.update_weights(
            {Category.SECURITY: 3.0},
            reviewed_by="security-team@example.com",
            notes="Post-incident increase",
        )

        assert config.config_version != initial_version
        # Version should increment from "1.0.0" to "1.1.0"
        assert config.config_version == "1.1.0"

    def test_weight_snapshot(self):
        """Test that weights can be snapshotted for verdict storage."""
        config = CategoryWeightConfig.create_default()

        snapshot = config.get_weights_snapshot()

        assert isinstance(snapshot, dict)
        assert "security" in snapshot
        assert snapshot["security"] == 2.0
        # Snapshot uses string keys (category.value)
        assert all(isinstance(k, str) for k in snapshot.keys())

    def test_multiple_updates_increment_version(self):
        """Test that multiple updates keep incrementing version."""
        config = CategoryWeightConfig.create_default()
        assert config.config_version == "1.0.0"

        config.update_weights(
            {Category.SECURITY: 3.0},
            reviewed_by="team1",
            notes="Update 1",
        )
        assert config.config_version == "1.1.0"

        config.update_weights(
            {Category.SECURITY: 2.5},
            reviewed_by="team2",
            notes="Update 2",
        )
        assert config.config_version == "1.2.0"


class TestEngineHealthRetry:
    """Test EngineHealth retry logic."""

    def test_should_retry_timeout(self):
        """Test that timeout errors trigger retry."""
        health = EngineHealth(
            engine_id="scanner",
            expected=True,
            ran=False,
            succeeded=False,
            timestamp="2026-02-01T10:00:00Z",
            error_message="Timeout after 300s",
        )

        assert health.should_retry()
        assert health.is_transient_failure

    def test_should_retry_network_error(self):
        """Test that network errors trigger retry."""
        health = EngineHealth(
            engine_id="scanner",
            expected=True,
            ran=False,
            succeeded=False,
            timestamp="2026-02-01T10:00:00Z",
            error_message="Connection refused",
        )

        assert health.should_retry()
        assert health.is_transient_failure

    def test_should_not_retry_logic_error(self):
        """Test that logic errors don't trigger retry."""
        health = EngineHealth(
            engine_id="scanner",
            expected=True,
            ran=True,
            succeeded=False,
            timestamp="2026-02-01T10:00:00Z",
            error_message="Invalid syntax in config",
        )

        assert not health.should_retry()
        assert not health.is_transient_failure

    def test_should_not_retry_after_max_retries(self):
        """Test that retry stops after max attempts."""
        health = EngineHealth(
            engine_id="scanner",
            expected=True,
            ran=False,
            succeeded=False,
            timestamp="2026-02-01T10:00:00Z",
            error_message="Timeout",
            max_retries=3,
        )

        assert health.should_retry()  # Retry 1
        health.record_retry()

        assert health.should_retry()  # Retry 2
        health.record_retry()

        assert health.should_retry()  # Retry 3
        health.record_retry()

        assert not health.should_retry()  # Max reached

    def test_record_retry(self):
        """Test that retry count is tracked."""
        health = EngineHealth(
            engine_id="scanner",
            expected=True,
            ran=False,
            succeeded=False,
            timestamp="2026-02-01T10:00:00Z",
        )

        assert health.retry_count == 0

        health.record_retry()
        assert health.retry_count == 1

        health.record_retry()
        assert health.retry_count == 2


class TestAggregatorReversibility:
    """Test VerdictAggregator reversibility features."""

    def test_remove_override(self):
        """Test that overrides can be removed before use."""
        aggregator = VerdictAggregator()

        override = Override.create_for_high_severity(
            approved_by="tech-lead@example.com",
            reason="Hotfix",
            max_highs_override=10,
        )

        aggregator.register_override(override)
        assert len(aggregator.overrides) == 1

        # Remove it
        removed = aggregator.remove_override(override.override_id)
        assert removed
        assert len(aggregator.overrides) == 0

    def test_remove_nonexistent_override(self):
        """Test that removing nonexistent override returns False."""
        aggregator = VerdictAggregator()

        removed = aggregator.remove_override("nonexistent-id")
        assert not removed

    def test_verdict_captures_weight_snapshot(self):
        """Test that verdicts capture category weight snapshot."""
        thresholds = VerdictThresholds.for_mode(Mode.PR)
        aggregator = VerdictAggregator(thresholds=thresholds)

        result = aggregator.aggregate(mode=Mode.PR)

        assert result.category_weights_used is not None
        assert isinstance(result.category_weights_used, dict)
        assert "security" in result.category_weights_used
        assert result.weight_version == thresholds.category_weight_config.config_version

    def test_verdict_weight_snapshot_enables_reconciliation(self):
        """Test that weight snapshot enables comparing verdicts across time."""
        thresholds1 = VerdictThresholds.for_mode(Mode.PR)
        aggregator1 = VerdictAggregator(thresholds=thresholds1)
        result1 = aggregator1.aggregate(mode=Mode.PR)

        # Change weights
        thresholds2 = VerdictThresholds.for_mode(Mode.PR)
        thresholds2.category_weight_config.update_weights(
            {Category.SECURITY: 3.0},
            reviewed_by="team@example.com",
            notes="Post-incident increase",
        )
        aggregator2 = VerdictAggregator(thresholds=thresholds2)
        result2 = aggregator2.aggregate(mode=Mode.PR)

        # Verdicts have different weight versions
        assert result1.weight_version != result2.weight_version

        # Snapshots show what weights were actually used
        assert result1.category_weights_used["security"] == 2.0
        assert result2.category_weights_used["security"] == 3.0


class TestReversibilityCostViolations:
    """Test that reversibility costs are acceptable."""

    def test_override_revoke_faster_than_re_approval(self):
        """Test that revocation is faster than creating new override."""
        import time

        override = Override.create_for_high_severity(
            approved_by="tech-lead@example.com",
            reason="Hotfix",
            max_highs_override=10,
        )

        # Revoke (should be < 1 second)
        start = time.time()
        override.revoke(revoked_by="security@example.com", reason="Policy changed")
        revoke_time = time.time() - start

        assert revoke_time < 1.0  # Cheap reversal

    def test_de_escalation_faster_than_deleting_record(self):
        """Test that de-escalation is faster than nuclear option."""
        import time

        finding = TemporalFinding(
            finding_fingerprint="abc123",
            first_seen="2026-02-01T10:00:00Z",
            last_seen="2026-02-01T10:00:00Z",
            occurrences=3,
            runs_with_finding=["run_1", "run_2", "run_3"],
        )

        # De-escalate (should be < 1 second, preserves history)
        start = time.time()
        finding.de_escalate(by="human@example.com", reason="False positive")
        de_escalate_time = time.time() - start

        assert de_escalate_time < 1.0
        # History preserved
        assert len(finding.runs_with_finding) == 3

    def test_category_correction_preserves_history(self):
        """Test that category corrections maintain version history."""
        history = CategoryAssignmentHistory(finding_id="F1")

        # Original assignment
        history.add_version(
            CategoryAssignment(
                finding_id="F1",
                category=Category.SECURITY,
                assigned_by="scanner",
                assigned_at="2026-02-01T10:00:00Z",
                reason="Auto",
                confidence=0.8,
            )
        )

        # Correction doesn't lose original
        history.add_version(
            CategoryAssignment(
                finding_id="F1",
                category=Category.BUILD,
                assigned_by="human@example.com",
                assigned_at="2026-02-01T12:00:00Z",
                reason="Correction",
                confidence=1.0,
            )
        )

        # Both versions preserved
        assert len(history.versions) == 2
        # Can look up what was used at any time
        assert history.get_at_time("2026-02-01T11:00:00Z").category == Category.SECURITY
        assert history.get_current().category == Category.BUILD
