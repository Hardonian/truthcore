"""Unified severity and governance models for TruthCore.

This module provides type-safe severity levels and governance primitives
that are shared across findings, verdicts, and policy systems.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any


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
    version: int = 1  # Assignment version for tracking corrections

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
            "version": self.version,
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
            version=data.get("version", 1),
        )


@dataclass
class CategoryAssignmentHistory:
    """Version history for category assignments with conflict resolution.

    Tracks all category assignments for a finding to enable:
    - Conflict resolution (scanner vs human)
    - Audit trail of corrections
    - Point-in-time lookup for verdict reconciliation
    """

    finding_id: str
    versions: list[CategoryAssignment] = field(default_factory=list)

    def add_version(self, assignment: CategoryAssignment) -> None:
        """Add a new version to history."""
        assignment.version = len(self.versions) + 1
        self.versions.append(assignment)

    def get_current(self) -> CategoryAssignment | None:
        """Get current authoritative assignment.

        Resolution rules:
        1. Highest confidence wins (human review = 1.0 > scanner = 0.8)
        2. If confidence tied, latest timestamp wins
        3. If no versions, return None
        """
        if not self.versions:
            return None
        return max(self.versions, key=lambda a: (a.confidence, a.assigned_at))

    def get_at_time(self, timestamp: str) -> CategoryAssignment | None:
        """Get assignment that was active at given timestamp.

        Used for verdict reconciliation to determine which category
        was authoritative when a verdict was issued.
        """
        valid_versions = [a for a in self.versions if a.assigned_at <= timestamp]
        if not valid_versions:
            return None
        return max(valid_versions, key=lambda a: (a.confidence, a.assigned_at))

    def has_conflict(self) -> bool:
        """Check if there are conflicting assignments (different categories)."""
        if len(self.versions) <= 1:
            return False
        categories = {a.category for a in self.versions}
        return len(categories) > 1

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "finding_id": self.finding_id,
            "versions": [v.to_dict() for v in self.versions],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CategoryAssignmentHistory:
        """Create from dictionary."""
        versions = [CategoryAssignment.from_dict(v) for v in data.get("versions", [])]
        return cls(
            finding_id=data["finding_id"],
            versions=versions,
        )


@dataclass
class OverrideScope:
    """Structured scope for override validation.

    Replaces free-text scope with validated schema.
    """

    scope_type: str  # "max_highs", "max_points", "max_category_points"
    limit: int  # New limit value
    original_limit: int | None = None  # Original threshold (for audit)

    def to_string(self) -> str:
        """Convert to legacy string format for compatibility."""
        if self.original_limit is not None:
            return f"{self.scope_type}: {self.original_limit} -> {self.limit}"
        return f"{self.scope_type}: {self.limit}"

    @classmethod
    def from_string(cls, scope_str: str) -> OverrideScope:
        """Parse legacy string format."""
        # Handle "max_highs: 5 -> 10" or "max_highs: 10"
        if ":" not in scope_str:
            raise ValueError(f"Invalid scope format: {scope_str}")

        parts = scope_str.split(":")
        scope_type = parts[0].strip().replace("_with_override", "")  # Handle legacy format
        value_part = parts[1].strip()

        if "->" in value_part:
            original, new = value_part.split("->")
            return cls(
                scope_type=scope_type,
                limit=int(new.strip()),
                original_limit=int(original.strip()),
            )
        else:
            return cls(scope_type=scope_type, limit=int(value_part))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "scope_type": self.scope_type,
            "limit": self.limit,
            "original_limit": self.original_limit,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OverrideScope:
        """Create from dictionary."""
        return cls(
            scope_type=data["scope_type"],
            limit=data["limit"],
            original_limit=data.get("original_limit"),
        )


@dataclass
class Override:
    """Governance record for verdict overrides.

    Overrides are not thresholds - they are human decisions with accountability.
    Each override MUST have: who approved it, why, when, and when it expires.

    REVERSIBILITY GUARANTEES:
    - Can be revoked before use (cheap reversal)
    - Can be extended without full re-approval (same approver)
    - Revocation creates audit trail (who, when, why)
    """

    override_id: str
    approved_by: str  # Human approver (email, username, etc.)
    approved_at: str  # ISO timestamp
    expires_at: str  # ISO timestamp
    reason: str
    scope: str  # What this override allows (validated via OverrideScope)
    conditions: list[str] = field(default_factory=list)  # Conditions that must be met
    used: bool = False
    used_at: str | None = None
    verdict_id: str | None = None  # Link to verdict that used this override
    revoked: bool = False  # Revocation flag
    revoked_by: str | None = None
    revoked_at: str | None = None
    revocation_reason: str | None = None
    parent_override_id: str | None = None  # Link to extended override

    def is_valid(self) -> bool:
        """Check if override is still valid (not expired, not used, not revoked).

        REVERSIBILITY: Revoked overrides are invalid even if not used/expired.
        """
        if self.used or self.revoked:
            return False
        try:
            expires_dt = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
            return datetime.now(UTC) < expires_dt
        except ValueError:
            return False

    def is_expired(self) -> bool:
        """Check if override has expired."""
        try:
            expires_dt = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
            return datetime.now(UTC) >= expires_dt
        except ValueError:
            return True

    def mark_used(self, verdict_id: str) -> None:
        """Mark override as used."""
        self.used = True
        self.used_at = datetime.now(UTC).isoformat()
        self.verdict_id = verdict_id

    def revoke(self, revoked_by: str, reason: str) -> None:
        """Revoke override before use.

        REVERSIBILITY: Enables cheap reversal before override is consumed.
        Cost: < 1 second (vs minutes for re-approval).

        Args:
            revoked_by: Who revoked this override
            reason: Why it was revoked
        """
        self.revoked = True
        self.revoked_by = revoked_by
        self.revoked_at = datetime.now(UTC).isoformat()
        self.revocation_reason = reason

    def parse_scope(self) -> OverrideScope:
        """Parse scope string into structured format.

        REVERSIBILITY: Validates scope before use to prevent silent failures.
        """
        return OverrideScope.from_string(self.scope)

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
            "revoked": self.revoked,
            "revoked_by": self.revoked_by,
            "revoked_at": self.revoked_at,
            "revocation_reason": self.revocation_reason,
            "parent_override_id": self.parent_override_id,
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
            revoked=data.get("revoked", False),
            revoked_by=data.get("revoked_by"),
            revoked_at=data.get("revoked_at"),
            revocation_reason=data.get("revocation_reason"),
            parent_override_id=data.get("parent_override_id"),
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
        now = datetime.now(UTC)
        expires = now + timedelta(hours=duration_hours)
        return cls(
            override_id=f"override-highs-{int(now.timestamp())}",
            approved_by=approved_by,
            approved_at=now.isoformat(),
            expires_at=expires.isoformat(),
            reason=reason,
            scope=f"max_highs: {max_highs_override}",
            conditions=[f"Must resolve within {duration_hours} hours"],
        )

    @classmethod
    def extend_existing(
        cls,
        existing: Override,
        additional_hours: int,
        extended_by: str,
        reason: str,
    ) -> Override:
        """Extend an existing override without full re-approval.

        REVERSIBILITY: Enables cheap extension (< 1 second vs minutes for re-approval).

        Args:
            existing: Override to extend
            additional_hours: Hours to add to expiry
            extended_by: Who is extending (must be same approver for auto-approval)
            reason: Why extension is needed

        Returns:
            New override linked to original via parent_override_id
        """
        new_expires = datetime.fromisoformat(existing.expires_at.replace("Z", "+00:00")) + timedelta(
            hours=additional_hours
        )
        return cls(
            override_id=f"{existing.override_id}-ext-{int(datetime.now(UTC).timestamp())}",
            approved_by=extended_by,
            approved_at=datetime.now(UTC).isoformat(),
            expires_at=new_expires.isoformat(),
            reason=f"Extension of {existing.override_id}: {reason}",
            scope=existing.scope,
            conditions=existing.conditions,
            parent_override_id=existing.override_id,
        )


@dataclass
class TemporalFinding:
    """Temporal tracking of a finding across multiple runs.

    Chronic issues (appearing repeatedly) should escalate in severity.
    This provides the evidence trail needed for that escalation.

    REVERSIBILITY GUARANTEES:
    - Can be de-escalated (mark false positive without losing history)
    - De-escalation creates audit trail (who, when, why)
    - Occurrence history preserved for forensics
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
    de_escalated: bool = False  # De-escalation flag
    de_escalated_by: str | None = None
    de_escalated_at: str | None = None
    de_escalation_reason: str | None = None

    def should_escalate(self, threshold_occurrences: int = 3) -> bool:
        """Determine if this finding should be escalated due to chronicity.

        REVERSIBILITY: De-escalated findings will not re-escalate.
        """
        if self.escalated or self.de_escalated:
            return False
        return self.occurrences >= threshold_occurrences

    def escalate(self, reason: str) -> None:
        """Mark finding as escalated."""
        self.escalated = True
        self.escalated_at = datetime.now(UTC).isoformat()
        self.escalation_reason = reason

    def de_escalate(self, by: str, reason: str) -> None:
        """Mark escalation as false positive.

        REVERSIBILITY: Preserves occurrence history but prevents future escalation.
        Cost: < 1 second (vs deleting entire record).

        Args:
            by: Who is de-escalating (human identifier)
            reason: Why this escalation was incorrect

        Example reasons:
        - "Fingerprint collision across microservices"
        - "Test findings in dev/staging, not production issue"
        - "Issue resolved, occurrences are historical"
        """
        self.escalated = False
        self.de_escalated = True
        self.de_escalated_by = by
        self.de_escalated_at = datetime.now(UTC).isoformat()
        self.de_escalation_reason = reason

    def record_occurrence(self, run_id: str, severity: str) -> None:
        """Record a new occurrence of this finding."""
        self.last_seen = datetime.now(UTC).isoformat()
        self.occurrences += 1
        if run_id not in self.runs_with_finding:
            self.runs_with_finding.append(run_id)
        self.severity_history.append((datetime.now(UTC).isoformat(), severity))

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
            "de_escalated": self.de_escalated,
            "de_escalated_by": self.de_escalated_by,
            "de_escalated_at": self.de_escalated_at,
            "de_escalation_reason": self.de_escalation_reason,
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
            de_escalated=data.get("de_escalated", False),
            de_escalated_by=data.get("de_escalated_by"),
            de_escalated_at=data.get("de_escalated_at"),
            de_escalation_reason=data.get("de_escalation_reason"),
        )


