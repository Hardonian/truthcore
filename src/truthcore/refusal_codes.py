"""Refusal reason codes for insufficient evidence scenarios.

Standardized codes for refusal cases to ensure stable, machine-readable
reasons across jobforge->runner->truthcore flows.
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class RefusalCode(Enum):
    """Standardized refusal reason codes.

    Format: DOMAIN_SUBCATEGORY_DETAIL
    - DOMAIN: High-level category (evidence, policy, system, validation)
    - SUBCATEGORY: Specific area within domain
    - DETAIL: Specific reason
    """

    # Evidence Domain - Missing or insufficient evidence
    EVIDENCE_MISSING_REQUIRED = "EVIDENCE_MISSING_REQUIRED"
    EVIDENCE_MISSING_INPUTS = "EVIDENCE_MISSING_INPUTS"
    EVIDENCE_MISSING_DEPENDENCIES = "EVIDENCE_MISSING_DEPENDENCIES"
    EVIDENCE_INSUFFICIENT_QUANTITY = "EVIDENCE_INSUFFICIENT_QUANTITY"
    EVIDENCE_INSUFFICIENT_QUALITY = "EVIDENCE_INSUFFICIENT_QUALITY"
    EVIDENCE_STALE = "EVIDENCE_STALE"
    EVIDENCE_CONFLICTING = "EVIDENCE_CONFLICTING"
    EVIDENCE_UNVERIFIABLE = "EVIDENCE_UNVERIFIABLE"

    # Policy Domain - Policy violations or constraints
    POLICY_VIOLATION_SECURITY = "POLICY_VIOLATION_SECURITY"
    POLICY_VIOLATION_PRIVACY = "POLICY_VIOLATION_PRIVACY"
    POLICY_VIOLATION_COMPLIANCE = "POLICY_VIOLATION_COMPLIANCE"
    POLICY_CONSTRAINT_UNMET = "POLICY_CONSTRAINT_UNMET"
    POLICY_OVERRIDE_REQUIRED = "POLICY_OVERRIDE_REQUIRED"

    # System Domain - System or infrastructure issues
    SYSTEM_ENGINE_UNAVAILABLE = "SYSTEM_ENGINE_UNAVAILABLE"
    SYSTEM_ENGINE_TIMEOUT = "SYSTEM_ENGINE_TIMEOUT"
    SYSTEM_ENGINE_FAILED = "SYSTEM_ENGINE_FAILED"
    SYSTEM_RESOURCE_EXHAUSTED = "SYSTEM_RESOURCE_EXHAUSTED"
    SYSTEM_DEPENDENCY_FAILURE = "SYSTEM_DEPENDENCY_FAILURE"
    SYSTEM_TIMEOUT = "SYSTEM_TIMEOUT"

    # Validation Domain - Validation or verification failures
    VALIDATION_SCHEMA_MISMATCH = "VALIDATION_SCHEMA_MISMATCH"
    VALIDATION_SIGNATURE_INVALID = "VALIDATION_SIGNATURE_INVALID"
    VALIDATION_HASH_MISMATCH = "VALIDATION_HASH_MISMATCH"
    VALIDATION_CHAIN_BROKEN = "VALIDATION_CHAIN_BROKEN"
    VALIDATION_INVARIANT_VIOLATED = "VALIDATION_INVARIANT_VIOLATED"

    # Processing Domain - Processing failures
    PROCESSING_INCOMPLETE = "PROCESSING_INCOMPLETE"
    PROCESSING_ERROR = "PROCESSING_ERROR"
    PROCESSING_SKIPPED = "PROCESSING_SKIPPED"


class RefusalReason:
    """Structured refusal reason with code and human-readable message.

    Ensures consistent, machine-readable refusal reasons across all flows.
    """

    def __init__(
        self,
        code: RefusalCode,
        message: str,
        details: dict[str, Any] | None = None,
        remediation: str | None = None,
    ):
        self.code = code
        self.message = message
        self.details = details or {}
        self.remediation = remediation

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "code": self.code.value,
            "message": self.message,
            "details": self.details,
        }
        if self.remediation:
            result["remediation"] = self.remediation
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RefusalReason:
        """Create from dictionary."""
        return cls(
            code=RefusalCode(data["code"]),
            message=data["message"],
            details=data.get("details", {}),
            remediation=data.get("remediation"),
        )

    def __str__(self) -> str:
        """String representation."""
        return f"[{self.code.value}] {self.message}"

    def __repr__(self) -> str:
        """Detailed representation."""
        return f"RefusalReason(code={self.code.value}, message={self.message!r})"


class RefusalCodes:
    """Convenience methods for creating common refusal reasons."""

    @staticmethod
    def missing_required_evidence(missing: list[str]) -> RefusalReason:
        """Evidence required for the operation is missing."""
        return RefusalReason(
            code=RefusalCode.EVIDENCE_MISSING_REQUIRED,
            message=f"Required evidence missing: {', '.join(missing)}",
            details={"missing_evidence": missing},
            remediation="Provide the required evidence items and retry",
        )

    @staticmethod
    def missing_inputs(input_paths: list[str]) -> RefusalReason:
        """Input files/directories not found or inaccessible."""
        return RefusalReason(
            code=RefusalCode.EVIDENCE_MISSING_INPUTS,
            message=f"Input paths not found: {', '.join(input_paths)}",
            details={"missing_inputs": input_paths},
            remediation="Ensure input paths exist and are accessible",
        )

    @staticmethod
    def insufficient_evidence_quantity(
        required: int, actual: int, evidence_type: str
    ) -> RefusalReason:
        """Not enough evidence items provided."""
        return RefusalReason(
            code=RefusalCode.EVIDENCE_INSUFFICIENT_QUANTITY,
            message=f"Insufficient {evidence_type} evidence: {actual} < {required}",
            details={"required": required, "actual": actual, "evidence_type": evidence_type},
            remediation=f"Provide at least {required} evidence items of type {evidence_type}",
        )

    @staticmethod
    def stale_evidence(evidence_ids: list[str], max_age_seconds: int) -> RefusalReason:
        """Evidence is too old to be considered valid."""
        return RefusalReason(
            code=RefusalCode.EVIDENCE_STALE,
            message=f"Evidence stale (older than {max_age_seconds}s): {', '.join(evidence_ids[:3])}",
            details={"stale_evidence_ids": evidence_ids, "max_age_seconds": max_age_seconds},
            remediation="Refresh the evidence by re-running the source operation",
        )

    @staticmethod
    def conflicting_evidence(conflicts: list[dict[str, str]]) -> RefusalReason:
        """Evidence items contradict each other."""
        return RefusalReason(
            code=RefusalCode.EVIDENCE_CONFLICTING,
            message=f"Conflicting evidence detected: {len(conflicts)} conflicts",
            details={"conflicts": conflicts},
            remediation="Review conflicting evidence and resolve contradictions",
        )

    @staticmethod
    def engine_unavailable(engine_id: str, reason: str) -> RefusalReason:
        """Required verification engine unavailable."""
        return RefusalReason(
            code=RefusalCode.SYSTEM_ENGINE_UNAVAILABLE,
            message=f"Engine '{engine_id}' unavailable: {reason}",
            details={"engine_id": engine_id, "reason": reason},
            remediation="Check engine health and configuration",
        )

    @staticmethod
    def engine_timeout(engine_id: str, timeout_seconds: int) -> RefusalReason:
        """Engine execution timed out."""
        return RefusalReason(
            code=RefusalCode.SYSTEM_ENGINE_TIMEOUT,
            message=f"Engine '{engine_id}' timed out after {timeout_seconds}s",
            details={"engine_id": engine_id, "timeout_seconds": timeout_seconds},
            remediation="Increase timeout or investigate engine performance",
        )

    @staticmethod
    def engine_failed(engine_id: str, error: str) -> RefusalReason:
        """Engine execution failed with error."""
        return RefusalReason(
            code=RefusalCode.SYSTEM_ENGINE_FAILED,
            message=f"Engine '{engine_id}' failed: {error}",
            details={"engine_id": engine_id, "error": error},
            remediation="Check engine logs and error details",
        )

    @staticmethod
    def policy_violation_security(policy_id: str, violation: str) -> RefusalReason:
        """Security policy violation detected."""
        return RefusalReason(
            code=RefusalCode.POLICY_VIOLATION_SECURITY,
            message=f"Security policy violation: {violation}",
            details={"policy_id": policy_id, "violation": violation},
            remediation="Address security issues or request policy override",
        )

    @staticmethod
    def validation_hash_mismatch(
        evidence_id: str, expected_hash: str, actual_hash: str
    ) -> RefusalReason:
        """Evidence hash verification failed."""
        return RefusalReason(
            code=RefusalCode.VALIDATION_HASH_MISMATCH,
            message=f"Hash mismatch for evidence '{evidence_id[:16]}...'",
            details={
                "evidence_id": evidence_id,
                "expected_hash": expected_hash,
                "actual_hash": actual_hash,
            },
            remediation="Evidence may be corrupted - regenerate from source",
        )

    @staticmethod
    def validation_signature_invalid(evidence_id: str, reason: str) -> RefusalReason:
        """Evidence signature verification failed."""
        return RefusalReason(
            code=RefusalCode.VALIDATION_SIGNATURE_INVALID,
            message=f"Invalid signature for evidence '{evidence_id[:16]}...': {reason}",
            details={"evidence_id": evidence_id, "reason": reason},
            remediation="Verify signing keys and evidence integrity",
        )

    @staticmethod
    def invariant_violated(invariant_id: str, details: str) -> RefusalReason:
        """System invariant violated."""
        return RefusalReason(
            code=RefusalCode.VALIDATION_INVARIANT_VIOLATED,
            message=f"Invariant '{invariant_id}' violated: {details}",
            details={"invariant_id": invariant_id, "violation_details": details},
            remediation="This indicates a system bug - contact support",
        )


# Common refusal code groupings for filtering
evidence_codes = {
    RefusalCode.EVIDENCE_MISSING_REQUIRED,
    RefusalCode.EVIDENCE_MISSING_INPUTS,
    RefusalCode.EVIDENCE_MISSING_DEPENDENCIES,
    RefusalCode.EVIDENCE_INSUFFICIENT_QUANTITY,
    RefusalCode.EVIDENCE_INSUFFICIENT_QUALITY,
    RefusalCode.EVIDENCE_STALE,
    RefusalCode.EVIDENCE_CONFLICTING,
    RefusalCode.EVIDENCE_UNVERIFIABLE,
}

system_codes = {
    RefusalCode.SYSTEM_ENGINE_UNAVAILABLE,
    RefusalCode.SYSTEM_ENGINE_TIMEOUT,
    RefusalCode.SYSTEM_ENGINE_FAILED,
    RefusalCode.SYSTEM_RESOURCE_EXHAUSTED,
    RefusalCode.SYSTEM_DEPENDENCY_FAILURE,
    RefusalCode.SYSTEM_TIMEOUT,
}

validation_codes = {
    RefusalCode.VALIDATION_SCHEMA_MISMATCH,
    RefusalCode.VALIDATION_SIGNATURE_INVALID,
    RefusalCode.VALIDATION_HASH_MISMATCH,
    RefusalCode.VALIDATION_CHAIN_BROKEN,
    RefusalCode.VALIDATION_INVARIANT_VIOLATED,
}

policy_codes = {
    RefusalCode.POLICY_VIOLATION_SECURITY,
    RefusalCode.POLICY_VIOLATION_PRIVACY,
    RefusalCode.POLICY_VIOLATION_COMPLIANCE,
    RefusalCode.POLICY_CONSTRAINT_UNMET,
    RefusalCode.POLICY_OVERRIDE_REQUIRED,
}
