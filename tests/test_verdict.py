"""Tests for Verdict Aggregator v2 (M6)."""

from __future__ import annotations

import json
import pytest
from pathlib import Path

from truthcore.verdict import (
    VerdictAggregator,
    VerdictThresholds,
    aggregate_verdict,
)
from truthcore.verdict.models import (
    Category,
    EngineContribution,
    Mode,
    SeverityLevel,
    VerdictResult,
    VerdictStatus,
    WeightedFinding,
)


class TestVerdictThresholds:
    """Tests for verdict thresholds."""

    def test_pr_mode_thresholds(self):
        """Test PR mode has lenient thresholds."""
        thresholds = VerdictThresholds.for_mode(Mode.PR)
        
        assert thresholds.mode == Mode.PR
        assert thresholds.max_blockers == 0
        assert thresholds.max_highs == 5
        assert thresholds.max_total_points == 150

    def test_main_mode_thresholds(self):
        """Test main mode has balanced thresholds."""
        thresholds = VerdictThresholds.for_mode(Mode.MAIN)
        
        assert thresholds.mode == Mode.MAIN
        assert thresholds.max_blockers == 0
        assert thresholds.max_highs == 2
        assert thresholds.max_total_points == 75

    def test_release_mode_thresholds(self):
        """Test release mode has strict thresholds."""
        thresholds = VerdictThresholds.for_mode(Mode.RELEASE)
        
        assert thresholds.mode == Mode.RELEASE
        assert thresholds.max_blockers == 0
        assert thresholds.max_highs == 0
        assert thresholds.max_total_points == 20

    def test_category_weights(self):
        """Test category weights are configured."""
        thresholds = VerdictThresholds.for_mode(Mode.PR)
        
        assert thresholds.get_category_weight(Category.SECURITY) == 2.0
        assert thresholds.get_category_weight(Category.PRIVACY) == 2.0
        assert thresholds.get_category_weight(Category.UI) == 1.0

    def test_severity_weights(self):
        """Test severity weights."""
        thresholds = VerdictThresholds.for_mode(Mode.PR)
        
        assert thresholds.get_severity_weight(SeverityLevel.BLOCKER) == float('inf')
        assert thresholds.get_severity_weight(SeverityLevel.HIGH) == 50.0


