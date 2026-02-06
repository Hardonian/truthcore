"""Unified severity and governance models for TruthCore.

This module provides type-safe severity levels and governance primitives
that are shared across findings, verdicts, and policy systems.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from truthcore.determinism import stable_isoformat, stable_now


class Severity(Enum):
    """Unified severity levels across all TruthCore systems.

    This is the single source of truth for severity levels.
    All subsystems (findings, verdict, policy) MUST use this enum.
    """

    BLOCKER = "BLOCKER"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"

    @classmethod
    def from_string(cls, value: str) -> Severity:
        """Parse severity from string (case-insensitive)."""
        value = value.upper()
        for member in cls:
            if member.value == value:
                return member
        raise ValueError(f"Unknown severity: {value}")

    def __lt__(self, other: Severity) -> bool:
        """Compare severity levels (higher severity > lower severity)."""
        if not isinstance(other, Severity):
            return NotImplemented
        order = {
            Severity.INFO: 0,
            Severity.LOW: 1,
            Severity.MEDIUM: 2,
            Severity.HIGH: 3,
            Severity.BLOCKER: 4,
        }
        return order[self] < order[other]

    def __le__(self, other: Severity) -> bool:
        """Compare severity levels (less than or equal)."""
        return self < other or self == other

    def __gt__(self, other: Severity) -> bool:
        """Compare severity levels (greater than)."""
        if not isinstance(other, Severity):
            return NotImplemented
        return not (self <= other)

    def __ge__(self, other: Severity) -> bool:
        """Compare severity levels (greater than or equal)."""
        return not (self < other)


def severity_order(severity: Severity | str) -> int:
    """Get numeric order for severity (higher = more severe)."""
    if isinstance(severity, str):
        severity = Severity.from_string(severity)
    order = {
        Severity.INFO: 0,
        Severity.LOW: 1,
        Severity.MEDIUM: 2,
        Severity.HIGH: 3,
        Severity.BLOCKER: 4,
    }
    return order.get(severity, 0)


class Category(Enum):
    """Finding categories with governance implications.

    Categories are not arbitrary labels - they carry weight multipliers
    and audit requirements. Assignment must be governed.
    """

    UI = "ui"
    BUILD = "build"
    TYPES = "types"
    SECURITY = "security"
    PRIVACY = "privacy"
    FINANCE = "finance"
    AGENT = "agent"
    KNOWLEDGE = "knowledge"
    GENERAL = "general"

    @classmethod
    def from_string(cls, value: str) -> Category:
        """Parse category from string (case-insensitive)."""
        value = value.lower()
        for member in cls:
            if member.value == value:
                return member
        raise ValueError(f"Unknown category: {value}")


@dataclass
class CategoryAssignment:
    """Auditable record of category assignment.

    Tracks WHO assigned a category, WHEN, and WHY.
    This prevents silent category inflation that would game the scoring system.
    """

    finding_id: str
    category: Category
    assigned_by: str  # Engine, rule, or human identifier
    assigned_at: str  # ISO timestamp
    reason: str  # Why this category was chosen
    confidence: float = 1.0  # 0.0-1.0, for automated assignments
    reviewed: bool = False  # Has a human reviewed this?
    reviewer: str | None = None
    reviewed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "finding_id": self.finding_id,
            "category": self.category.value,
            "assigned_by": self.assigned_by,
            "assigned_at": self.assigned_at,
            "reason": self.reason,
            "confidence": self.confidence,
            "reviewed": self.reviewed,
            "reviewer": self.reviewer,
            "reviewed_at": self.reviewed_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CategoryAssignment:
        """Create from dictionary."""
        return cls(
            finding_id=data["finding_id"],
            category=Category.from_string(data["category"]),
            assigned_by=data["assigned_by"],
            assigned_at=data["assigned_at"],
            reason=data["reason"],
            confidence=data.get("confidence", 1.0),
            reviewed=data.get("reviewed", False),
            reviewer=data.get("reviewer"),
            reviewed_at=data.get("reviewed_at"),
        )


@dataclass
class Override:
    """Governance record for verdict overrides.

    Overrides are not thresholds - they are human decisions with accountability.
    Each override MUST have: who approved it, why, when, and when it expires.
    """

    override_id: str
    approved_by: str  # Human approver (email, username, etc.)
    approved_at: str  # ISO timestamp
    expires_at: str  # ISO timestamp
    reason: str
    scope: str  # What this override allows (e.g., "max_highs: 5 -> 10")
    conditions: list[str] = field(default_factory=list)  # Conditions that must be met
    used: bool = False
    used_at: str | None = None
    verdict_id: str | None = None  # Link to verdict that used this override

    def is_valid(self) -> bool:
        """Check if override is still valid (not expired, not yet used)."""
        if self.used:
            return False
        try:
            expires_dt = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
            return stable_now() < expires_dt
        except ValueError:
            return False

    def is_expired(self) -> bool:
        """Check if override has expired."""
        try:
            expires_dt = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
            return stable_now() >= expires_dt
        except ValueError:
            return True

    def mark_used(self, verdict_id: str) -> None:
        """Mark override as used."""
        self.used = True
        self.used_at = stable_isoformat()
        self.verdict_id = verdict_id

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "override_id": self.override_id,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "expires_at": self.expires_at,
            "reason": self.reason,
            "scope": self.scope,
            "conditions": self.conditions,
            "used": self.used,
            "used_at": self.used_at,
            "verdict_id": self.verdict_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Override:
        """Create from dictionary."""
        return cls(
            override_id=data["override_id"],
            approved_by=data["approved_by"],
            approved_at=data["approved_at"],
            expires_at=data["expires_at"],
            reason=data["reason"],
            scope=data["scope"],
            conditions=data.get("conditions", []),
            used=data.get("used", False),
            used_at=data.get("used_at"),
            verdict_id=data.get("verdict_id"),
        )

    @classmethod
    def create_for_high_severity(
        cls,
        approved_by: str,
        reason: str,
        max_highs_override: int,
        duration_hours: int = 24,
    ) -> Override:
        """Convenience constructor for high-severity overrides."""
        now = stable_now()
        expires = now + timedelta(hours=duration_hours)
        return cls(
            override_id=f"override-highs-{int(now.timestamp())}",
            approved_by=approved_by,
            approved_at=now.isoformat(),
            expires_at=expires.isoformat(),
            reason=reason,
            scope=f"max_highs_with_override: {max_highs_override}",
            conditions=[f"Must resolve within {duration_hours} hours"],
        )


@dataclass
class TemporalFinding:
    """Temporal tracking of a finding across multiple runs.

    Chronic issues (appearing repeatedly) should escalate in severity.
    This provides the evidence trail needed for that escalation.
    """

    finding_fingerprint: str  # Stable hash of rule_id + location
    first_seen: str  # ISO timestamp
    last_seen: str  # ISO timestamp
    occurrences: int = 1
    runs_with_finding: list[str] = field(default_factory=list)  # Run IDs
    severity_history: list[tuple[str, str]] = field(default_factory=list)  # [(timestamp, severity)]
    escalated: bool = False
    escalated_at: str | None = None
    escalation_reason: str | None = None

    def should_escalate(self, threshold_occurrences: int = 3) -> bool:
        """Determine if this finding should be escalated due to chronicity."""
        if self.escalated:
            return False
        return self.occurrences >= threshold_occurrences

    def escalate(self, reason: str) -> None:
        """Mark finding as escalated."""
        self.escalated = True
        self.escalated_at = stable_isoformat()
        self.escalation_reason = reason

    def record_occurrence(self, run_id: str, severity: str) -> None:
        """Record a new occurrence of this finding."""
        self.last_seen = stable_isoformat()
        self.occurrences += 1
        if run_id not in self.runs_with_finding:
            self.runs_with_finding.append(run_id)
        self.severity_history.append((stable_isoformat(), severity))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "finding_fingerprint": self.finding_fingerprint,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "occurrences": self.occurrences,
            "runs_with_finding": self.runs_with_finding,
            "severity_history": self.severity_history,
            "escalated": self.escalated,
            "escalated_at": self.escalated_at,
            "escalation_reason": self.escalation_reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TemporalFinding:
        """Create from dictionary."""
        return cls(
            finding_fingerprint=data["finding_fingerprint"],
            first_seen=data["first_seen"],
            last_seen=data["last_seen"],
            occurrences=data.get("occurrences", 1),
            runs_with_finding=data.get("runs_with_finding", []),
            severity_history=data.get("severity_history", []),
            escalated=data.get("escalated", False),
            escalated_at=data.get("escalated_at"),
            escalation_reason=data.get("escalation_reason"),
        )


@dataclass
class EngineHealth:
    """Health check record for an engine.

    Silence is NOT health. Engines must actively report their status.
    Missing engines should degrade the verdict, not improve it.
    """

    engine_id: str
    expected: bool  # Was this engine expected to run?
    ran: bool  # Did this engine actually run?
    succeeded: bool  # Did the engine complete successfully?
    timestamp: str  # ISO timestamp
    findings_reported: int = 0
    error_message: str | None = None
    execution_time_ms: float | None = None

    def is_healthy(self) -> bool:
        """Determine if engine is healthy."""
        if not self.expected:
            return True  # Not expected, so absence is OK
        if not self.ran:
            return False  # Expected but didn't run
        return self.succeeded  # Ran, so check if it succeeded

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "engine_id": self.engine_id,
            "expected": self.expected,
            "ran": self.ran,
            "succeeded": self.succeeded,
            "timestamp": self.timestamp,
            "findings_reported": self.findings_reported,
            "error_message": self.error_message,
            "execution_time_ms": self.execution_time_ms,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EngineHealth:
        """Create from dictionary."""
        return cls(
            engine_id=data["engine_id"],
            expected=data["expected"],
            ran=data["ran"],
            succeeded=data["succeeded"],
            timestamp=data["timestamp"],
            findings_reported=data.get("findings_reported", 0),
            error_message=data.get("error_message"),
            execution_time_ms=data.get("execution_time_ms"),
        )


@dataclass
class CategoryWeightConfig:
    """Configuration for category weights with governance.

    Weights are not constants - they encode organizational values
    and must be reviewed periodically.
    """

    weights: dict[Category, float] = field(default_factory=dict)
    config_version: str = "1.0.0"
    last_reviewed: str = field(default_factory=stable_isoformat)
    review_frequency_days: int = 90  # Require review every 90 days
    reviewed_by: str | None = None
    review_notes: str | None = None

    def is_review_overdue(self) -> bool:
        """Check if weight configuration needs review."""
        try:
            last_review_dt = datetime.fromisoformat(self.last_reviewed.replace("Z", "+00:00"))
            next_review = last_review_dt + timedelta(days=self.review_frequency_days)
            return stable_now() >= next_review
        except ValueError:
            return True  # If we can't parse, assume review is needed

    def get_weight(self, category: Category) -> float:
        """Get weight for a category."""
        return self.weights.get(category, 1.0)

    def update_weights(self, new_weights: dict[Category, float], reviewed_by: str, notes: str) -> None:
        """Update weights and record review."""
        self.weights = new_weights
        self.last_reviewed = stable_isoformat()
        self.reviewed_by = reviewed_by
        self.review_notes = notes

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "weights": {k.value: v for k, v in self.weights.items()},
            "config_version": self.config_version,
            "last_reviewed": self.last_reviewed,
            "review_frequency_days": self.review_frequency_days,
            "reviewed_by": self.reviewed_by,
            "review_notes": self.review_notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CategoryWeightConfig:
        """Create from dictionary."""
        weights = {Category.from_string(k): v for k, v in data.get("weights", {}).items()}
        return cls(
            weights=weights,
            config_version=data.get("config_version", "1.0.0"),
            last_reviewed=data.get("last_reviewed", stable_isoformat()),
            review_frequency_days=data.get("review_frequency_days", 90),
            reviewed_by=data.get("reviewed_by"),
            review_notes=data.get("review_notes"),
        )

    @classmethod
    def create_default(cls) -> CategoryWeightConfig:
        """Create default category weight configuration."""
        return cls(
            weights={
                Category.SECURITY: 2.0,
                Category.PRIVACY: 2.0,
                Category.FINANCE: 1.5,
                Category.BUILD: 1.5,
                Category.TYPES: 1.2,
                Category.UI: 1.0,
                Category.AGENT: 1.0,
                Category.KNOWLEDGE: 1.0,
                Category.GENERAL: 1.0,
            },
            reviewed_by="system",
            review_notes="Default weight configuration",
        )
