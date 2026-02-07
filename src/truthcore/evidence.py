"""Evidence packet generation and validation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from truthcore.findings import Finding


@dataclass
class RuleEvaluation:
    """Evaluation result for a single rule."""

    rule_id: str
    rule_description: str
    triggered: bool
    matches_found: int
    threshold_met: bool
    suppressed: bool
    suppressed_reason: str | None = None
    findings: list[Finding] = field(default_factory=list)
    alternatives_not_triggered: list[str] = field(default_factory=list)  # Explain why not

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "rule_id": self.rule_id,
            "rule_description": self.rule_description,
            "triggered": self.triggered,
            "matches_found": self.matches_found,
            "threshold_met": self.threshold_met,
            "suppressed": self.suppressed,
            "suppressed_reason": self.suppressed_reason,
            "findings_count": len(self.findings),
            "findings": [f.to_dict() for f in self.findings],
            "alternatives_not_triggered": self.alternatives_not_triggered,
        }


@dataclass
class EvidencePacket:
    """Auditable evidence packet for policy evaluation."""

    # Metadata
    evaluation_id: str
    timestamp: str
    version: str
    policy_pack_name: str
    policy_pack_version: str
    policy_pack_hash: str

    # Inputs
    input_hash: str
    input_summary: dict[str, Any]  # Summary of input without sensitive data

    # Evaluation results
    rules_evaluated: int
    rules_triggered: int
    rule_evaluations: list[RuleEvaluation]

    # Decision
    decision: str  # "allow", "deny", "conditional"
    decision_reason: str
    blocking_findings: int

    # Additional context
    execution_metadata: dict[str, Any] = field(default_factory=dict)



    def compute_content_hash(self) -> str:
        """Compute hash of the evidence content for integrity."""
        # Sort all nested structures for deterministic hashing
        content = self.to_dict()
        # Remove timestamp and evaluation_id for content hash
        content_for_hash = {
            k: v for k, v in content.items()
            if k not in ("evaluation_id", "timestamp")
        }
        content_str = json.dumps(content_for_hash, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(content_str.encode('utf-8')).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary with sorted keys."""
        return {
            "evaluation_id": self.evaluation_id,
            "timestamp": self.timestamp,
            "version": self.version,
            "policy_pack": {
                "name": self.policy_pack_name,
                "version": self.policy_pack_version,
                "hash": self.policy_pack_hash,
            },
            "input": {
                "hash": self.input_hash,
                "summary": dict(sorted(self.input_summary.items())),
            },
            "evaluation": {
                "rules_evaluated": self.rules_evaluated,
                "rules_triggered": self.rules_triggered,
                "rule_evaluations": [r.to_dict() for r in self.rule_evaluations],
            },
            "decision": {
                "outcome": self.decision,
                "reason": self.decision_reason,
                "blocking_findings": self.blocking_findings,
            },
            "execution_metadata": dict(sorted(self.execution_metadata.items())),
            "content_hash": self.compute_content_hash(),
        }

    def to_json(self, path: Path) -> None:
        """Write evidence packet to JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, sort_keys=True)

    def to_markdown_summary(self) -> str:
        """Generate human-readable markdown summary."""
        lines = [
            "# Evidence Packet Summary",
            "",
            f"**Evaluation ID:** {self.evaluation_id}",
            f"**Timestamp:** {self.timestamp}",
            f"**Decision:** {self.decision.upper()}",
            f"**Reason:** {self.decision_reason}",
            "",
            "## Policy Pack",
            "",
            f"- Name: {self.policy_pack_name}",
            f"- Version: {self.policy_pack_version}",
            f"- Hash: {self.policy_pack_hash[:8]}...",
            "",
            "## Evaluation Results",
            "",
            f"- Rules Evaluated: {self.rules_evaluated}",
            f"- Rules Triggered: {self.rules_triggered}",
            f"- Blocking Findings: {self.blocking_findings}",
            "",
        ]

        if self.rule_evaluations:
            lines.extend(["## Rule Evaluations", ""])

            for rule_eval in self.rule_evaluations:
                status = "✅ TRIGGERED" if rule_eval.triggered else "❌ Not Triggered"
                lines.extend([
                    f"### {rule_eval.rule_id}",
                    "",
                    f"**Description:** {rule_eval.rule_description}",
                    f"**Status:** {status}",
                    f"**Matches Found:** {rule_eval.matches_found}",
                    f"**Threshold Met:** {'Yes' if rule_eval.threshold_met else 'No'}",
                ])

                if rule_eval.suppressed:
                    lines.append(f"**Suppressed:** Yes ({rule_eval.suppressed_reason})")

                if rule_eval.findings:
                    lines.append(f"**Findings:** {len(rule_eval.findings)}")

                if rule_eval.alternatives_not_triggered:
                    lines.extend([
                        "**Why Not Triggered:**",
                        "",
                        *[f"- {reason}" for reason in rule_eval.alternatives_not_triggered],
                        "",
                    ])

                lines.append("")

        if self.execution_metadata:
            lines.extend(["## Execution Metadata", ""])
            for key, value in sorted(self.execution_metadata.items()):
                lines.append(f"- **{key}:** {value}")
            lines.append("")

        lines.extend([
            "## Integrity",
            "",
            f"**Content Hash:** {self.compute_content_hash()[:16]}...",
            "",
            "*This evidence packet ensures auditability and deterministic behavior.*",
        ])

        return "\n".join(lines)


    def to_markdown_file(self, path: Path) -> None:
        """Write markdown summary to file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(self.to_markdown_summary())