class TestVerdictAggregator:
    """Tests for verdict aggregator."""

    def test_empty_aggregation(self):
        """Test aggregation with no findings."""
        aggregator = VerdictAggregator()
        result = aggregator.aggregate(mode=Mode.PR)
        
        assert result.verdict == VerdictStatus.SHIP
        assert result.total_findings == 0
        assert result.total_points == 0

    def test_single_finding(self):
        """Test aggregation with single finding."""
        aggregator = VerdictAggregator()
        aggregator.add_finding(
            finding_id="test-1",
            tool="eslint",
            severity=SeverityLevel.LOW,
            category=Category.BUILD,
            message="Minor issue",
        )
        
        result = aggregator.aggregate(mode=Mode.PR)
        
        assert result.total_findings == 1
        assert result.lows == 1
        assert result.verdict == VerdictStatus.SHIP  # Low issues don't block

    def test_blocker_causes_no_ship(self):
        """Test that blockers cause NO_SHIP."""
        aggregator = VerdictAggregator()
        aggregator.add_finding(
            finding_id="blocker-1",
            tool="security",
            severity=SeverityLevel.BLOCKER,
            category=Category.SECURITY,
            message="Critical security issue",
        )
        
        result = aggregator.aggregate(mode=Mode.PR)
        
        assert result.verdict == VerdictStatus.NO_SHIP
        assert result.blockers == 1
        assert len(result.no_ship_reasons) > 0

    def test_high_threshold(self):
        """Test high severity threshold."""
        thresholds = VerdictThresholds.for_mode(Mode.MAIN)
        aggregator = VerdictAggregator(thresholds)
        
        # Add more highs than allowed
        for i in range(thresholds.max_highs + 2):
            aggregator.add_finding(
                finding_id=f"high-{i}",
                tool="eslint",
                severity=SeverityLevel.HIGH,
                category=Category.BUILD,
                message=f"High issue {i}",
            )
        
        result = aggregator.aggregate(mode=Mode.MAIN)
        
        assert result.highs > thresholds.max_highs
        assert result.verdict == VerdictStatus.NO_SHIP

    def test_points_threshold(self):
        """Test total points threshold."""
        thresholds = VerdictThresholds.for_mode(Mode.MAIN)
        aggregator = VerdictAggregator(thresholds)
        
        # Add enough high severity issues to exceed points
        for i in range(5):
            aggregator.add_finding(
                finding_id=f"high-{i}",
                tool="test",
                severity=SeverityLevel.HIGH,
                category=Category.BUILD,
                message=f"Issue {i}",
            )
        
        result = aggregator.aggregate(mode=Mode.MAIN)
        
        assert result.total_points > thresholds.max_total_points
        assert result.verdict == VerdictStatus.NO_SHIP

    def test_category_points_calculation(self):
        """Test category-specific points."""
        aggregator = VerdictAggregator()
        
        # Add security finding (2.0x weight)
        aggregator.add_finding(
            finding_id="sec-1",
            tool="security",
            severity=SeverityLevel.HIGH,
            category=Category.SECURITY,
            message="Security issue",
        )
        
        # Add UI finding (1.0x weight)
        aggregator.add_finding(
            finding_id="ui-1",
            tool="test",
            severity=SeverityLevel.HIGH,
            category=Category.UI,
            message="UI issue",
        )
        
        result = aggregator.aggregate(mode=Mode.PR)
        
        # Security should have more points due to weight
        sec_category = next(c for c in result.categories if c.category == Category.SECURITY)
        ui_category = next(c for c in result.categories if c.category == Category.UI)
        
        assert sec_category.points_contributed > ui_category.points_contributed

    def test_engine_contributions(self):
        """Test engine contribution tracking."""
        aggregator = VerdictAggregator()
        
        aggregator.add_finding(
            finding_id="eslint-1",
            tool="eslint",
            severity=SeverityLevel.HIGH,
            category=Category.BUILD,
            message="ESLint issue",
            source_engine="readiness",
        )
        
        aggregator.add_finding(
            finding_id="policy-1",
            tool="policy",
            severity=SeverityLevel.MEDIUM,
            category=Category.SECURITY,
            message="Policy issue",
            source_engine="policy",
        )
        
        result = aggregator.aggregate(mode=Mode.PR)
        
        assert len(result.engines) == 2
        engine_ids = [e.engine_id for e in result.engines]
        assert "readiness" in engine_ids
        assert "policy" in engine_ids

    def test_top_findings_sorted(self):
        """Test that top findings are sorted by severity."""
        aggregator = VerdictAggregator()
        
        # Add findings in random order
        aggregator.add_finding(
            finding_id="low-1",
            tool="test",
            severity=SeverityLevel.LOW,
            category=Category.BUILD,
            message="Low issue",
        )
        
        aggregator.add_finding(
            finding_id="blocker-1",
            tool="test",
            severity=SeverityLevel.BLOCKER,
            category=Category.SECURITY,
            message="Blocker issue",
        )
        
        aggregator.add_finding(
            finding_id="high-1",
            tool="test",
            severity=SeverityLevel.HIGH,
            category=Category.BUILD,
            message="High issue",
        )
        
        result = aggregator.aggregate(mode=Mode.PR)
        
        # Blocker should be first
        assert result.top_findings[0].severity == SeverityLevel.BLOCKER
        # High should be second
        assert result.top_findings[1].severity == SeverityLevel.HIGH


