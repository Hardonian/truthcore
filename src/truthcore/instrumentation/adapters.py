"""
Boundary adapters for attaching instrumentation to system boundaries.

Provides hooks for:
- Engine lifecycle (start/finish)
- Finding creation
- Verdict decisions
- Policy evaluation
- Cache operations
- Human overrides

All hooks are safe no-ops if instrumentation is disabled.
"""

from typing import Any

from truthcore.instrumentation.core import InstrumentationCore, content_hash


class BoundaryAdapter:
    """
    Attaches to system boundaries to capture events.

    Uses instrumentation core to emit events.
    Never modifies behavior, never throws exceptions.
    """

    def __init__(self, core: InstrumentationCore):
        self.core = core

    def on_engine_start(self, engine_name: str, inputs: dict[str, Any]) -> None:
        """
        Called when an engine begins execution.

        Args:
            engine_name: Name of the engine
            inputs: Input parameters
        """
        self.core.emit({
            "signal_type": "engine_lifecycle",
            "event": "engine_start",
            "engine": engine_name,
            "inputs_hash": content_hash(inputs),
        })

    def on_engine_finish(
        self,
        engine_name: str,
        outputs: dict[str, Any],
        duration_ms: float,
        success: bool = True,
    ) -> None:
        """
        Called when an engine completes execution.

        Args:
            engine_name: Name of the engine
            outputs: Output results
            duration_ms: Execution duration in milliseconds
            success: Whether execution succeeded
        """
        self.core.emit({
            "signal_type": "engine_lifecycle",
            "event": "engine_finish",
            "engine": engine_name,
            "outputs_hash": content_hash(outputs),
            "duration_ms": duration_ms,
            "success": success,
        })

    def on_finding_created(self, finding: Any) -> None:
        """
        Called when a Finding is created.

        Args:
            finding: Finding object (duck-typed)
        """
        self.core.emit({
            "signal_type": "assertion",
            "source": getattr(finding, "rule_id", "unknown"),
            "claim": getattr(finding, "message", ""),
            "severity": getattr(getattr(finding, "severity", None), "value", None),
            "confidence_hint": getattr(finding, "confidence", None),
            "context": {
                "file_path": getattr(finding, "file_path", None),
                "line_number": getattr(finding, "line_number", None),
            },
        })

    def on_verdict_decided(self, verdict: Any) -> None:
        """
        Called when a Verdict is computed.

        Args:
            verdict: VerdictResult object (duck-typed)
        """
        self.core.emit({
            "signal_type": "decision",
            "decision_type": "system",
            "actor": "verdict_aggregator",
            "action": getattr(getattr(verdict, "verdict", None), "value", None),
            "score": getattr(verdict, "value", None),
            "rationale": getattr(verdict, "summary", None),
        })

    def on_policy_evaluated(
        self,
        policy_id: str,
        result: bool,
        enforcement_mode: str = "observe",
    ) -> None:
        """
        Called when a policy is evaluated.

        Args:
            policy_id: Policy identifier
            result: Evaluation result (pass/fail)
            enforcement_mode: observe/warn/block
        """
        self.core.emit({
            "signal_type": "policy_reference",
            "policy_id": policy_id,
            "evaluation_result": "PASS" if result else "FAIL",
            "enforcement_mode": enforcement_mode,
        })

    def on_human_override(
        self,
        original_decision: str,
        override_decision: str,
        actor: str,
        rationale: str,
        scope: str | None = None,
        authority: str | None = None,
    ) -> None:
        """
        Called when a human overrides a system decision.

        Args:
            original_decision: Original system decision
            override_decision: Human's override decision
            actor: User/entity making override
            rationale: Explanation for override
            scope: What the override applies to
            authority: Authorization level
        """
        self.core.emit({
            "signal_type": "override",
            "override_type": "human",
            "actor": actor,
            "original_decision": original_decision,
            "override_decision": override_decision,
            "rationale": rationale,
            "scope": scope,
            "authority": authority,
        })

    def on_cache_decision(self, key: str, hit: bool, reused: bool = False) -> None:
        """
        Called when a cache decision is made.

        Args:
            key: Cache key
            hit: Whether cache hit occurred
            reused: Whether cached result was reused
        """
        self.core.emit({
            "signal_type": "decision",
            "decision_type": "cache",
            "action": "hit" if hit else "miss",
            "key_hash": content_hash(key),
            "reused": reused,
        })

    def on_evidence_input(
        self,
        evidence_type: str,
        source: str,
        content_hash_value: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Called when evidence is input to reasoning.

        Args:
            evidence_type: Type of evidence (file_read, api_response, etc.)
            source: Source of evidence
            content_hash_value: Content hash
            metadata: Additional metadata
        """
        self.core.emit({
            "signal_type": "evidence",
            "evidence_type": evidence_type,
            "source": source,
            "content_hash": content_hash_value,
            **(metadata or {}),
        })

    def on_belief_change(
        self,
        subject: str,
        old_value: Any,
        new_value: Any,
        trigger: str,
    ) -> None:
        """
        Called when a belief changes.

        Args:
            subject: What the belief is about
            old_value: Previous belief value
            new_value: New belief value
            trigger: What triggered the change
        """
        self.core.emit({
            "signal_type": "belief_change",
            "subject": subject,
            "old_value": old_value,
            "new_value": new_value,
            "trigger": trigger,
        })

    def on_economic_signal(
        self,
        metric: str,
        amount: float,
        unit: str,
        applies_to: str | None = None,
        cost_estimate: float | None = None,
    ) -> None:
        """
        Called when an economic signal is recorded.

        Args:
            metric: What is being measured (token_usage, time_spent, etc.)
            amount: Numeric value
            unit: Units (tokens, seconds, USD, etc.)
            applies_to: What this applies to
            cost_estimate: Estimated cost in currency
        """
        self.core.emit({
            "signal_type": "economic",
            "metric": metric,
            "amount": amount,
            "unit": unit,
            "applies_to": applies_to,
            "cost_estimate": cost_estimate,
        })

    def on_semantic_usage(
        self,
        term: str,
        definition_source: str,
        actual_usage: str,
        context: str | None = None,
    ) -> None:
        """
        Called when semantic terms are used.

        Args:
            term: Term being used (e.g., "deployment_ready")
            definition_source: Where term is defined
            actual_usage: How it's actually being used
            context: Usage context
        """
        self.core.emit({
            "signal_type": "semantic_usage",
            "term": term,
            "definition_source": definition_source,
            "actual_usage": actual_usage,
            "usage_context": context,
        })
