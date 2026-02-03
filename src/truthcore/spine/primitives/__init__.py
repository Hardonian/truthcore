"""Core primitives for TruthCore Spine.

These are the foundational data structures for the truth spine:
- Assertion: Immutable claims backed by evidence
- Evidence: Content-addressed data inputs
- Belief: Versioned assertions with confidence
- MeaningVersion: Semantic versioning for concepts
- Decision: Recorded choices with provenance
- Override: Scoped human interventions
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class ClaimType(Enum):
    """Type of claim being asserted."""
    OBSERVED = "observed"      # Direct observation
    DERIVED = "derived"        # Computed from other assertions
    INFERRED = "inferred"      # Inferred from patterns


class EvidenceType(Enum):
    """Type of evidence."""
    RAW = "raw"                # Direct input (file, API response)
    DERIVED = "derived"        # Computed from other evidence
    HUMAN_INPUT = "human_input"  # Explicit human assertion
    EXTERNAL = "external"      # Third-party system


class DecisionType(Enum):
    """Type of decision."""
    SYSTEM = "system"          # Automated decision
    HUMAN_OVERRIDE = "human_override"  # Human intervention
    POLICY_ENFORCED = "policy_enforced"  # Hard policy constraint


@dataclass(frozen=True)
class Evidence:
    """Raw or derived data that supports assertions.

    Evidence is the foundation - assertions are built upon it.
    Both are immutable and content-addressed.
    """
    evidence_id: str            # blake2b hash of content
    evidence_type: EvidenceType
    content_hash: str           # Hash of actual data
    source: str                 # Where it came from
    timestamp: str              # ISO 8601 UTC
    validity_seconds: int | None = None  # How long valid (None = forever)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # Convert datetime to ISO string if needed
        object.__setattr__(self, 'timestamp', _ensure_iso_timestamp(self.timestamp))

    def is_stale(self, now: datetime | None = None) -> bool:
        """Check if evidence has expired."""
        if self.validity_seconds is None:
            return False
        now = now or datetime.now(UTC)
        created = datetime.fromisoformat(self.timestamp.replace('Z', '+00:00'))
        return (now - created).total_seconds() > self.validity_seconds

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary with canonical ordering."""
        return {
            "evidence_id": self.evidence_id,
            "evidence_type": self.evidence_type.value,
            "content_hash": self.content_hash,
            "source": self.source,
            "timestamp": self.timestamp,
            "validity_seconds": self.validity_seconds,
            "metadata": dict(sorted(self.metadata.items())),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Evidence:
        """Create from dictionary."""
        return cls(
            evidence_id=data["evidence_id"],
            evidence_type=EvidenceType(data["evidence_type"]),
            content_hash=data["content_hash"],
            source=data["source"],
            timestamp=data["timestamp"],
            validity_seconds=data.get("validity_seconds"),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def compute_hash(cls, content: bytes | str) -> str:
        """Compute blake2b hash of content."""
        if isinstance(content, str):
            content = content.encode('utf-8')
        return hashlib.blake2b(content, digest_size=32).hexdigest()


@dataclass(frozen=True)
class Assertion:
    """A claim backed by evidence. Immutable and content-addressed.

    Assertions do not have confidence - they are statements of what
    the system observed or calculated. Confidence belongs to Beliefs.
    """
    assertion_id: str           # blake2b hash of claim + evidence_ids
    claim: str                  # Human-readable claim text
    evidence_ids: tuple[str, ...]  # References to Evidence objects (tuple for immutability)
    claim_type: ClaimType
    source: str                 # Origin (engine, human, external)
    timestamp: str              # ISO 8601 UTC
    context: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # Convert datetime to ISO string if needed
        object.__setattr__(self, 'timestamp', _ensure_iso_timestamp(self.timestamp))
        # Ensure evidence_ids is a tuple
        if not isinstance(self.evidence_ids, tuple):
            object.__setattr__(self, 'evidence_ids', tuple(self.evidence_ids))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary with canonical ordering."""
        return {
            "assertion_id": self.assertion_id,
            "claim": self.claim,
            "evidence_ids": list(self.evidence_ids),
            "claim_type": self.claim_type.value,
            "source": self.source,
            "timestamp": self.timestamp,
            "context": dict(sorted(self.context.items())),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Assertion:
        """Create from dictionary."""
        return cls(
            assertion_id=data["assertion_id"],
            claim=data["claim"],
            evidence_ids=tuple(data.get("evidence_ids", [])),
            claim_type=ClaimType(data.get("claim_type", "observed")),
            source=data["source"],
            timestamp=data["timestamp"],
            context=data.get("context", {}),
        )

    @classmethod
    def compute_id(cls, claim: str, evidence_ids: list[str]) -> str:
        """Compute content-addressed ID from claim and evidence."""
        content = json.dumps({
            "claim": claim,
            "evidence_ids": sorted(evidence_ids),
        }, sort_keys=True)
        return hashlib.blake2b(content.encode('utf-8'), digest_size=32).hexdigest()


@dataclass(frozen=True)
class Belief:
    """A versioned belief in an assertion with confidence scoring.

    Beliefs are NOT mutable - each update creates a new Belief
    with incremented version number. Previous beliefs retained
    for history queries.
    """
    belief_id: str              # Unique identifier (assertion_id + version)
    assertion_id: str           # What we believe
    version: int                # Monotonically increasing
    confidence: float           # [0.0, 1.0]
    confidence_method: str      # How computed (rule-based, decay, etc.)
    formed_at: str              # ISO 8601
    superseded_at: str | None   # ISO 8601 (when newer belief formed)
    upstream_belief_ids: tuple[str, ...] = field(default_factory=tuple)
    rationale: str = ""         # Why this confidence level
    decay_rate: float = 0.0     # Daily decay rate

    def __post_init__(self):
        # Convert datetime to ISO string if needed
        object.__setattr__(self, 'formed_at', _ensure_iso_timestamp(self.formed_at))
        if self.superseded_at:
            object.__setattr__(self, 'superseded_at', _ensure_iso_timestamp(self.superseded_at))
        # Ensure upstream_belief_ids is a tuple
        if not isinstance(self.upstream_belief_ids, tuple):
            object.__setattr__(self, 'upstream_belief_ids', tuple(self.upstream_belief_ids))
        # Clamp confidence to [0, 1]
        confidence = max(0.0, min(1.0, self.confidence))
        object.__setattr__(self, 'confidence', confidence)

    def current_confidence(self, now: datetime | None = None) -> float:
        """Compute confidence with time-based decay."""
        if self.decay_rate <= 0 or self.superseded_at:
            return self.confidence

        now = now or datetime.now(UTC)
        formed = datetime.fromisoformat(self.formed_at.replace('Z', '+00:00'))
        days_elapsed = (now - formed).total_seconds() / 86400

        # Apply exponential decay
        import math
        return self.confidence * math.exp(-self.decay_rate * days_elapsed)

    def is_superseded(self) -> bool:
        """Check if a newer version exists."""
        return self.superseded_at is not None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "belief_id": self.belief_id,
            "assertion_id": self.assertion_id,
            "version": self.version,
            "confidence": self.confidence,
            "confidence_method": self.confidence_method,
            "formed_at": self.formed_at,
            "upstream_belief_ids": list(self.upstream_belief_ids),
            "rationale": self.rationale,
            "decay_rate": self.decay_rate,
        }
        if self.superseded_at:
            result["superseded_at"] = self.superseded_at
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Belief:
        """Create from dictionary."""
        return cls(
            belief_id=data["belief_id"],
            assertion_id=data["assertion_id"],
            version=data["version"],
            confidence=data["confidence"],
            confidence_method=data.get("confidence_method", "unknown"),
            formed_at=data["formed_at"],
            superseded_at=data.get("superseded_at"),
            upstream_belief_ids=tuple(data.get("upstream_belief_ids", [])),
            rationale=data.get("rationale", ""),
            decay_rate=data.get("decay_rate", 0.0),
        )

    @classmethod
    def compute_id(cls, assertion_id: str, version: int) -> str:
        """Compute belief ID from assertion and version."""
        return f"{assertion_id}_v{version:03d}"


@dataclass(frozen=True)
class MeaningVersion:
    """Semantic versioning for the *meaning* of concepts.

    When "deployment ready" changes from "score >= 90" to
    "score >= 90 AND all reviews complete", this captures
    that semantic drift explicitly.
    """
    meaning_id: str             # Semantic identifier (e.g., "deployment.success")
    version: str                # SemVer (e.g., "2.1.0")
    definition: str             # Human-readable definition
    computation: str | None     # Formula or algorithm
    examples: list[dict[str, Any]] = field(default_factory=list)
    valid_from: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    valid_until: str | None = None

    def __post_init__(self):
        # Convert datetime to ISO string if needed
        object.__setattr__(self, 'valid_from', _ensure_iso_timestamp(self.valid_from))
        if self.valid_until:
            object.__setattr__(self, 'valid_until', _ensure_iso_timestamp(self.valid_until))

    def is_current(self, timestamp: str | datetime | None = None) -> bool:
        """Check if this meaning version is current at given time."""
        if self.valid_until is None:
            return True

        if timestamp is None:
            timestamp = datetime.now(UTC)
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))

        valid_until = datetime.fromisoformat(self.valid_until.replace('Z', '+00:00'))
        return timestamp <= valid_until

    def is_compatible_with(self, other: MeaningVersion) -> bool:
        """Check if two meanings are semantically compatible."""
        # Same meaning_id and major version = compatible
        if self.meaning_id != other.meaning_id:
            return False

        self_major = self.version.split('.')[0]
        other_major = other.version.split('.')[0]
        return self_major == other_major

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "meaning_id": self.meaning_id,
            "version": self.version,
            "definition": self.definition,
            "computation": self.computation,
            "examples": self.examples,
            "valid_from": self.valid_from,
        }
        if self.valid_until:
            result["valid_until"] = self.valid_until
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MeaningVersion:
        """Create from dictionary."""
        return cls(
            meaning_id=data["meaning_id"],
            version=data["version"],
            definition=data["definition"],
            computation=data.get("computation"),
            examples=data.get("examples", []),
            valid_from=data.get("valid_from", datetime.now(UTC).isoformat()),
            valid_until=data.get("valid_until"),
        )


@dataclass(frozen=True)
class Decision:
    """A recorded choice made by system or human.

    Decisions reference the beliefs that informed them.
    They do not require TruthCore's permission to be made.
    """
    decision_id: str            # Content hash
    decision_type: DecisionType
    action: str                 # What was decided
    belief_ids: tuple[str, ...] = field(default_factory=tuple)
    context: dict[str, Any] = field(default_factory=dict)
    actor: str = "system"
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def __post_init__(self):
        # Convert datetime to ISO string if needed
        object.__setattr__(self, 'timestamp', _ensure_iso_timestamp(self.timestamp))
        # Ensure belief_ids is a tuple
        if not isinstance(self.belief_ids, tuple):
            object.__setattr__(self, 'belief_ids', tuple(self.belief_ids))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "decision_id": self.decision_id,
            "decision_type": self.decision_type.value,
            "action": self.action,
            "belief_ids": list(self.belief_ids),
            "context": dict(sorted(self.context.items())),
            "actor": self.actor,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Decision:
        """Create from dictionary."""
        return cls(
            decision_id=data["decision_id"],
            decision_type=DecisionType(data.get("decision_type", "system")),
            action=data["action"],
            belief_ids=tuple(data.get("belief_ids", [])),
            context=data.get("context", {}),
            actor=data.get("actor", "system"),
            timestamp=data.get("timestamp", datetime.now(UTC).isoformat()),
        )

    @classmethod
    def compute_id(cls, action: str, belief_ids: list[str], timestamp: str) -> str:
        """Compute content-addressed ID."""
        content = json.dumps({
            "action": action,
            "belief_ids": sorted(belief_ids),
            "timestamp": timestamp,
        }, sort_keys=True)
        return hashlib.blake2b(content.encode('utf-8'), digest_size=32).hexdigest()


@dataclass(frozen=True)
class Override:
    """Human intervention that contradicts system recommendation.

    All overrides are scoped, authorized, and time-bounded.
    """
    override_id: str            # Unique identifier
    original_decision: str      # Decision being overridden
    override_decision: str      # New decision
    actor: str                  # Who authorized
    authority_scope: str        # What they can override
    rationale: str              # Why override
    expires_at: str             # ISO 8601 (REQUIRED - no permanent overrides)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def __post_init__(self):
        # Convert datetime to ISO string if needed
        object.__setattr__(self, 'created_at', _ensure_iso_timestamp(self.created_at))
        object.__setattr__(self, 'expires_at', _ensure_iso_timestamp(self.expires_at))

    def is_expired(self, now: datetime | None = None) -> bool:
        """Check if override has expired."""
        now = now or datetime.now(UTC)
        expires = datetime.fromisoformat(self.expires_at.replace('Z', '+00:00'))
        return now > expires

    def time_remaining(self, now: datetime | None = None) -> float:
        """Get seconds remaining until expiry (negative if expired)."""
        now = now or datetime.now(UTC)
        expires = datetime.fromisoformat(self.expires_at.replace('Z', '+00:00'))
        return (expires - now).total_seconds()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "override_id": self.override_id,
            "original_decision": self.original_decision,
            "override_decision": self.override_decision,
            "actor": self.actor,
            "authority_scope": self.authority_scope,
            "rationale": self.rationale,
            "expires_at": self.expires_at,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Override:
        """Create from dictionary."""
        return cls(
            override_id=data["override_id"],
            original_decision=data["original_decision"],
            override_decision=data["override_decision"],
            actor=data["actor"],
            authority_scope=data["authority_scope"],
            rationale=data["rationale"],
            expires_at=data["expires_at"],
            created_at=data.get("created_at", datetime.now(UTC).isoformat()),
        )


# Helper functions

def _ensure_iso_timestamp(ts: str | datetime) -> str:
    """Ensure timestamp is ISO 8601 string."""
    if isinstance(ts, datetime):
        return ts.isoformat()
    return ts


def utc_now_iso() -> str:
    """Get current UTC time as ISO string."""
    return datetime.now(UTC).isoformat()