class TestVerdictModes:
    """Tests for different execution modes."""

    def test_pr_mode_allows_issues(self):
        """Test PR mode is lenient."""
        aggregator = VerdictAggregator(VerdictThresholds.for_mode(Mode.PR))

        # Add a few high issues (within PR tolerance)
        # Use GENERAL category (1.0x weight) so 3 highs = 150 points (at limit)
        for i in range(3):
            aggregator.add_finding(
                finding_id=f"high-{i}",
                tool="test",
                severity=SeverityLevel.HIGH,
                category=Category.GENERAL,
                message=f"Issue {i}",
            )

        result = aggregator.aggregate(mode=Mode.PR)

        # PR mode allows up to 5 highs and 150 points (3*50=150 should pass)
        assert result.verdict == VerdictStatus.SHIP

    def test_release_mode_strict(self):
        """Test release mode is strict."""
        aggregator = VerdictAggregator(VerdictThresholds.for_mode(Mode.RELEASE))
        
        # Single high issue should fail in release mode
        aggregator.add_finding(
            finding_id="high-1",
            tool="test",
            severity=SeverityLevel.HIGH,
            category=Category.BUILD,
            message="High issue",
        )
        
        result = aggregator.aggregate(mode=Mode.RELEASE)
        
        assert result.verdict == VerdictStatus.NO_SHIP

    def test_main_mode_balanced(self):
        """Test main mode is balanced."""
        aggregator = VerdictAggregator(VerdictThresholds.for_mode(Mode.MAIN))

        # One high issue within limit (1 * 50 * 1.5 for BUILD = 75, at limit)
        aggregator.add_finding(
            finding_id="high-1",
            tool="test",
            severity=SeverityLevel.HIGH,
            category=Category.BUILD,
            message="Issue 1",
        )

        result = aggregator.aggregate(mode=Mode.MAIN)

        # Debug
        print(f"\nDEBUG: total_points={result.total_points}, highs={result.highs}")
        print(f"DEBUG: categories={[(c.category.value, c.points_contributed, c.max_allowed) for c in result.categories]}")
        print(f"DEBUG: no_ship_reasons={result.no_ship_reasons}")

        # At limit, should be SHIP
        assert result.verdict == VerdictStatus.SHIP


class TestAggregateVerdictFunction:
    """Tests for the aggregate_verdict convenience function."""

    def test_aggregate_from_empty_files(self, tmp_path: Path):
        """Test aggregation with empty input directory."""
        # Create empty files
        readiness = tmp_path / "readiness.json"
        readiness.write_text('{"findings": []}')
        
        result = aggregate_verdict([readiness], mode="pr")
        
        assert result.verdict == VerdictStatus.SHIP
        assert result.total_findings == 0

    def test_aggregate_with_findings(self, tmp_path: Path):
        """Test aggregation with findings in files."""
        # Create file with findings
        readiness = tmp_path / "readiness.json"
        data = {
            "findings": [
                {
                    "id": "error-1",
                    "severity": "HIGH",
                    "category": "build",
                    "message": "Build error",
                }
            ]
        }
        readiness.write_text(json.dumps(data))
        
        result = aggregate_verdict([readiness], mode="pr")
        
        assert result.total_findings == 1
        assert result.highs == 1

    def test_aggregate_missing_file(self, tmp_path: Path):
        """Test aggregation handles missing files gracefully."""
        # Try to aggregate with non-existent file
        missing = tmp_path / "missing.json"
        
        # Should not raise, just skip
        result = aggregate_verdict([missing], mode="pr")
        
        assert result.total_findings == 0


