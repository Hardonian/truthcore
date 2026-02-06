"""Policy decision models for deterministic policy reasoning.

This module extends TruthCore's policy engine with:
- Policy effect types (allow/deny/conditional)
- Priority-based conflict resolution
- Decision traceability
- Deterministic override rules
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from truthcore.severity import Severity


class PolicyEffect(Enum):
    """Policy decision effect types.
    
    Deterministic effects for policy rules:
    - ALLOW: Explicitly permit the action/target
    - DENY: Explicitly forbid the action/target  
    - CONDITIONAL: Permit with conditions attached
    """
    
    ALLOW = "allow"
    DENY = "deny"
    CONDITIONAL = "conditional"


class PolicyPriority(Enum):
    """Priority levels for policy conflict resolution.
    
    Higher priority rules override lower priority rules.
    Within same priority, DENY typically wins over ALLOW.
    """
    
    CRITICAL = 0     # System-critical policies (e.g., security)
    HIGH = 1         # Important policies (e.g., compliance)
    MEDIUM = 2       # Standard policies
    LOW = 3          # Advisory policies
    DEFAULT = 4      # Fallback/default policies


@dataclass
class PolicyCondition:
    """Condition for CONDITIONAL policy effects.
    
    Attributes:
        field: Field to check (e.g., "time", "user_role")
        operator: Comparison operator (eq, ne, gt, lt, in, not_in)
        value: Value to compare against
    """
    
    field: str
    operator: str  # eq, ne, gt, lt, gte, lte, in, not_in, contains
    value: Any
    
    def evaluate(self, context: dict[str, Any]) -> bool:
        """Evaluate condition against context.
        
        Args:
            context: Dictionary of context values
            
        Returns:
            True if condition is satisfied
        """
        actual_value = context.get(self.field)
        
        if self.operator == "eq":
            return actual_value == self.value
        elif self.operator == "ne":
            return actual_value != self.value
        elif self.operator == "gt":
            return actual_value is not None and actual_value > self.value
        elif self.operator == "lt":
            return actual_value is not None and actual_value < self.value
        elif self.operator == "gte":
            return actual_value is not None and actual_value >= self.value
        elif self.operator == "lte":
            return actual_value is not None and actual_value <= self.value
        elif self.operator == "in":
            return actual_value in self.value if self.value is not None else False
        elif self.operator == "not_in":
            return actual_value not in self.value if self.value is not None else True
        elif self.operator == "contains":
            return self.value in actual_value if actual_value is not None else False
        
        return False
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "field": self.field,
            "operator": self.operator,
            "value": self.value,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PolicyCondition:
        """Create from dictionary."""
        return cls(
            field=data["field"],
            operator=data["operator"],
            value=data["value"],
        )


@dataclass
class PolicyOverride:
    """Override rule for policy decisions.
    
    Allows specific policies to override others based on
    conditions and approval.
    
    Attributes:
        policy_id: ID of policy that can be overridden
        condition: Optional condition for override
        approved_by: Who approved this override
        expires_at: When override expires (ISO format)
        reason: Why override is in place
    """
    
    policy_id: str
    condition: PolicyCondition | None = None
    approved_by: str | None = None
    expires_at: str | None = None
    reason: str | None = None
    
    def is_active(self, context: dict[str, Any]) -> bool:
        """Check if override is currently active.

        Args:
            context: Evaluation context

        Returns:
            True if override applies
        """
        from truthcore.determinism import stable_now

        # Check expiry
        if self.expires_at:
            try:
                expiry = datetime.fromisoformat(self.expires_at)
                if stable_now() > expiry:
                    return False
            except ValueError:
                return False
        
        # Check condition
        if self.condition:
            return self.condition.evaluate(context)
        
        return True
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "policy_id": self.policy_id,
            "approved_by": self.approved_by,
            "expires_at": self.expires_at,
            "reason": self.reason,
        }
        if self.condition:
            result["condition"] = self.condition.to_dict()
        return result
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PolicyOverride:
        """Create from dictionary."""
        condition = None
        if "condition" in data:
            condition = PolicyCondition.from_dict(data["condition"])
        return cls(
            policy_id=data["policy_id"],
            condition=condition,
            approved_by=data.get("approved_by"),
            expires_at=data.get("expires_at"),
            reason=data.get("reason"),
        )


@dataclass
class PolicyDecision:
    """Single policy decision in the evaluation chain.
    
    Records one step in the policy evaluation process for
    full traceability.
    
    Attributes:
        policy_id: ID of policy being evaluated
        rule_id: Specific rule ID
        effect: ALLOW/DENY/CONDITIONAL
        priority: Policy priority level
        matched: Whether the policy matched
        conditions_met: Whether conditions were satisfied
        overridden_by: ID of policy that overrode this one
    """
    
    policy_id: str
    rule_id: str
    effect: PolicyEffect
    priority: PolicyPriority
    matched: bool = False
    conditions_met: bool = True
    overridden_by: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_effective(self) -> bool:
        """Whether this decision affects the final outcome.
        
        Returns:
            True if policy matched, conditions met, and not overridden
        """
        return self.matched and self.conditions_met and self.overridden_by is None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "policy_id": self.policy_id,
            "rule_id": self.rule_id,
            "effect": self.effect.value,
            "priority": self.priority.name,
            "matched": self.matched,
            "conditions_met": self.conditions_met,
            "overridden_by": self.overridden_by,
            "is_effective": self.is_effective,
            "metadata": dict(sorted(self.metadata.items())),
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PolicyDecision:
        """Create from dictionary."""
        return cls(
            policy_id=data["policy_id"],
            rule_id=data["rule_id"],
            effect=PolicyEffect(data["effect"]),
            priority=PolicyPriority[data["priority"]],
            matched=data.get("matched", False),
            conditions_met=data.get("conditions_met", True),
            overridden_by=data.get("overridden_by"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class PolicyDecisionTrace:
    """Complete trace of policy evaluation.
    
    Records the entire chain of policy decisions that led
    to the final outcome, ensuring full explainability.
    
    Attributes:
        decisions: List of policy decisions in evaluation order
        final_effect: Final computed effect
        final_policy_id: ID of policy that determined outcome
        conflicts_detected: List of policy conflicts encountered
        overrides_applied: List of overrides that were active
    """
    
    decisions: list[PolicyDecision] = field(default_factory=list)
    final_effect: PolicyEffect | None = None
    final_policy_id: str | None = None
    conflicts_detected: list[dict[str, Any]] = field(default_factory=list)
    overrides_applied: list[PolicyOverride] = field(default_factory=list)
    
    def add_decision(self, decision: PolicyDecision) -> None:
        """Add a decision to the trace."""
        self.decisions.append(decision)
    
    def record_conflict(
        self,
        policy_a: str,
        policy_b: str,
        resolution: str,
        winner: str,
    ) -> None:
        """Record a policy conflict and its resolution."""
        self.conflicts_detected.append({
            "policy_a": policy_a,
            "policy_b": policy_b,
            "resolution": resolution,
            "winner": winner,
        })
    
    def get_effective_decisions(self) -> list[PolicyDecision]:
        """Get only decisions that affected the outcome."""
        return [d for d in self.decisions if d.is_effective]
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "decisions": [d.to_dict() for d in self.decisions],
            "final_effect": self.final_effect.value if self.final_effect else None,
            "final_policy_id": self.final_policy_id,
            "conflicts_detected": self.conflicts_detected,
            "overrides_applied": [o.to_dict() for o in self.overrides_applied],
            "effective_decisions_count": len(self.get_effective_decisions()),
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PolicyDecisionTrace:
        """Create from dictionary."""
        trace = cls(
            decisions=[PolicyDecision.from_dict(d) for d in data.get("decisions", [])],
            final_effect=PolicyEffect(data["final_effect"]) if data.get("final_effect") else None,
            final_policy_id=data.get("final_policy_id"),
            conflicts_detected=data.get("conflicts_detected", []),
            overrides_applied=[PolicyOverride.from_dict(o) for o in data.get("overrides_applied", [])],
        )
        return trace


@dataclass
class PolicyEvidencePacket:
    """Extended evidence packet with policy reasoning.
    
    Attaches policy references and decision trace to findings
    for full explainability.
    
    Attributes:
        finding_id: ID of the finding this packet relates to
        policy_id: ID of policy that triggered
        rule_id: Specific rule ID
        policy_effect: Effect type (allow/deny/conditional)
        decision_trace: Full trace of policy evaluation
        conditions: Conditions that were evaluated
        override_applied: Whether an override was active
        refusal_reason: If denied, the refusal reason
    """
    
    finding_id: str
    policy_id: str
    rule_id: str
    policy_effect: PolicyEffect
    decision_trace: PolicyDecisionTrace = field(default_factory=PolicyDecisionTrace)
    conditions: list[PolicyCondition] = field(default_factory=list)
    override_applied: PolicyOverride | None = None
    refusal_reason: str | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "finding_id": self.finding_id,
            "policy_id": self.policy_id,
            "rule_id": self.rule_id,
            "policy_effect": self.policy_effect.value,
            "decision_trace": self.decision_trace.to_dict(),
            "conditions": [c.to_dict() for c in self.conditions],
            "override_applied": self.override_applied.to_dict() if self.override_applied else None,
            "refusal_reason": self.refusal_reason,
        }
        return result
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PolicyEvidencePacket:
        """Create from dictionary."""
        override = None
        if data.get("override_applied"):
            override = PolicyOverride.from_dict(data["override_applied"])
        
        return cls(
            finding_id=data["finding_id"],
            policy_id=data["policy_id"],
            rule_id=data["rule_id"],
            policy_effect=PolicyEffect(data["policy_effect"]),
            decision_trace=PolicyDecisionTrace.from_dict(data.get("decision_trace", {})),
            conditions=[PolicyCondition.from_dict(c) for c in data.get("conditions", [])],
            override_applied=override,
            refusal_reason=data.get("refusal_reason"),
        )


class PolicyConflictResolver:
    """Deterministic resolver for policy conflicts.
    
    Implements priority-based conflict resolution with override support.
    All decisions are explainable via the decision trace.
    """
    
    @staticmethod
    def resolve(
        decisions: list[PolicyDecision],
        overrides: list[PolicyOverride] | None = None,
        context: dict[str, Any] | None = None,
    ) -> tuple[PolicyEffect, PolicyDecisionTrace]:
        """Resolve policy conflicts deterministically.
        
        Resolution order:
        1. Filter to only matched decisions
        2. Apply active overrides
        3. Sort by priority (highest first)
        4. Within same priority, DENY beats ALLOW
        5. Return highest priority effective decision
        
        Args:
            decisions: All policy decisions from evaluation
            overrides: Optional override rules
            context: Evaluation context for conditions
            
        Returns:
            Tuple of (final_effect, decision_trace)
        """
        trace = PolicyDecisionTrace()
        overrides = overrides or []
        context = context or {}
        
        # Record all decisions
        for decision in decisions:
            trace.add_decision(decision)
        
        # Filter to matched decisions
        matched = [d for d in decisions if d.matched]
        
        if not matched:
            # No policies matched - default allow
            trace.final_effect = PolicyEffect.ALLOW
            return PolicyEffect.ALLOW, trace
        
        # Check for active overrides
        active_overrides = []
        for override in overrides:
            if override.is_active(context):
                active_overrides.append(override)
                # Mark overridden policies
                for decision in matched:
                    if decision.policy_id == override.policy_id:
                        decision.overridden_by = "override_rule"
        
        trace.overrides_applied = active_overrides
        
        # Get effective decisions (matched, conditions met, not overridden)
        effective = [d for d in matched if d.is_effective]
        
        if not effective:
            # All policies overridden - default allow
            trace.final_effect = PolicyEffect.ALLOW
            return PolicyEffect.ALLOW, trace
        
        # Sort by priority (lower number = higher priority)
        # Then by effect: DENY before ALLOW before CONDITIONAL
        def sort_key(d: PolicyDecision) -> tuple:
            effect_order = {
                PolicyEffect.DENY: 0,
                PolicyEffect.CONDITIONAL: 1,
                PolicyEffect.ALLOW: 2,
            }
            return (d.priority.value, effect_order.get(d.effect, 3))
        
        effective.sort(key=sort_key)
        
        # Detect conflicts (multiple policies at same priority with different effects)
        if len(effective) > 1:
            first_priority = effective[0].priority
            first_effect = effective[0].effect
            for other in effective[1:]:
                if other.priority == first_priority and other.effect != first_effect:
                    trace.record_conflict(
                        policy_a=effective[0].policy_id,
                        policy_b=other.policy_id,
                        resolution=f"Priority {first_priority.name} conflict resolved: "
                                   f"{first_effect.value} wins over {other.effect.value}",
                        winner=effective[0].policy_id,
                    )
        
        # Winner is the first (highest priority, DENY beats ALLOW)
        winner = effective[0]
        trace.final_effect = winner.effect
        trace.final_policy_id = winner.policy_id
        
        return winner.effect, trace
