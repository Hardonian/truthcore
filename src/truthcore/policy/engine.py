"""Policy execution engine."""

from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from truthcore.evidence import EvidencePacket, RuleEvaluation
from truthcore.findings import Finding, FindingReport
from truthcore.policy.models import PolicyPack, PolicyRule
from truthcore.policy.scanners import (
    ArtifactScanner,
    ConfigScanner,
    PIIScanner,
    ScanContext,
    SecretScanner,
)
from truthcore.security import SecurityLimits, check_path_safety


@dataclass
class PolicyResult:
    """Result of a policy scan."""

    pack_name: str
    pack_version: str
    findings: list[Finding] = field(default_factory=list)
    rules_evaluated: int = 0
    rules_triggered: int = 0
    scan_duration_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "pack_name": self.pack_name,
            "pack_version": self.pack_version,
            "findings_count": len(self.findings),
            "findings": [f.to_dict() for f in self.findings],
            "rules_evaluated": self.rules_evaluated,
            "rules_triggered": self.rules_triggered,
            "scan_duration_ms": self.scan_duration_ms,
            "metadata": dict(sorted(self.metadata.items())),
        }

    def has_blocking(self) -> bool:
        """Check if any findings are blocking."""
        from truthcore.findings import Severity as FindingSeverity
        return any(
            f.severity == FindingSeverity.BLOCKER for f in self.findings
        )