class TestVerdictOutput:
    """Tests for verdict output formats."""

    def test_to_dict_structure(self):
        """Test verdict dict structure."""
        aggregator = VerdictAggregator()
        aggregator.add_finding(
            finding_id="test-1",
            tool="test",
            severity=SeverityLevel.LOW,
            category=Category.BUILD,
            message="Test",
        )
        
        result = aggregator.aggregate(mode=Mode.PR)
        data = result.to_dict()
        
        assert "verdict" in data
        assert "version" in data
        assert "timestamp" in data
        assert "summary" in data
        assert "engines" in data
        assert "categories" in data
        assert "reasoning" in data

    def test_to_markdown_structure(self):
        """Test markdown output structure."""
        aggregator = VerdictAggregator()
        aggregator.add_finding(
            finding_id="test-1",
            tool="test",
            severity=SeverityLevel.HIGH,
            category=Category.BUILD,
            message="Test issue",
        )
        
        result = aggregator.aggregate(mode=Mode.PR)
        markdown = result.to_markdown()
        
        assert "# Verdict Report" in markdown
        assert "Verdict:" in markdown
        assert "## Summary" in markdown

    def test_json_roundtrip(self, tmp_path: Path):
        """Test JSON serialization roundtrip."""
        aggregator = VerdictAggregator()
        aggregator.add_finding(
            finding_id="test-1",
            tool="test",
            severity=SeverityLevel.LOW,
            category=Category.BUILD,
            message="Test",
        )
        
        result = aggregator.aggregate(mode=Mode.PR)
        
        # Write and read back
        json_path = tmp_path / "verdict.json"
        result.write_json(json_path)
        
        data = json.loads(json_path.read_text())
        assert data["verdict"] == "SHIP"

    def test_markdown_output(self, tmp_path: Path):
        """Test markdown file output."""
        aggregator = VerdictAggregator()
        
        result = aggregator.aggregate(mode=Mode.PR)
        
        md_path = tmp_path / "verdict.md"
        result.write_markdown(md_path)
        
        content = md_path.read_text()
        assert "# Verdict Report" in content


class TestDeterminism:
    """Tests for verdict determinism."""

    def test_same_findings_same_result(self):
        """Test that same findings produce same result."""
        findings_data = [
            ("high-1", SeverityLevel.HIGH, "Issue 1"),
            ("low-1", SeverityLevel.LOW, "Issue 2"),
            ("med-1", SeverityLevel.MEDIUM, "Issue 3"),
        ]
        
        results = []
        for _ in range(5):
            aggregator = VerdictAggregator()
            for fid, sev, msg in findings_data:
                aggregator.add_finding(
                    finding_id=fid,
                    tool="test",
                    severity=sev,
                    category=Category.BUILD,
                    message=msg,
                )
            result = aggregator.aggregate(mode=Mode.PR)
            results.append(result)
        
        # All should have same verdict
        assert all(r.verdict == results[0].verdict for r in results)
        assert all(r.total_points == results[0].total_points for r in results)

    def test_deterministic_ordering(self):
        """Test that findings are ordered deterministically."""
        aggregator = VerdictAggregator()
        
        # Add in random order
        for i in range(10):
            severity = [
                SeverityLevel.LOW,
                SeverityLevel.MEDIUM,
                SeverityLevel.HIGH,
            ][i % 3]
            aggregator.add_finding(
                finding_id=f"finding-{i}",
                tool="test",
                severity=severity,
                category=Category.BUILD,
                message=f"Issue {i}",
            )
        
        result = aggregator.aggregate(mode=Mode.PR)
        
        # Run multiple times and check order
        severities_list = []
        for _ in range(3):
            agg = VerdictAggregator()
            for i in range(10):
                severity = [
                    SeverityLevel.LOW,
                    SeverityLevel.MEDIUM,
                    SeverityLevel.HIGH,
                ][i % 3]
                agg.add_finding(
                    finding_id=f"finding-{i}",
                    tool="test",
                    severity=severity,
                    category=Category.BUILD,
                    message=f"Issue {i}",
                )
            res = agg.aggregate(mode=Mode.PR)
            severities = [f.severity.value for f in res.top_findings[:5]]
            severities_list.append(severities)
        
        # All orders should match
        assert all(s == severities_list[0] for s in severities_list)
