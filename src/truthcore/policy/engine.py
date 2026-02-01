"""Policy execution engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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
