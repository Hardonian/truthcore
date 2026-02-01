"""Belief engine for TruthCore Spine.

Computes and manages beliefs with confidence scoring, decay, and versioning.
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from truthcore.spine.primitives import Assertion, Belief, Evidence
from truthcore.spine.graph import GraphStore


class BeliefEngine:
    """
    Computes and updates beliefs based on assertions and evidence.
    
    Responsibilities:
    - Form initial beliefs from assertions
    - Update confidence when evidence changes
    - Propagate decay through dependency chains
    - Version belief history
    """
    
    def __init__(self, store: GraphStore):
        self.store = store
    
    def form_belief(
        self,
        assertion: Assertion,
        initial_confidence: float | None = None,
        decay_rate: float = 0.0,
        upstream_belief_ids: list[str] | None = None,
        rationale: str = "",
    ) -> Belief:
        """
        Form a new belief from an assertion.
        
        If no initial confidence provided, computes from evidence quality.
        """
        if initial_confidence is None:
            initial_confidence = self._compute_confidence_from_evidence(assertion)
        
        # Get next version number
        version = self._get_next_version(assertion.assertion_id)
        
        # Create belief
        belief = Belief(
            belief_id=Belief.compute_id(assertion.assertion_id, version),
            assertion_id=assertion.assertion_id,
            version=version,
            confidence=initial_confidence,
            confidence_method="evidence_weighted" if not rationale else "specified",
            formed_at=datetime.now(UTC).isoformat(),
            superseded_at=None,
            upstream_belief_ids=tuple(upstream_belief_ids or []),
            rationale=rationale or f"Formed from {len(assertion.evidence_ids)} evidence items",
            decay_rate=decay_rate,
        )
        
        # Store belief
        self._store_belief(belief)
        
        # Mark previous version as superseded (if any)
        if version > 1:
            self._supersede_previous_version(assertion.assertion_id, version - 1, belief.formed_at)
        
        return belief
    
    def update_belief(
        self,
        assertion_id: str,
        new_evidence: list[Evidence] | None = None,
        decay_rate: float | None = None,
    ) -> Belief | None:
        """
        Update a belief with new evidence or parameters.
        
        Creates a new belief version with updated confidence.
        """
        # Get current belief
        current = self.get_current_belief(assertion_id)
        if not current:
            return None
        
        # Get assertion
        assertion = self.store.get_assertion(assertion_id)
        if not assertion:
            return None
        
        # Compute new confidence
        if new_evidence:
            new_confidence = self._compute_confidence_from_evidence(assertion, new_evidence)
        else:
            # Just recompute with existing evidence
            new_confidence = self._compute_confidence_from_evidence(assertion)
        
        # Apply decay rate if specified
        new_decay = decay_rate if decay_rate is not None else current.decay_rate
        
        # Create new version
        return self.form_belief(
            assertion=assertion,
            initial_confidence=new_confidence,
            decay_rate=new_decay,
            upstream_belief_ids=list(current.upstream_belief_ids),
            rationale=f"Updated from v{current.version}: confidence {current.confidence:.2f} -> {new_confidence:.2f}",
        )
    
    def get_current_belief(self, assertion_id: str) -> Belief | None:
        """Get the current (latest) belief for an assertion."""
        current_path = self.store.base_path / "beliefs" / assertion_id / "current.json"
        
        if not current_path.exists():
            # Try to find any version
            beliefs = self.get_belief_history(assertion_id)
            if beliefs:
                return beliefs[-1]  # Latest
            return None
        
        # Read the current symlink target or file
        if current_path.is_symlink():
            target = current_path.readlink()
            belief_path = current_path.parent / target
        else:
            belief_path = current_path
        
        if not belief_path.exists():
            return None
        
        with open(belief_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return Belief.from_dict(data)
    
    def get_belief_history(self, assertion_id: str) -> list[Belief]:
        """Get all belief versions for an assertion."""
        belief_dir = self.store.base_path / "beliefs" / assertion_id
        if not belief_dir.exists():
            return []
        
        beliefs = []
        for f in belief_dir.glob("v*.json"):
            with open(f, "r", encoding="utf-8") as file:
                data = json.load(file)
                beliefs.append(Belief.from_dict(data))
        
        # Sort by version
        beliefs.sort(key=lambda b: b.version)
        return beliefs
    
    def get_belief_at_time(self, assertion_id: str, timestamp: str) -> Belief | None:
        """Get the belief that was current at a specific time."""
        history = self.get_belief_history(assertion_id)
        if not history:
            return None
        
        target_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        
        # Find the belief that was current at that time
        current = None
        for belief in history:
            formed_time = datetime.fromisoformat(belief.formed_at.replace('Z', '+00:00'))
            if formed_time <= target_time:
                # Check if it was superseded before target time
                if belief.superseded_at:
                    superseded_time = datetime.fromisoformat(belief.superseded_at.replace('Z', '+00:00'))
                    if superseded_time > target_time:
                        current = belief
                else:
                    current = belief
        
        return current
    
    def propagate_decay(self, upstream_assertion_id: str) -> list[Belief]:
        """
        When an upstream belief decays, propagate to downstream beliefs.
        
        Returns list of updated beliefs.
        """
        # Get upstream belief
        upstream = self.get_current_belief(upstream_assertion_id)
        if not upstream:
            return []
        
        updated = []
        
        # Find all beliefs that depend on this one
        # This requires scanning all beliefs - in production, use an index
        all_assertions = self.store.list_assertions()
        
        for assertion_id in all_assertions:
            current = self.get_current_belief(assertion_id)
            if not current:
                continue
            
            if upstream_assertion_id in current.upstream_belief_ids:
                # This belief depends on the upstream one
                # Recompute confidence with decay
                new_confidence = current.confidence * upstream.current_confidence()
                
                if abs(new_confidence - current.confidence) > 0.01:
                    # Significant change, create new version
                    assertion = self.store.get_assertion(assertion_id)
                    if assertion:
                        new_belief = self.form_belief(
                            assertion=assertion,
                            initial_confidence=new_confidence,
                            decay_rate=current.decay_rate,
                            upstream_belief_ids=list(current.upstream_belief_ids),
                            rationale=f"Decay propagated from {upstream_assertion_id}: {current.confidence:.2f} -> {new_confidence:.2f}",
                        )
                        updated.append(new_belief)
        
        return updated
    
    def _compute_confidence_from_evidence(
        self,
        assertion: Assertion,
        evidence_list: list[Evidence] | None = None,
    ) -> float:
        """
        Compute confidence based on evidence quality and quantity.
        
        This is a simple heuristic - can be replaced with more sophisticated ML.
        """
        if evidence_list is None:
            evidence_list = [
                self.store.get_evidence(eid)
                for eid in assertion.evidence_ids
            ]
            evidence_list = [e for e in evidence_list if e is not None]
        
        if not evidence_list:
            return 0.5  # Neutral confidence with no evidence
        
        # Base confidence from evidence count (diminishing returns)
        base = 0.5 + (0.1 * min(len(evidence_list), 5))
        
        # Adjust for stale evidence
        fresh_count = sum(1 for e in evidence_list if not e.is_stale())
        stale_ratio = 1 - (fresh_count / len(evidence_list))
        
        # Reduce confidence if much evidence is stale
        confidence = base * (1 - (stale_ratio * 0.3))
        
        # Clamp to [0, 1]
        return max(0.0, min(1.0, confidence))
    
    def _get_next_version(self, assertion_id: str) -> int:
        """Get next version number for an assertion."""
        history = self.get_belief_history(assertion_id)
        if not history:
            return 1
        return history[-1].version + 1
    
    def _store_belief(self, belief: Belief) -> Path:
        """Store a belief."""
        belief_dir = self.store.base_path / "beliefs" / belief.assertion_id
        belief_dir.mkdir(parents=True, exist_ok=True)
        
        # Store versioned file
        version_file = belief_dir / f"v{belief.version:03d}.json"
        with open(version_file, "w", encoding="utf-8") as f:
            json.dump(belief.to_dict(), f, indent=2, sort_keys=True)
        
        # Update current symlink
        current_link = belief_dir / "current.json"
        if current_link.exists() or current_link.is_symlink():
            current_link.unlink()
        
        # On Windows, symlinks may require special permissions, so use a file instead
        try:
            current_link.symlink_to(version_file.name)
        except (OSError, NotImplementedError):
            # Fallback: copy the file
            import shutil
            shutil.copy2(version_file, current_link)
        
        return version_file
    
    def _supersede_previous_version(self, assertion_id: str, version: int, timestamp: str) -> None:
        """Mark a previous belief version as superseded."""
        belief_dir = self.store.base_path / "beliefs" / assertion_id
        version_file = belief_dir / f"v{version:03d}.json"
        
        if not version_file.exists():
            return
        
        with open(version_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        data["superseded_at"] = timestamp
        
        with open(version_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
    
    def compute_belief_stats(self) -> dict[str, Any]:
        """Compute statistics about beliefs."""
        all_assertions = self.store.list_assertions()
        
        total_beliefs = 0
        high_confidence = 0
        medium_confidence = 0
        low_confidence = 0
        superseded_count = 0
        
        for assertion_id in all_assertions:
            history = self.get_belief_history(assertion_id)
            total_beliefs += len(history)
            
            for belief in history:
                if belief.is_superseded():
                    superseded_count += 1
                
                current_conf = belief.current_confidence()
                if current_conf >= 0.8:
                    high_confidence += 1
                elif current_conf >= 0.5:
                    medium_confidence += 1
                else:
                    low_confidence += 1
        
        return {
            "total_beliefs": total_beliefs,
            "assertions_with_beliefs": len(all_assertions),
            "high_confidence": high_confidence,
            "medium_confidence": medium_confidence,
            "low_confidence": low_confidence,
            "superseded_beliefs": superseded_count,
            "average_confidence": (high_confidence * 0.9 + medium_confidence * 0.65 + low_confidence * 0.25) / max(total_beliefs, 1),
        }
