"""Query surface for TruthCore Spine.

Implements the 7 MVP query types:
- Why Query: Belief provenance and lineage
- Evidence Query: Supporting/weakening evidence  
- History Query: Belief version timeline
- Meaning Query: Semantic version resolution
- Override Query: Human intervention tracking
- Dependencies Query: Assumption tracing
- Invalidation Query: Counter-evidence identification
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from truthcore.spine.primitives import Assertion, Belief, Evidence, MeaningVersion, Override
from truthcore.spine.graph import GraphStore
from truthcore.spine.belief import BeliefEngine


@dataclass
class WhyResult:
    """Result of a 'why' query."""
    assertion: Assertion
    current_belief: Belief | None
    confidence_explanation: str
    evidence_count: int
    upstream_dependencies: list[str]
    formation_rationale: str


@dataclass
class EvidenceResult:
    """Result of an evidence query."""
    assertion_id: str
    supporting_evidence: list[Evidence]
    weakening_evidence: list[Evidence]
    stale_evidence: list[Evidence]
    total_weight: float


@dataclass
class HistoryResult:
    """Result of a history query."""
    assertion_id: str
    beliefs: list[Belief]
    change_summary: list[str]


@dataclass
class MeaningResult:
    """Result of a meaning query."""
    concept: str
    current_version: MeaningVersion | None
    all_versions: list[MeaningVersion]
    compatibility_warnings: list[str]


@dataclass
class OverrideResult:
    """Result of an override query."""
    decision_id: str
    override: Override | None
    is_expired: bool
    time_remaining_seconds: float


@dataclass
class DependenciesResult:
    """Result of a dependencies query."""
    assertion_id: str
    direct_dependencies: list[str]
    transitive_dependencies: list[str]
    evidence_dependencies: list[str]
    depth: int


@dataclass
class InvalidationResult:
    """Result of an invalidation query."""
    assertion_id: str
    potential_counter_evidence: list[str]
    semantic_conflicts: list[str]
    dependency_failures: list[str]
    invalidation_scenarios: list[str]


class QueryEngine:
    """
    Main query engine for TruthCore Spine.
    
    Provides read-only access to all spine data.
    """
    
    def __init__(self, store: GraphStore):
        self.store = store
        self.belief_engine = BeliefEngine(store)
    
    # Q1: Why is this believed?
    def why(self, assertion_id: str) -> WhyResult | None:
        """
        Explain why an assertion is believed.
        
        Returns lineage, evidence, and confidence computation.
        """
        assertion = self.store.get_assertion(assertion_id)
        if not assertion:
            return None
        
        belief = self.belief_engine.get_current_belief(assertion_id)
        
        # Get evidence
        evidence_list = [
            self.store.get_evidence(eid)
            for eid in assertion.evidence_ids
        ]
        evidence_list = [e for e in evidence_list if e is not None]
        
        # Build confidence explanation
        if belief:
            current_conf = belief.current_confidence()
            confidence_explanation = (
                f"Current confidence: {current_conf:.2f} "
                f"(base: {belief.confidence:.2f}, method: {belief.confidence_method})"
            )
            formation_rationale = belief.rationale
            upstream = list(belief.upstream_belief_ids)
        else:
            confidence_explanation = "No active belief formed"
            formation_rationale = "Not yet believed"
            upstream = []
        
        return WhyResult(
            assertion=assertion,
            current_belief=belief,
            confidence_explanation=confidence_explanation,
            evidence_count=len(evidence_list),
            upstream_dependencies=upstream,
            formation_rationale=formation_rationale,
        )
    
    # Q2: What evidence supports or weakens it?
    def evidence(
        self,
        assertion_id: str,
        include_stale: bool = True,
    ) -> EvidenceResult | None:
        """
        Get evidence related to an assertion.
        
        Categorizes as supporting, weakening, or stale.
        """
        assertion = self.store.get_assertion(assertion_id)
        if not assertion:
            return None
        
        all_evidence = self.store.get_evidence_batch(list(assertion.evidence_ids))
        
        supporting = []
        stale = []
        
        for ev in all_evidence.values():
            if ev.is_stale():
                stale.append(ev)
            else:
                supporting.append(ev)
        
        # Calculate total weight (simple heuristic)
        total_weight = len(supporting) + (0.5 * len(stale))
        
        # For now, we don't have explicit weakening evidence
        # This would require tracking counter-evidence separately
        weakening = []
        
        if not include_stale:
            stale = []
        
        return EvidenceResult(
            assertion_id=assertion_id,
            supporting_evidence=supporting,
            weakening_evidence=weakening,
            stale_evidence=stale,
            total_weight=total_weight,
        )
    
    # Q3: When and why did this belief change?
    def history(self, assertion_id: str) -> HistoryResult | None:
        """
        Get belief version history for an assertion.
        
        Shows how confidence changed over time.
        """
        assertion = self.store.get_assertion(assertion_id)
        if not assertion:
            return None
        
        beliefs = self.belief_engine.get_belief_history(assertion_id)
        
        # Generate change summary
        changes = []
        for i, belief in enumerate(beliefs):
            if i == 0:
                changes.append(f"v1: Initial formation (confidence: {belief.confidence:.2f})")
            else:
                prev = beliefs[i-1]
                delta = belief.confidence - prev.confidence
                direction = "increased" if delta > 0 else "decreased"
                changes.append(
                    f"v{belief.version}: Confidence {direction} by {abs(delta):.2f} "
                    f"({prev.confidence:.2f} -> {belief.confidence:.2f})"
                )
            
            if belief.is_superseded():
                changes.append(f"  -> Superseded at {belief.superseded_at}")
        
        return HistoryResult(
            assertion_id=assertion_id,
            beliefs=beliefs,
            change_summary=changes,
        )
    
    # Q4: Which meaning version applies?
    def meaning(
        self,
        concept: str,
        timestamp: str | None = None,
    ) -> MeaningResult | None:
        """
        Get semantic meaning information for a concept.
        
        Returns current and historical versions.
        """
        # Load meaning registry
        meanings = self._load_meanings(concept)
        
        if not meanings:
            return MeaningResult(
                concept=concept,
                current_version=None,
                all_versions=[],
                compatibility_warnings=[f"No meaning registered for '{concept}'"],
            )
        
        # Find current version
        if timestamp:
            from datetime import datetime
            target_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            current = None
            for m in meanings:
                if m.is_current(target_time):
                    current = m
                    break
        else:
            # Get latest
            current = meanings[-1] if meanings else None
        
        # Check for compatibility issues
        warnings = []
        if len(meanings) > 1:
            latest = meanings[-1]
            for m in meanings[:-1]:
                if not m.is_compatible_with(latest):
                    warnings.append(
                        f"Version {m.version} is incompatible with current ({latest.version})"
                    )
        
        return MeaningResult(
            concept=concept,
            current_version=current,
            all_versions=meanings,
            compatibility_warnings=warnings,
        )
    
    # Q5: Who overrode this, when, and with what scope?
    def override(self, decision_id: str) -> OverrideResult | None:
        """
        Get override information for a decision.
        
        Returns override record and expiry status.
        """
        # Load override from storage
        override = self._load_override(decision_id)
        
        if not override:
            return OverrideResult(
                decision_id=decision_id,
                override=None,
                is_expired=False,
                time_remaining_seconds=0,
            )
        
        is_expired = override.is_expired()
        time_remaining = override.time_remaining()
        
        return OverrideResult(
            decision_id=decision_id,
            override=override,
            is_expired=is_expired,
            time_remaining_seconds=time_remaining,
        )
    
    # Q6: What assumptions does this depend on?
    def dependencies(
        self,
        assertion_id: str,
        recursive: bool = False,
        max_depth: int = 5,
    ) -> DependenciesResult | None:
        """
        Get dependency graph for an assertion.
        
        Shows upstream beliefs and evidence.
        """
        assertion = self.store.get_assertion(assertion_id)
        if not assertion:
            return None
        
        # Direct dependencies from evidence
        evidence_deps = list(assertion.evidence_ids)
        
        # Get belief dependencies
        belief = self.belief_engine.get_current_belief(assertion_id)
        direct_deps = list(belief.upstream_belief_ids) if belief else []
        
        transitive_deps = []
        if recursive and direct_deps:
            visited = {assertion_id}
            queue = list(direct_deps)
            depth = 0
            
            while queue and depth < max_depth:
                current = queue.pop(0)
                if current in visited:
                    continue
                
                visited.add(current)
                transitive_deps.append(current)
                
                # Get upstream of this dependency
                dep_belief = self.belief_engine.get_current_belief(current)
                if dep_belief:
                    for up in dep_belief.upstream_belief_ids:
                        if up not in visited:
                            queue.append(up)
                
                depth += 1
        
        return DependenciesResult(
            assertion_id=assertion_id,
            direct_dependencies=direct_deps,
            transitive_dependencies=transitive_deps,
            evidence_dependencies=evidence_deps,
            depth=len(transitive_deps) if recursive else 1,
        )
    
    # Q7: What would invalidate this belief?
    def invalidate(self, assertion_id: str) -> InvalidationResult | None:
        """
        Identify what could invalidate a belief.
        
        Returns counter-evidence patterns and scenarios.
        """
        assertion = self.store.get_assertion(assertion_id)
        if not assertion:
            return None
        
        belief = self.belief_engine.get_current_belief(assertion_id)
        
        # Potential counter-evidence types
        counter_evidence = [
            "Directly contradictory evidence",
            "Stale or expired evidence",
            "Evidence from conflicting sources",
        ]
        
        # Semantic conflicts
        semantic_conflicts = []
        if belief:
            for dep_id in belief.upstream_belief_ids:
                dep = self.belief_engine.get_current_belief(dep_id)
                if dep and dep.current_confidence() < 0.5:
                    semantic_conflicts.append(
                        f"Upstream belief {dep_id} has low confidence"
                    )
        
        # Dependency failures
        dependency_failures = []
        for ev_id in assertion.evidence_ids:
            ev = self.store.get_evidence(ev_id)
            if ev and ev.is_stale():
                dependency_failures.append(f"Evidence {ev_id} has expired")
        
        # Invalidation scenarios
        scenarios = [
            "New evidence contradicts current belief",
            "Upstream dependency confidence drops below threshold",
            "Evidence expires without replacement",
            "Semantic meaning changes (version incompatibility)",
            "Manual override by authorized human",
        ]
        
        return InvalidationResult(
            assertion_id=assertion_id,
            potential_counter_evidence=counter_evidence,
            semantic_conflicts=semantic_conflicts,
            dependency_failures=dependency_failures,
            invalidation_scenarios=scenarios,
        )
    
    def _load_meanings(self, concept: str) -> list[MeaningVersion]:
        """Load all meaning versions for a concept."""
        meaning_dir = self.store.base_path / "meanings" / concept
        if not meaning_dir.exists():
            return []
        
        meanings = []
        for f in meaning_dir.glob("v*.json"):
            import json
            with open(f, "r", encoding="utf-8") as file:
                data = json.load(file)
                meanings.append(MeaningVersion.from_dict(data))
        
        # Sort by version
        meanings.sort(key=lambda m: m.version)
        return meanings
    
    def _load_override(self, decision_id: str) -> Override | None:
        """Load override for a decision."""
        # Search in override storage
        override_dir = self.store.base_path / "overrides"
        if not override_dir.exists():
            return None
        
        for subdir in override_dir.iterdir():
            if subdir.is_dir():
                for f in subdir.glob("*.json"):
                    import json
                    with open(f, "r", encoding="utf-8") as file:
                        data = json.load(file)
                        if data.get("override_id") == decision_id or data.get("decision_id") == decision_id:
                            return Override.from_dict(data)
        
        return None


class SpineQueryClient:
    """
    High-level client for querying TruthCore Spine.
    
    Provides convenient access to all query types.
    """
    
    def __init__(self, store: GraphStore | None = None):
        self.store = store or GraphStore()
        self.engine = QueryEngine(self.store)
    
    def why(self, assertion_id: str) -> WhyResult | None:
        """Query: Why is this believed?"""
        return self.engine.why(assertion_id)
    
    def evidence(self, assertion_id: str, **kwargs) -> EvidenceResult | None:
        """Query: What evidence supports or weakens it?"""
        return self.engine.evidence(assertion_id, **kwargs)
    
    def history(self, assertion_id: str) -> HistoryResult | None:
        """Query: When and why did this belief change?"""
        return self.engine.history(assertion_id)
    
    def meaning(self, concept: str, **kwargs) -> MeaningResult | None:
        """Query: Which meaning version applies?"""
        return self.engine.meaning(concept, **kwargs)
    
    def override(self, decision_id: str) -> OverrideResult | None:
        """Query: Who overrode this, when, and with what scope?"""
        return self.engine.override(decision_id)
    
    def dependencies(self, assertion_id: str, **kwargs) -> DependenciesResult | None:
        """Query: What assumptions does this depend on?"""
        return self.engine.dependencies(assertion_id, **kwargs)
    
    def invalidate(self, assertion_id: str) -> InvalidationResult | None:
        """Query: What would invalidate this belief?"""
        return self.engine.invalidate(assertion_id)