class PolicyEngine:
    """Main policy execution engine."""

    def __init__(
        self,
        input_dir: Path,
        output_dir: Path,
        limits: SecurityLimits | None = None,
    ) -> None:
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.limits = limits or SecurityLimits()
        self.context = ScanContext(
            input_dir=input_dir,
            limits=self.limits,
        )

    def run_pack(
        self,
        pack: PolicyPack,
        config: dict[str, Any] | None = None,
    ) -> PolicyResult:
        """Run a policy pack against input directory.

        Args:
            pack: Policy pack to run
            config: Optional configuration overrides

        Returns:
            PolicyResult with findings
        """
        import time

        start_time = time.time()
        result = PolicyResult(
            pack_name=pack.name,
            pack_version=pack.version,
        )

        # Validate input directory is safe
        try:
            check_path_safety(self.input_dir)
        except Exception as e:
            result.metadata["error"] = f"Invalid input directory: {e}"
            return result

        # Run each enabled rule
        for rule in pack.get_enabled_rules():
            result.rules_evaluated += 1
            findings = self._run_rule(rule)
            if findings:
                result.rules_triggered += 1
                result.findings.extend(findings)

        result.scan_duration_ms = int((time.time() - start_time) * 1000)

        return result

    def _run_rule(self, rule: PolicyRule) -> list[Finding]:
        """Run a single rule."""
        # Select scanner based on rule target and category
        scanner = self._get_scanner(rule)
        if scanner is None:
            return []

        return scanner.scan(rule)

    def _get_scanner(self, rule: PolicyRule):
        """Get appropriate scanner for rule."""
        category = rule.category.lower()
        target = rule.target

        if category in ("security", "secrets"):
            return SecretScanner(self.context)
        elif category in ("privacy", "pii"):
            return PIIScanner(self.context)
        elif category in ("config", "configuration"):
            return ConfigScanner(self.context)
        elif category in ("artifact", "hygiene"):
            return ArtifactScanner(self.context)

        # Default based on target
        if target == "files":
            return SecretScanner(self.context)
        elif target == "logs":
            return PIIScanner(self.context)
        elif target == "json_fields":
            return ConfigScanner(self.context)
        elif target == "findings":
            return ArtifactScanner(self.context)

        return SecretScanner(self.context)

    def run_pack_with_evidence(
        self,
        pack: PolicyPack,
        config: dict[str, Any] | None = None,
    ) -> tuple[PolicyResult, EvidencePacket]:
        """Run a policy pack and generate evidence packet.

        Returns:
            Tuple of (PolicyResult, EvidencePacket)
        """
        import hashlib
        import time

        start_time = time.time()
        result = PolicyResult(
            pack_name=pack.name,
            pack_version=pack.version,
        )

        # Validate input directory is safe
        try:
            check_path_safety(self.input_dir)
        except Exception as e:
            result.metadata["error"] = f"Invalid input directory: {e}"
            # Create minimal evidence packet for error case
            input_hash = hashlib.sha256(str(self.input_dir).encode()).hexdigest()
            input_summary = {"error": str(e)}
            rule_evaluations = []
            # Compute policy pack hash inline to avoid circular import
            pack_content = str(sorted(pack.to_dict().items()))
            policy_pack_hash = hashlib.sha256(pack_content.encode("utf-8")).hexdigest()[:16]

            evidence = EvidencePacket(
                evaluation_id=str(uuid.uuid4()),
                timestamp=datetime.now(UTC).isoformat(),
                version="1.0.0",
                policy_pack_name=pack.name,
                policy_pack_version=pack.version,
                policy_pack_hash=policy_pack_hash,
                input_hash=input_hash,
                input_summary=input_summary,
                rules_evaluated=0,
                rules_triggered=0,
                rule_evaluations=rule_evaluations,
                decision="deny",
                decision_reason="Input validation failed",
                blocking_findings=0,
                execution_metadata={"error": str(e)},
            )
            return result, evidence

        # Compute input hash and summary
        input_hash = self._compute_input_hash()
        input_summary = self._compute_input_summary()

        # Run each enabled rule and collect evaluations
        rule_evaluations = []
        for rule in pack.get_enabled_rules():
            rule_eval = self._run_rule_with_evaluation(rule)
            rule_evaluations.append(rule_eval)
            if rule_eval.triggered:
                result.rules_triggered += 1
                result.findings.extend(rule_eval.findings)
            result.rules_evaluated += 1

        result.scan_duration_ms = int((time.time() - start_time) * 1000)

        # Determine decision
        decision, decision_reason = self._determine_decision(result)

        # Compute policy pack hash inline to avoid circular import
        pack_content = str(sorted(pack.to_dict().items()))
        policy_pack_hash = hashlib.sha256(pack_content.encode("utf-8")).hexdigest()[:16]

        # Count blocking findings
        blocking_findings = sum(
            len(r.findings) for r in rule_evaluations
            if r.triggered and any(f.severity.value == "BLOCKER" for f in r.findings)
        )

        # Create evidence packet
        evidence = EvidencePacket(
            evaluation_id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC).isoformat(),
            version="1.0.0",
            policy_pack_name=pack.name,
            policy_pack_version=pack.version,
            policy_pack_hash=policy_pack_hash,
            input_hash=input_hash,
            input_summary=input_summary,
            rules_evaluated=result.rules_evaluated,
            rules_triggered=result.rules_triggered,
            rule_evaluations=rule_evaluations,
            decision=decision,
            decision_reason=decision_reason,
            blocking_findings=blocking_findings,
            execution_metadata={
                "scan_duration_ms": result.scan_duration_ms,
                "rules_evaluated": result.rules_evaluated,
                "rules_triggered": result.rules_triggered,
            },
        )

        return result, evidence

    def _run_rule_with_evaluation(self, rule: PolicyRule) -> RuleEvaluation:
        """Run a single rule and return detailed evaluation."""
        findings = self._run_rule(rule)

        # Check if rule was triggered
        triggered = len(findings) > 0

        # Check threshold
        threshold_met = True
        if rule.threshold:
            if rule.threshold.count is not None:
                threshold_met = len(findings) >= rule.threshold.count
            if rule.threshold.distinct is not None:
                distinct_values = len(set(str(f.target) for f in findings))
                threshold_met = threshold_met and distinct_values >= rule.threshold.distinct
            triggered = triggered and threshold_met

        # Check suppressions
        suppressed = False
        suppressed_reason = None
        if triggered:
            for finding in findings:
                if rule.is_suppressed(finding.target):
                    suppressed = True
                    suppressed_reason = "Finding suppressed by rule configuration"
                    break

        # Generate alternatives not triggered
        alternatives_not_triggered = self._explain_alternatives(rule, findings)

        return RuleEvaluation(
            rule_id=rule.id,
            rule_description=rule.description,
            triggered=triggered and not suppressed,
            matches_found=len(findings),
            threshold_met=threshold_met,
            suppressed=suppressed,
            suppressed_reason=suppressed_reason,
            findings=findings,
            alternatives_not_triggered=alternatives_not_triggered,
        )

    def _explain_alternatives(self, rule: PolicyRule, findings: list[Finding]) -> list[str]:
        """Explain why alternative conditions did not trigger."""
        reasons = []

        if not findings:
            reasons.append("No matches found for any rule patterns")

        if rule.threshold:
            if rule.threshold.count is not None and len(findings) < rule.threshold.count:
                reasons.append(f"Match count ({len(findings)}) below threshold ({rule.threshold.count})")
            if rule.threshold.distinct is not None:
                distinct_values = len(set(str(f.target) for f in findings))
                if distinct_values < rule.threshold.distinct:
                    reasons.append(f"Distinct values ({distinct_values}) below threshold ({rule.threshold.distinct})")

        if rule.matchers:
            matched_any = any(
                any(matcher.matches(f.target) for matcher in rule.matchers)
                for f in findings
            )
            if not matched_any:
                reasons.append("No findings matched the rule's pattern matchers")

        return reasons

    def _compute_input_hash(self) -> str:
        """Compute hash of input directory for integrity."""
        import hashlib

        # Simple hash of directory path and file count for now
        # In production, this could hash file contents
        dir_str = str(self.input_dir)
        file_count = sum(1 for _ in self.input_dir.rglob("*") if _.is_file())
        content = f"{dir_str}:{file_count}"
        return hashlib.sha256(content.encode()).hexdigest()

    def _compute_input_summary(self) -> dict[str, Any]:
        """Compute summary of input without sensitive data."""
        file_count = sum(1 for _ in self.input_dir.rglob("*") if _.is_file())
        dir_count = sum(1 for _ in self.input_dir.rglob("*") if _.is_dir())

        # Get file extensions
        extensions = {}
        for file_path in self.input_dir.rglob("*"):
            if file_path.is_file():
                ext = file_path.suffix.lower()
                extensions[ext] = extensions.get(ext, 0) + 1

        return {
            "total_files": file_count,
            "total_directories": dir_count,
            "file_extensions": dict(sorted(extensions.items())),
        }

    def _determine_decision(self, result: PolicyResult) -> tuple[str, str]:
        """Determine overall decision from results."""
        if result.has_blocking():
            return "deny", "Blocking findings detected"
        elif result.findings:
            return "conditional", "Non-blocking findings require review"
        else:
            return "allow", "All checks passed"

    def write_outputs(
        self,
        result: PolicyResult,
        base_name: str = "policy",
    ) -> dict[str, Path]:
        """Write all policy output formats.

        Returns:
            Dictionary mapping format to path
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)
        paths = {}

        # JSON output
        json_path = self.output_dir / f"{base_name}_findings.json"
        report = FindingReport(
            findings=result.findings,
            tool="truthcore-policy",
            tool_version=result.pack_version,
            metadata={
                "pack_name": result.pack_name,
                "rules_evaluated": result.rules_evaluated,
                "rules_triggered": result.rules_triggered,
                "scan_duration_ms": result.scan_duration_ms,
            },
        )
        report.write_json(json_path)
        paths["json"] = json_path

        # Markdown output
        md_path = self.output_dir / f"{base_name}_findings.md"
        report.write_markdown(md_path)
        paths["markdown"] = md_path

        # CSV output
        csv_path = self.output_dir / f"{base_name}_summary.csv"
        report.write_csv(csv_path)
        paths["csv"] = csv_path

        return paths

    @staticmethod
    def explain_rule(rule: PolicyRule) -> str:
        """Generate human-readable explanation of a rule."""
        lines = [
            f"# Policy Rule: {rule.id}",
            "",
            f"**Description:** {rule.description}",
            f"**Severity:** {rule.severity.value}",
            f"**Category:** {rule.category}",
            f"**Target:** {rule.target}",
            "",
        ]

        if rule.matchers:
            lines.extend(["## Matchers", ""])
            for i, matcher in enumerate(rule.matchers, 1):
                lines.append(f"{i}. **{matcher.type}:** `{matcher.pattern}`")
                if matcher.flags:
                    lines.append(f"   Flags: {', '.join(matcher.flags)}")
            lines.append("")

        if rule.threshold:
            lines.extend(["## Threshold", ""])
            thresh = rule.threshold
            if thresh.count is not None:
                lines.append(f"- Minimum count: {thresh.count}")
            if thresh.rate is not None:
                lines.append(f"- Minimum rate: {thresh.rate * 100:.1f}%")
            if thresh.distinct is not None:
                lines.append(f"- Minimum distinct: {thresh.distinct}")
            lines.append("")

        if rule.suppressions:
            lines.extend(["## Suppressions", ""])
            for sup in rule.suppressions:
                lines.append(f"- Pattern: `{sup.pattern}`")
                lines.append(f"  Reason: {sup.reason}")
                if sup.expiry:
                    lines.append(f"  Expiry: {sup.expiry}")
                if sup.author:
                    lines.append(f"  Author: {sup.author}")
            lines.append("")

        if rule.suggestion:
            lines.extend(["## Suggestion", "", rule.suggestion, ""])

        if rule.metadata:
            lines.extend(["## Metadata", ""])
            for key, value in sorted(rule.metadata.items()):
                lines.append(f"- {key}: {value}")
            lines.append("")

        return "\n".join(lines)


class PolicyPackLoader:
    """Loader for built-in and custom policy packs."""

    BUILT_IN_PACKS = {
        "base": "src/truthcore/policy/packs/base.yaml",
        "security": "src/truthcore/policy/packs/security.yaml",
        "privacy": "src/truthcore/policy/packs/privacy.yaml",
        "logging": "src/truthcore/policy/packs/logging.yaml",
        "agent": "src/truthcore/policy/packs/agent.yaml",
    }

    @classmethod
    def load_pack(cls, name_or_path: str) -> PolicyPack:
        """Load a policy pack by name or path.

        Args:
            name_or_path: Built-in pack name or path to YAML file

        Returns:
            Loaded PolicyPack

        Raises:
            FileNotFoundError: If pack not found
            ValueError: If pack is invalid
        """
        # Check if built-in
        if name_or_path in cls.BUILT_IN_PACKS:
            # Try to find in package
            import importlib
            import importlib.util

            try:
                spec = importlib.util.find_spec("truthcore")
                if spec and spec.origin:
                    package_dir = Path(spec.origin).parent
                    pack_path = package_dir / "policy" / "packs" / f"{name_or_path}.yaml"
                    if pack_path.exists():
                        return PolicyPack.from_yaml(pack_path)
            except Exception:
                pass

            # Fallback to relative path
            pack_path = Path(cls.BUILT_IN_PACKS[name_or_path])
            if pack_path.exists():
                return PolicyPack.from_yaml(pack_path)

            raise FileNotFoundError(f"Built-in pack not found: {name_or_path}")

        # Try as path
        pack_path = Path(name_or_path)
        if not pack_path.exists():
            raise FileNotFoundError(f"Policy pack not found: {name_or_path}")

        return PolicyPack.from_yaml(pack_path)

    @classmethod
    def list_built_in(cls) -> list[str]:
        """List available built-in pack names."""
        return list(cls.BUILT_IN_PACKS.keys())
