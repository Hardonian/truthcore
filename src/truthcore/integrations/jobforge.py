"""JobForge integration hooks for explicit policy validation.

This module provides integration points for JobForge to request
policy validation explicitly, with full support for the policy
reasoning extensions (effect types, priority, conflict resolution,
and decision traceability).

Usage:
    from truthcore.integrations.jobforge import JobForgePolicyValidator
    
    validator = JobForgePolicyValidator()
    result = validator.validate_for_jobforge(
        jobforge_output=job_data,
        correlation_id="corr-123",
        explicit_policies=["security", "compliance"]
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from truthcore.findings import Finding, FindingReport, Location
from truthcore.policy.decisions import (
    PolicyConflictResolver,
    PolicyDecision,
    PolicyDecisionTrace,
    PolicyEffect,
    PolicyEvidencePacket,
    PolicyOverride,
    PolicyPriority,
)
from truthcore.policy.engine import PolicyEngine, PolicyPackLoader
from truthcore.policy.models import PolicyPack, PolicyRule
from truthcore.refusal_codes import RefusalCode, RefusalReason


@dataclass
class JobForgePolicyResult:
    """Result of JobForge policy validation.
    
    Attributes:
        passed: Whether validation passed
        findings: List of findings from policy evaluation
        decision_trace: Full trace of policy decisions
        refusal_reasons: List of refusal reasons if validation failed
        correlation_id: Correlation ID for provenance
        metadata: Additional metadata
    """
    
    passed: bool
    findings: list[Finding] = field(default_factory=list)
    decision_trace: PolicyDecisionTrace = field(default_factory=PolicyDecisionTrace)
    refusal_reasons: list[RefusalReason] = field(default_factory=list)
    correlation_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "passed": self.passed,
            "findings_count": len(self.findings),
            "findings": [f.to_dict() for f in self.findings],
            "decision_trace": self.decision_trace.to_dict(),
            "refusal_reasons": [r.to_dict() for r in self.refusal_reasons],
            "correlation_id": self.correlation_id,
            "metadata": dict(sorted(self.metadata.items())),
        }


class JobForgePolicyValidator:
    """Explicit policy validator for JobForge integration.
    
    This validator provides JobForge with the ability to request
    policy validation explicitly, receiving full decision traces
    and evidence packets for explainability.
    
    Key features:
    - Explicit policy pack selection
    - Priority-based conflict resolution
    - Full decision trace capture
    - Deterministic override support
    - Refusal reason generation
    """
    
    def __init__(self, policy_packs_dir: Path | None = None) -> None:
        """Initialize the validator.
        
        Args:
            policy_packs_dir: Optional directory containing policy packs
        """
        self.policy_packs_dir = policy_packs_dir
        self._cache: dict[str, PolicyPack] = {}
    
    def validate_for_jobforge(
        self,
        jobforge_output: dict[str, Any],
        correlation_id: str | None = None,
        explicit_policies: list[str] | None = None,
        overrides: list[PolicyOverride] | None = None,
        context: dict[str, Any] | None = None,
    ) -> JobForgePolicyResult:
        """Validate JobForge output against policies.
        
        Args:
            jobforge_output: Output from JobForge to validate
            correlation_id: Optional correlation ID for provenance
            explicit_policies: List of policy pack names to apply
            overrides: Optional list of policy overrides
            context: Optional evaluation context
            
        Returns:
            JobForgePolicyResult with findings and decision trace
        """
        explicit_policies = explicit_policies or ["base", "security"]
        overrides = overrides or []
        context = context or {}
        
        result = JobForgePolicyResult(
            passed=True,
            correlation_id=correlation_id,
        )
        
        # Load and evaluate each policy pack
        all_decisions: list[PolicyDecision] = []
        
        for pack_name in explicit_policies:
            try:
                pack = self._load_pack(pack_name)
                pack_decisions = self._evaluate_pack(
                    pack=pack,
                    jobforge_output=jobforge_output,
                    context=context,
                )
                all_decisions.extend(pack_decisions)
            except Exception as e:
                # Record engine failure as refusal
                result.refusal_reasons.append(
                    RefusalReason(
                        code=RefusalCode.SYSTEM_ENGINE_FAILED,
                        message=f"Policy pack '{pack_name}' failed to load: {e}",
                        details={"pack_name": pack_name, "error": str(e)},
                    )
                )
                result.passed = False
        
        # Resolve conflicts and determine final outcome
        if all_decisions:
            final_effect, trace = PolicyConflictResolver.resolve(
                decisions=all_decisions,
                overrides=overrides,
                context=context,
            )
            result.decision_trace = trace
            
            # Convert effective decisions to findings
            for decision in trace.get_effective_decisions():
                if decision.effect == PolicyEffect.DENY:
                    finding = self._decision_to_finding(
                        decision=decision,
                        correlation_id=correlation_id,
                        trace=trace,
                    )
                    result.findings.append(finding)
                    result.passed = False
                    
                    # Generate refusal reason
                    result.refusal_reasons.append(
                        RefusalReason(
                            code=RefusalCode.POLICY_VIOLATION_SECURITY,
                            message=f"Policy '{decision.policy_id}' denied: {decision.rule_id}",
                            details={
                                "policy_id": decision.policy_id,
                                "rule_id": decision.rule_id,
                                "decision_trace": decision.to_dict(),
                            },
                        )
                    )
        
        # Record metadata
        result.metadata = {
            "policies_evaluated": explicit_policies,
            "decisions_count": len(all_decisions),
            "effective_decisions_count": len(result.decision_trace.get_effective_decisions()),
            "overrides_count": len(overrides),
        }
        
        return result
    
    def _load_pack(self, name: str) -> PolicyPack:
        """Load a policy pack with caching."""
        if name not in self._cache:
            self._cache[name] = PolicyPackLoader.load_pack(name)
        return self._cache[name]
    
    def _evaluate_pack(
        self,
        pack: PolicyPack,
        jobforge_output: dict[str, Any],
        context: dict[str, Any],
    ) -> list[PolicyDecision]:
        """Evaluate a policy pack against JobForge output.
        
        Args:
            pack: Policy pack to evaluate
            jobforge_output: JobForge output to check
            context: Evaluation context
            
        Returns:
            List of policy decisions
        """
        decisions: list[PolicyDecision] = []
        
        for rule in pack.get_enabled_rules():
            decision = self._evaluate_rule(
                rule=rule,
                pack_name=pack.name,
                jobforge_output=jobforge_output,
                context=context,
            )
            decisions.append(decision)
        
        return decisions
    
    def _evaluate_rule(
        self,
        rule: PolicyRule,
        pack_name: str,
        jobforge_output: dict[str, Any],
        context: dict[str, Any],
    ) -> PolicyDecision:
        """Evaluate a single rule against JobForge output.
        
        Args:
            rule: Policy rule to evaluate
            pack_name: Name of the policy pack
            jobforge_output: JobForge output to check
            context: Evaluation context
            
        Returns:
            PolicyDecision with evaluation result
        """
        # Check if rule matches JobForge output
        matched = self._rule_matches(rule, jobforge_output)
        
        # Check conditions if conditional
        conditions_met = True
        if rule.effect == PolicyEffect.CONDITIONAL and matched:
            # For now, assume conditions are in rule metadata
            conditions = rule.metadata.get("conditions", [])
            conditions_met = self._evaluate_conditions(conditions, context)
        
        return PolicyDecision(
            policy_id=pack_name,
            rule_id=rule.id,
            effect=rule.effect,
            priority=rule.priority,
            matched=matched,
            conditions_met=conditions_met,
            metadata={
                "rule_description": rule.description,
                "rule_severity": rule.severity.value,
                "rule_category": rule.category,
            },
        )
    
    def _rule_matches(
        self,
        rule: PolicyRule,
        jobforge_output: dict[str, Any],
    ) -> bool:
        """Check if a rule matches the JobForge output.
        
        This is a simplified implementation that checks:
        - If rule target matches JobForge output structure
        - If rule matchers match values in output
        
        Args:
            rule: Policy rule
            jobforge_output: JobForge output
            
        Returns:
            True if rule matches
        """
        # For now, simple keyword matching in output
        output_str = str(jobforge_output).lower()
        
        # Check matchers if present
        if rule.matchers:
            for matcher in rule.matchers:
                if matcher.matches(output_str):
                    return True
            return False
        
        # Default: check if rule category appears in output
        return rule.category.lower() in output_str
    
    def _evaluate_conditions(
        self,
        conditions: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> bool:
        """Evaluate a list of conditions.
        
        Args:
            conditions: List of condition dictionaries
            context: Evaluation context
            
        Returns:
            True if all conditions are met
        """
        from truthcore.policy.decisions import PolicyCondition
        
        for cond_data in conditions:
            condition = PolicyCondition.from_dict(cond_data)
            if not condition.evaluate(context):
                return False
        return True
    
    def _decision_to_finding(
        self,
        decision: PolicyDecision,
        correlation_id: str | None,
        trace: PolicyDecisionTrace,
    ) -> Finding:
        """Convert a policy decision to a Finding.
        
        Args:
            decision: Policy decision
            correlation_id: Correlation ID for provenance
            trace: Full decision trace
            
        Returns:
            Finding with policy evidence packet
        """
        # Create evidence packet
        evidence = PolicyEvidencePacket(
            finding_id=f"policy-{decision.rule_id}-{hash(decision.policy_id) & 0xFFFF:04x}",
            policy_id=decision.policy_id,
            rule_id=decision.rule_id,
            policy_effect=decision.effect,
            decision_trace=trace,
            refusal_reason=f"Policy violation: {decision.rule_id}" if decision.effect == PolicyEffect.DENY else None,
        )
        
        # Create finding
        finding = Finding(
            rule_id=decision.rule_id,
            severity=self._priority_to_severity(decision.priority),
            target=f"jobforge://{decision.policy_id}",
            location=Location(
                path=f"policy://{decision.policy_id}/{decision.rule_id}",
            ),
            message=f"[{decision.effect.value.upper()}] Policy '{decision.policy_id}': {decision.metadata.get('rule_description', 'No description')}",
            policy_evidence=evidence,
            metadata={
                "correlation_id": correlation_id,
                "policy_priority": decision.priority.name,
                "policy_effect": decision.effect.value,
                "pipeline_stages_completed": ["jobforge", "policy_validation", "truthcore"],
            },
        )
        
        return finding
    
    def _priority_to_severity(self, priority: PolicyPriority) -> Any:
        """Convert policy priority to finding severity.
        
        Args:
            priority: Policy priority
            
        Returns:
            Severity level
        """
        from truthcore.severity import Severity
        
        mapping = {
            PolicyPriority.CRITICAL: Severity.BLOCKER,
            PolicyPriority.HIGH: Severity.HIGH,
            PolicyPriority.MEDIUM: Severity.MEDIUM,
            PolicyPriority.LOW: Severity.LOW,
            PolicyPriority.DEFAULT: Severity.INFO,
        }
        return mapping.get(priority, Severity.MEDIUM)


def create_jobforge_policy_result(
    passed: bool,
    reason: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """Create a standardized JobForge policy result.
    
    This is a convenience function for creating simple results
    without using the full validator.
    
    Args:
        passed: Whether validation passed
        reason: Optional reason string
        correlation_id: Optional correlation ID
        
    Returns:
        Dictionary with standardized result format
    """
    return {
        "passed": passed,
        "reason": reason,
        "correlation_id": correlation_id,
        "timestamp": None,  # Will be filled in by caller
        "policy_version": "2.0.0",
    }