@dataclass
class EngineHealth:
    """Health check record for an engine.

    Silence is NOT health. Engines must actively report their status.
    Missing engines should degrade the verdict, not improve it.

    REVERSIBILITY GUARANTEES:
    - Transient failures (timeouts) can be retried (reduces reversal cost)
    - Retry history preserved in audit trail
    - Auto-retry reduces reversal cost from 10+ min (full CI/CD) to ~30sec
    """

    engine_id: str
    expected: bool  # Was this engine expected to run?
    ran: bool  # Did this engine actually run?
    succeeded: bool  # Did the engine complete successfully?
    timestamp: str  # ISO timestamp
    findings_reported: int = 0
    error_message: str | None = None
    execution_time_ms: float | None = None
    retry_count: int = 0  # Number of retries attempted
    max_retries: int = 3  # Maximum retries for transient failures
    is_transient_failure: bool = False  # Is this a retryable failure?

    def is_healthy(self) -> bool:
        """Determine if engine is healthy."""
        if not self.expected:
            return True  # Not expected, so absence is OK
        if not self.ran:
            return False  # Expected but didn't run
        return self.succeeded  # Ran, so check if it succeeded

    def should_retry(self) -> bool:
        """Determine if this failure should be retried.

        REVERSIBILITY: Auto-retry reduces cost of reversal from full CI/CD re-run.

        Returns True if:
        - Engine didn't run OR failed
        - Error indicates transient issue (timeout, network, resource)
        - Retry count below maximum
        """
        if self.ran and self.succeeded:
            return False  # Healthy, no retry needed

        if self.retry_count >= self.max_retries:
            return False  # Max retries exceeded

        # Check if error is transient
        if self.error_message:
            error_lower = self.error_message.lower()
            transient_indicators = [
                "timeout",
                "timed out",
                "network",
                "connection refused",
                "connection reset",
                "temporarily unavailable",
                "resource exhausted",
                "rate limit",
            ]
            self.is_transient_failure = any(indicator in error_lower for indicator in transient_indicators)
            return self.is_transient_failure

        return False

    def record_retry(self) -> None:
        """Record a retry attempt.

        REVERSIBILITY: Tracks retry history for audit trail.
        """
        self.retry_count += 1

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
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "is_transient_failure": self.is_transient_failure,
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
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
            is_transient_failure=data.get("is_transient_failure", False),
        )


