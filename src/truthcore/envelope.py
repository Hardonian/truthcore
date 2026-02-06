"""Explainability envelope for TruthCore outputs.

Every TruthCore output MUST be wrapped in an explainability envelope that
provides:
- decision: the final verdict or outcome
- reasons: list of reasons mapped to rule IDs
- evidence_refs: references to evidence packets used
- uncertainty: explicit notes about what is unknown or ambiguous
- content_hash: blake2b hash of the envelope content for integrity

This prevents opaque verdicts and forces the system to show its work.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from truthcore.canonical import canonical_hash, canonical_json
from truthcore.determinism import stable_timestamp


@dataclass
class ReasonEntry:
    """A single reason contributing to a decision.

    Always maps to a specific rule ID for traceability.
    """

    rule_id: str
    description: str
    effect: str  # "ship", "no_ship", "degrade", "info"
    severity: str | None = None
    evidence_ref: str | None = None  # Hash or ID of supporting evidence

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "rule_id": self.rule_id,
            "description": self.description,
            "effect": self.effect,
            "severity": self.severity,
            "evidence_ref": self.evidence_ref,
        }


@dataclass
class UncertaintyNote:
    """Explicit documentation of uncertainty in the output.

    Prevents fake precision by requiring the system to declare
    what it does NOT know.
    """

    source: str  # What produced this uncertainty
    description: str  # What is uncertain
    impact: str  # How it affects the decision: "may_change_verdict", "informational", "needs_review"
    confidence_range: tuple[float, float] | None = None  # (low, high) confidence bounds

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result: dict[str, Any] = {
            "source": self.source,
            "description": self.description,
            "impact": self.impact,
        }
        if self.confidence_range is not None:
            result["confidence_range"] = list(self.confidence_range)
        return result


@dataclass
class ExplainabilityEnvelope:
    """Wraps any TruthCore output with full explainability.

    Fields:
        decision: The final outcome (e.g., "SHIP", "NO_SHIP", "PASS", "FAIL")
        reasons: List of reasons, each mapped to a rule ID
        evidence_refs: List of evidence packet hashes or IDs
        uncertainty: Explicit notes about unknowns
        timestamp: When the envelope was created
        truthcore_version: Version of TruthCore that produced this
        payload: The actual output data (verdict, finding report, etc.)
        content_hash: Blake2b hash of (decision + reasons + evidence_refs + payload)
    """

    decision: str
    reasons: list[ReasonEntry] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    uncertainty: list[UncertaintyNote] = field(default_factory=list)
    timestamp: str = field(default_factory=stable_timestamp)
    truthcore_version: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    content_hash: str = ""

    def __post_init__(self) -> None:
        """Compute content hash after initialization."""
        if not self.truthcore_version:
            from truthcore import __version__
            self.truthcore_version = __version__
        if not self.content_hash:
            self.content_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """Compute deterministic hash of envelope content."""
        hashable = {
            "decision": self.decision,
            "reasons": [r.to_dict() for r in self.reasons],
            "evidence_refs": sorted(self.evidence_refs),
            "payload": self.payload,
        }
        return canonical_hash(hashable)

    def add_reason(
        self,
        rule_id: str,
        description: str,
        effect: str,
        severity: str | None = None,
        evidence_ref: str | None = None,
    ) -> None:
        """Add a reason entry and update the hash."""
        self.reasons.append(ReasonEntry(
            rule_id=rule_id,
            description=description,
            effect=effect,
            severity=severity,
            evidence_ref=evidence_ref,
        ))
        self.content_hash = self._compute_hash()

    def add_uncertainty(
        self,
        source: str,
        description: str,
        impact: str,
        confidence_range: tuple[float, float] | None = None,
    ) -> None:
        """Add an uncertainty note."""
        self.uncertainty.append(UncertaintyNote(
            source=source,
            description=description,
            impact=impact,
            confidence_range=confidence_range,
        ))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary with stable ordering."""
        return {
            "envelope_version": "1.0",
            "decision": self.decision,
            "reasons": [r.to_dict() for r in self.reasons],
            "evidence_refs": sorted(self.evidence_refs),
            "uncertainty": [u.to_dict() for u in self.uncertainty],
            "timestamp": self.timestamp,
            "truthcore_version": self.truthcore_version,
            "content_hash": self.content_hash,
            "payload": self.payload,
        }

    def to_json(self) -> str:
        """Produce canonical JSON representation."""
        return canonical_json(self.to_dict())

    @classmethod
    def from_verdict_result(cls, result: Any) -> ExplainabilityEnvelope:
        """Create envelope from a VerdictResult.

        Maps verdict reasons to rule IDs and extracts evidence refs.
        """
        from truthcore import __version__

        decision = result.verdict.value if hasattr(result.verdict, "value") else str(result.verdict)

        reasons: list[ReasonEntry] = []

        # Map ship reasons
        for i, reason_text in enumerate(result.ship_reasons):
            reasons.append(ReasonEntry(
                rule_id=f"ship_reason_{i}",
                description=reason_text,
                effect="ship",
            ))

        # Map no-ship reasons
        for i, reason_text in enumerate(result.no_ship_reasons):
            reasons.append(ReasonEntry(
                rule_id=f"no_ship_reason_{i}",
                description=reason_text,
                effect="no_ship",
            ))

        # Map degradation reasons
        for i, reason_text in enumerate(result.degradation_reasons):
            reasons.append(ReasonEntry(
                rule_id=f"degradation_{i}",
                description=reason_text,
                effect="degrade",
            ))

        # Map findings as reasons with evidence refs
        evidence_refs: list[str] = []
        for finding in result.top_findings[:10]:
            ref = finding.finding_id
            evidence_refs.append(ref)
            reasons.append(ReasonEntry(
                rule_id=finding.rule_id or finding.finding_id,
                description=finding.message,
                effect="no_ship" if finding.severity.value in ("BLOCKER", "HIGH") else "info",
                severity=finding.severity.value,
                evidence_ref=ref,
            ))

        # Uncertainty notes
        uncertainty: list[UncertaintyNote] = []
        if result.engines_failed > 0:
            uncertainty.append(UncertaintyNote(
                source="engine_health",
                description=f"{result.engines_failed} engine(s) failed, results may be incomplete",
                impact="may_change_verdict",
            ))
        if result.engines_ran < result.engines_expected:
            uncertainty.append(UncertaintyNote(
                source="engine_coverage",
                description=f"Only {result.engines_ran}/{result.engines_expected} engines ran",
                impact="needs_review",
            ))

        envelope = cls(
            decision=decision,
            reasons=reasons,
            evidence_refs=evidence_refs,
            uncertainty=uncertainty,
            truthcore_version=__version__,
            payload=result.to_dict(),
        )

        return envelope
