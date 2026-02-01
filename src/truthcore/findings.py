"""Shared finding models for truth-core.

This module provides unified dataclasses for findings across
invariants, policy, and other verification systems.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any


class Severity(Enum):
    """Severity levels for findings."""

    BLOCKER = "BLOCKER"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"

    @classmethod
    def from_string(cls, value: str) -> Severity:
        """Parse severity from string."""
        value = value.upper()
        for member in cls:
            if member.value == value:
                return member
        raise ValueError(f"Unknown severity: {value}")


@dataclass
class Location:
    """Location of a finding within a file."""

    path: str
    line: int | None = None
    column: int | None = None
    byte_offset: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "path": self.path,
            "line": self.line,
            "column": self.column,
            "byte_offset": self.byte_offset,
        }


@dataclass
class Finding:
    """Unified finding model for all verification systems.

    Attributes:
        rule_id: Unique identifier for the rule that produced this finding
        severity: Severity level (BLOCKER, HIGH, MEDIUM, LOW, INFO)
        target: What was being checked (file, log entry, config key, etc.)
        location: Where in the target the issue was found
        message: Human-readable description of the finding
        excerpt: Snippet of content that triggered the finding (may be hashed/redacted)
        excerpt_hash: SHA-256 hash of the original excerpt
        suggestion: Optional suggestion for remediation
        metadata: Additional context-specific data
        timestamp: When the finding was created (ISO format)
    """

    rule_id: str
    severity: Severity
    target: str
    location: Location
    message: str
    excerpt: str | None = None
    excerpt_hash: str | None = None
    suggestion: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def __post_init__(self):
        """Ensure timestamp is ISO format and compute excerpt hash if needed."""
        if isinstance(self.timestamp, datetime):
            self.timestamp = self.timestamp.isoformat()
        if self.excerpt and not self.excerpt_hash:
            self.excerpt_hash = hashlib.sha256(self.excerpt.encode("utf-8")).hexdigest()[:32]

    def to_dict(self) -> dict[str, Any]:
        """Convert finding to dictionary with stable ordering."""
        return {
            "rule_id": self.rule_id,
            "severity": self.severity.value,
            "target": self.target,
            "location": self.location.to_dict(),
            "message": self.message,
            "excerpt": self.excerpt,
            "excerpt_hash": self.excerpt_hash,
            "suggestion": self.suggestion,
            "metadata": dict(sorted(self.metadata.items())),
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Finding:
        """Create finding from dictionary."""
        return cls(
            rule_id=data["rule_id"],
            severity=Severity.from_string(data["severity"]),
            target=data["target"],
            location=Location(
                path=data["location"]["path"],
                line=data["location"].get("line"),
                column=data["location"].get("column"),
                byte_offset=data["location"].get("byte_offset"),
            ),
            message=data["message"],
            excerpt=data.get("excerpt"),
            excerpt_hash=data.get("excerpt_hash"),
            suggestion=data.get("suggestion"),
            metadata=data.get("metadata", {}),
            timestamp=data.get("timestamp", datetime.now(UTC).isoformat()),
        )

    def with_redacted_excerpt(self) -> Finding:
        """Return copy with excerpt redacted but hash preserved."""
        return Finding(
            rule_id=self.rule_id,
            severity=self.severity,
            target=self.target,
            location=self.location,
            message=self.message,
            excerpt="[REDACTED]",
            excerpt_hash=self.excerpt_hash,
            suggestion=self.suggestion,
            metadata=self.metadata,
            timestamp=self.timestamp,
        )

    @property
    def is_blocking(self) -> bool:
        """Check if finding is blocking (BLOCKER severity)."""
        return self.severity == Severity.BLOCKER


@dataclass
class FindingReport:
    """Collection of findings with metadata."""

    findings: list[Finding] = field(default_factory=list)
    tool: str = "unknown"
    tool_version: str = "unknown"
    run_id: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Ensure timestamp is ISO format."""
        if isinstance(self.timestamp, datetime):
            self.timestamp = self.timestamp.isoformat()

    def add_finding(self, finding: Finding) -> None:
        """Add a finding to the report."""
        self.findings.append(finding)

    def get_by_severity(self, severity: Severity) -> list[Finding]:
        """Get all findings of a specific severity."""
        return [f for f in self.findings if f.severity == severity]

    def get_blocking(self) -> list[Finding]:
        """Get all blocking findings."""
        return self.get_by_severity(Severity.BLOCKER)

    def has_blocking(self) -> bool:
        """Check if any findings are blocking."""
        return any(f.is_blocking for f in self.findings)

    def to_dict(self) -> dict[str, Any]:
        """Convert report to dictionary."""
        return {
            "tool": self.tool,
            "tool_version": self.tool_version,
            "run_id": self.run_id,
            "timestamp": self.timestamp,
            "findings_count": len(self.findings),
            "findings": [f.to_dict() for f in self.findings],
            "metadata": dict(sorted(self.metadata.items())),
        }

    def write_json(self, path: Path) -> None:
        """Write report as JSON."""
        import json

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, sort_keys=True)

    def write_markdown(self, path: Path) -> None:
        """Write report as Markdown."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self._generate_markdown())

    def _generate_markdown(self) -> str:
        """Generate markdown representation."""
        lines = [
            f"# {self.tool} Report",
            "",
            f"**Tool Version:** {self.tool_version}",
            f"**Run ID:** {self.run_id or 'N/A'}",
            f"**Timestamp:** {self.timestamp}",
            f"**Total Findings:** {len(self.findings)}",
            "",
            "## Summary by Severity",
            "",
        ]

        for sev in Severity:
            count = len(self.get_by_severity(sev))
            if count > 0:
                lines.append(f"- **{sev.value}**: {count}")

        lines.extend(["", "## Findings", ""])

        if not self.findings:
            lines.append("No findings.")
        else:
            for finding in sorted(self.findings, key=lambda f: f.severity.value):
                lines.extend([
                    f"### {finding.rule_id}",
                    "",
                    f"- **Severity:** {finding.severity.value}",
                    f"- **Target:** {finding.target}",
                    f"- **Location:** {finding.location.path}",
                ])
                if finding.location.line:
                    lines.append(f"- **Line:** {finding.location.line}")
                lines.extend([
                    "",
                    f"**Message:** {finding.message}",
                    "",
                ])
                if finding.excerpt:
                    lines.extend([
                        "**Excerpt:**",
                        "",
                        "```",
                        finding.excerpt[:500],  # Limit excerpt length
                        "```",
                        "",
                    ])
                if finding.excerpt_hash:
                    lines.append(f"**Excerpt Hash:** `{finding.excerpt_hash}`")
                if finding.suggestion:
                    lines.extend([
                        "",
                        f"**Suggestion:** {finding.suggestion}",
                    ])
                lines.append("")

        return "\n".join(lines)

    def write_csv(self, path: Path) -> None:
        """Write report as CSV summary."""
        import csv

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["rule_id", "severity", "target", "path", "line", "message", "excerpt_hash"])
            for finding in self.findings:
                writer.writerow([
                    finding.rule_id,
                    finding.severity.value,
                    finding.target,
                    finding.location.path,
                    finding.location.line or "",
                    finding.message,
                    finding.excerpt_hash or "",
                ])


def severity_order(severity: Severity | str) -> int:
    """Get numeric order for severity (higher = more severe)."""
    order = {
        Severity.INFO: 0,
        Severity.LOW: 1,
        Severity.MEDIUM: 2,
        Severity.HIGH: 3,
        Severity.BLOCKER: 4,
    }
    if isinstance(severity, str):
        severity = Severity.from_string(severity)
    return order.get(severity, 0)
