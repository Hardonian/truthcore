"""Tests for the findings module."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from truthcore.findings import Finding, FindingReport, Location, Severity, severity_order


class TestSeverity:
    """Test the Severity enum."""

    def test_severity_values(self):
        """Test severity has expected values."""
        assert Severity.BLOCKER.value == "BLOCKER"
        assert Severity.HIGH.value == "HIGH"
        assert Severity.MEDIUM.value == "MEDIUM"
        assert Severity.LOW.value == "LOW"
        assert Severity.INFO.value == "INFO"

    def test_from_string(self):
        """Test parsing severity from string."""
        assert Severity.from_string("HIGH") == Severity.HIGH
        assert Severity.from_string("high") == Severity.HIGH

    def test_from_string_invalid(self):
        """Test parsing invalid severity."""
        with pytest.raises(ValueError):
            Severity.from_string("INVALID")

    def test_severity_order(self):
        """Test severity ordering."""
        assert severity_order(Severity.BLOCKER) == 4
        assert severity_order(Severity.HIGH) == 3
        assert severity_order(Severity.MEDIUM) == 2
        assert severity_order(Severity.LOW) == 1
        assert severity_order(Severity.INFO) == 0


class TestLocation:
    """Test the Location class."""

    def test_location_creation(self):
        """Test creating a location."""
        loc = Location(path="src/file.py", line=10, column=5)
        assert loc.path == "src/file.py"
        assert loc.line == 10
        assert loc.column == 5

    def test_location_to_dict(self):
        """Test converting to dict."""
        loc = Location(path="src/file.py", line=10)
        data = loc.to_dict()
        assert data["path"] == "src/file.py"
        assert data["line"] == 10


class TestFinding:
    """Test the Finding class."""

    def test_finding_creation(self):
        """Test creating a finding."""
        finding = Finding(
            rule_id="TEST_RULE",
            severity=Severity.HIGH,
            target="src/file.py",
            location=Location(path="src/file.py", line=10),
            message="Test message",
        )
        assert finding.rule_id == "TEST_RULE"
        assert finding.severity == Severity.HIGH
        assert finding.is_blocking is False

    def test_blocking_finding(self):
        """Test blocking finding."""
        finding = Finding(
            rule_id="BLOCKER_RULE",
            severity=Severity.BLOCKER,
            target="src/file.py",
            location=Location(path="src/file.py"),
            message="Blocker!",
        )
        assert finding.is_blocking is True

    def test_excerpt_hash(self):
        """Test excerpt hash is computed."""
        finding = Finding(
            rule_id="TEST_RULE",
            severity=Severity.HIGH,
            target="src/file.py",
            location=Location(path="src/file.py"),
            message="Test",
            excerpt="secret data",
        )
        assert finding.excerpt_hash is not None
        assert len(finding.excerpt_hash) == 32

    def test_with_redacted_excerpt(self):
        """Test redacting excerpt."""
        finding = Finding(
            rule_id="TEST_RULE",
            severity=Severity.HIGH,
            target="src/file.py",
            location=Location(path="src/file.py"),
            message="Test",
            excerpt="secret data",
        )
        redacted = finding.with_redacted_excerpt()
        assert redacted.excerpt == "[REDACTED]"
        assert redacted.excerpt_hash == finding.excerpt_hash

    def test_roundtrip_dict(self):
        """Test roundtrip through dict."""
        finding = Finding(
            rule_id="TEST_RULE",
            severity=Severity.HIGH,
            target="src/file.py",
            location=Location(path="src/file.py", line=10),
            message="Test message",
            excerpt="test excerpt",
            suggestion="Fix it",
        )
        data = finding.to_dict()
        finding2 = Finding.from_dict(data)
        assert finding2.rule_id == "TEST_RULE"
        assert finding2.severity == Severity.HIGH


class TestFindingReport:
    """Test the FindingReport class."""

    def test_report_creation(self):
        """Test creating a report."""
        report = FindingReport(
            tool="test-tool",
            tool_version="1.0.0",
        )
        assert report.tool == "test-tool"
        assert len(report.findings) == 0

    def test_add_finding(self):
        """Test adding findings."""
        report = FindingReport()
        finding = Finding(
            rule_id="TEST",
            severity=Severity.MEDIUM,
            target="file.py",
            location=Location(path="file.py"),
            message="Test",
        )
        report.add_finding(finding)
        assert len(report.findings) == 1

    def test_get_by_severity(self):
        """Test filtering by severity."""
        report = FindingReport()
        report.add_finding(Finding(
            rule_id="HIGH",
            severity=Severity.HIGH,
            target="file.py",
            location=Location(path="file.py"),
            message="High",
        ))
        report.add_finding(Finding(
            rule_id="MEDIUM",
            severity=Severity.MEDIUM,
            target="file.py",
            location=Location(path="file.py"),
            message="Medium",
        ))

        high_findings = report.get_by_severity(Severity.HIGH)
        assert len(high_findings) == 1
        assert high_findings[0].rule_id == "HIGH"

    def test_get_blocking(self):
        """Test getting blocking findings."""
        report = FindingReport()
        report.add_finding(Finding(
            rule_id="BLOCKER",
            severity=Severity.BLOCKER,
            target="file.py",
            location=Location(path="file.py"),
            message="Blocker",
        ))
        report.add_finding(Finding(
            rule_id="HIGH",
            severity=Severity.HIGH,
            target="file.py",
            location=Location(path="file.py"),
            message="High",
        ))

        blockers = report.get_blocking()
        assert len(blockers) == 1
        assert blockers[0].rule_id == "BLOCKER"

    def test_has_blocking(self):
        """Test checking for blocking findings."""
        report = FindingReport()
        assert report.has_blocking() is False

        report.add_finding(Finding(
            rule_id="BLOCKER",
            severity=Severity.BLOCKER,
            target="file.py",
            location=Location(path="file.py"),
            message="Blocker",
        ))
        assert report.has_blocking() is True

    def test_write_json(self, tmp_path: Path):
        """Test writing JSON output."""
        report = FindingReport()
        report.add_finding(Finding(
            rule_id="TEST",
            severity=Severity.MEDIUM,
            target="file.py",
            location=Location(path="file.py"),
            message="Test",
        ))

        json_path = tmp_path / "findings.json"
        report.write_json(json_path)

        assert json_path.exists()
        import json
        data = json.loads(json_path.read_text())
        assert data["tool"] == "unknown"
        assert data["findings_count"] == 1

    def test_write_markdown(self, tmp_path: Path):
        """Test writing Markdown output."""
        report = FindingReport(
            tool="test-tool",
            tool_version="1.0.0",
        )
        report.add_finding(Finding(
            rule_id="TEST_RULE",
            severity=Severity.HIGH,
            target="file.py",
            location=Location(path="file.py", line=10),
            message="Test message",
            excerpt="code line",
            suggestion="Fix it",
        ))

        md_path = tmp_path / "findings.md"
        report.write_markdown(md_path)

        assert md_path.exists()
        content = md_path.read_text()
        assert "TEST_RULE" in content
        assert "HIGH" in content
        assert "Test message" in content

    def test_write_csv(self, tmp_path: Path):
        """Test writing CSV output."""
        report = FindingReport()
        report.add_finding(Finding(
            rule_id="TEST",
            severity=Severity.MEDIUM,
            target="file.py",
            location=Location(path="file.py", line=5),
            message="Test",
            excerpt_hash="abc123",
        ))

        csv_path = tmp_path / "findings.csv"
        report.write_csv(csv_path)

        assert csv_path.exists()
        content = csv_path.read_text()
        assert "rule_id" in content
        assert "TEST" in content
        assert "MEDIUM" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