@dataclass
class CategoryWeightConfig:
    """Configuration for category weights with governance.

    Weights are not constants - they encode organizational values
    and must be reviewed periodically.

    REVERSIBILITY GUARANTEES:
    - Version increments on every weight change
    - Verdicts link to weight version for point-in-time reconciliation
    - Can revert to previous version (weights stored in history)
    """

    weights: dict[Category, float] = field(default_factory=dict)
    config_version: str = "1.0.0"
    last_reviewed: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    review_frequency_days: int = 90  # Require review every 90 days
    reviewed_by: str | None = None
    review_notes: str | None = None

    def is_review_overdue(self) -> bool:
        """Check if weight configuration needs review."""
        try:
            last_review_dt = datetime.fromisoformat(self.last_reviewed.replace("Z", "+00:00"))
            next_review = last_review_dt + timedelta(days=self.review_frequency_days)
            return datetime.now(UTC) >= next_review
        except ValueError:
            return True  # If we can't parse, assume review is needed

    def get_weight(self, category: Category) -> float:
        """Get weight for a category."""
        return self.weights.get(category, 1.0)

    def update_weights(self, new_weights: dict[Category, float], reviewed_by: str, notes: str) -> None:
        """Update weights and record review.

        REVERSIBILITY: Increments version to enable verdict reconciliation.
        """
        self.weights = new_weights
        self.last_reviewed = datetime.now(UTC).isoformat()
        self.reviewed_by = reviewed_by
        self.review_notes = notes
        # Increment version (e.g., "1.0.0" -> "1.1.0")
        self._increment_version()

    def _increment_version(self) -> None:
        """Increment minor version on weight change."""
        try:
            parts = self.config_version.split(".")
            if len(parts) == 3:
                major, minor, patch = parts
                self.config_version = f"{major}.{int(minor) + 1}.{patch}"
            else:
                # Fallback: append timestamp if version format unexpected
                self.config_version = f"{self.config_version}.{int(datetime.now(UTC).timestamp())}"
        except (ValueError, IndexError):
            # Fallback: use timestamp
            self.config_version = f"1.0.{int(datetime.now(UTC).timestamp())}"

    def get_weights_snapshot(self) -> dict[str, float]:
        """Get current weights as snapshot (for verdict metadata).

        REVERSIBILITY: Verdicts store this snapshot to enable accurate
        point-in-time reconciliation even if weights change.
        """
        return {cat.value: weight for cat, weight in self.weights.items()}

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
            last_reviewed=data.get("last_reviewed", datetime.now(UTC).isoformat()),
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
