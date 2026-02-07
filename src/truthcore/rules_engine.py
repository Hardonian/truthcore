"""Clean API surface for provable rules engine."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from truthcore.evidence import EvidencePacket
from truthcore.policy.engine import PolicyEngine, PolicyPackLoader
from truthcore.policy.models import PolicyPack


class RulesEngine:
    """Provable rules engine with evidence packets."""

    def __init__(self, policy_pack: str | PolicyPack):
        """Initialize with a policy pack."""
        if isinstance(policy_pack, str):
            self.policy_pack = PolicyPackLoader.load_pack(policy_pack)
        else:
            self.policy_pack = policy_pack

    def evaluate(
        self,
        input_path: str | Path,
        policy_options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Evaluate input against policy and return decision with evidence.

        Args:
            input_path: Path to input directory or file
            policy_options: Optional policy configuration overrides

        Returns:
            Dictionary with:
            - decision: "allow", "deny", or "conditional"
            - evidence: EvidencePacket object
            - summary: Human-readable summary
        """
        input_path = Path(input_path)
        if not input_path.exists():
            raise ValueError(f"Input path does not exist: {input_path}")

        # Create temporary output directory for processing
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Run evaluation
            engine = PolicyEngine(input_path, temp_path)
            result, evidence = engine.run_pack_with_evidence(
                self.policy_pack,
                config=policy_options,
            )

            return {
                "decision": evidence.decision,
                "evidence": evidence,
                "summary": evidence.to_markdown_summary(),
                "findings_count": len(result.findings),
                "blocking_findings": evidence.blocking_findings,
            }


# Convenience function for direct use
def evaluate(
    input_path: str | Path,
    policy_pack: str | PolicyPack,
    policy_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate input against policy pack.

    Args:
        input_path: Path to input directory or file
        policy_pack: Policy pack name/path or PolicyPack object
        policy_options: Optional policy configuration

    Returns:
        Evaluation result with decision and evidence
    """
    engine = RulesEngine(policy_pack)
    return engine.evaluate(input_path, policy_options)
