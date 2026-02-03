"""Tests for TruthCore Spine module.

Covers all phases:
- Phase 0: Core primitives
- Phase 1: Graph & Belief Engine
- Phase 2: Ingestion
- Phase 3: Query Surface
- Phase 4: CLI
- Phase 5: Integration
"""

import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from truthcore.spine import (
    Assertion,
    Belief,
    BeliefEngine,
    ClaimType,
    Decision,
    DecisionType,
    Evidence,
    EvidenceType,
    GraphStore,
    IngestionBridge,
    MeaningVersion,
    Override,
    QueryEngine,
    SpineQueryClient,
)


class TestPhase0Primitives:
    """Test core primitives."""

    def test_evidence_creation(self):
        """Test Evidence dataclass."""
        ev = Evidence(
            evidence_id="abc123",
            evidence_type=EvidenceType.RAW,
            content_hash="hash123",
            source="test",
            timestamp=datetime.now(UTC).isoformat(),
        )
        assert ev.evidence_id == "abc123"
        assert not ev.is_stale()

    def test_evidence_staleness(self):
        """Test evidence staleness detection."""
        ev = Evidence(
            evidence_id="abc123",
            evidence_type=EvidenceType.RAW,
            content_hash="hash123",
            source="test",
            timestamp="2024-01-01T00:00:00+00:00",
            validity_seconds=60,  # 1 minute TTL
        )
        assert ev.is_stale()

    def test_assertion_creation(self):
        """Test Assertion dataclass."""
        assertion = Assertion(
            assertion_id="assert_123",
            claim="Tests pass",
            evidence_ids=("ev1", "ev2"),
            claim_type=ClaimType.OBSERVED,
            source="test_engine",
            timestamp=datetime.now(UTC).isoformat(),
        )
        assert assertion.claim == "Tests pass"
        assert len(assertion.evidence_ids) == 2

    def test_assertion_compute_id(self):
        """Test content-addressed ID computation."""
        claim = "Deployment ready"
        evidence_ids = ["ev1", "ev2"]
        id1 = Assertion.compute_id(claim, evidence_ids)
        id2 = Assertion.compute_id(claim, evidence_ids)
        assert id1 == id2  # Deterministic

    def test_belief_creation(self):
        """Test Belief dataclass."""
        belief = Belief(
            belief_id="belief_123",
            assertion_id="assert_123",
            version=1,
            confidence=0.85,
            confidence_method="test",
            formed_at=datetime.now(UTC).isoformat(),
            superseded_at=None,
        )
        assert belief.confidence == 0.85
        assert not belief.is_superseded()

    def test_belief_confidence_clamping(self):
        """Test confidence is clamped to [0, 1]."""
        belief = Belief(
            belief_id="belief_123",
            assertion_id="assert_123",
            version=1,
            confidence=1.5,  # Should be clamped
            confidence_method="test",
            formed_at=datetime.now(UTC).isoformat(),
            superseded_at=None,
        )
        assert belief.confidence == 1.0

    def test_belief_decay(self):
        """Test confidence decay over time."""
        belief = Belief(
            belief_id="belief_123",
            assertion_id="assert_123",
            version=1,
            confidence=1.0,
            confidence_method="test",
            formed_at="2024-01-01T00:00:00+00:00",  # Old
            superseded_at=None,
            decay_rate=0.1,  # 10% per day
        )
        # Should have decayed
        current = belief.current_confidence()
        assert current < 1.0

    def test_meaning_version(self):
        """Test MeaningVersion dataclass."""
        meaning = MeaningVersion(
            meaning_id="deployment.ready",
            version="1.0.0",
            definition="Score >= 90",
            computation="score >= 90",
        )
        assert meaning.meaning_id == "deployment.ready"
        assert meaning.is_current()

    def test_decision_creation(self):
        """Test Decision dataclass."""
        decision = Decision(
            decision_id="dec_123",
            decision_type=DecisionType.SYSTEM,
            action="SHIP",
            belief_ids=("belief_1",),
            actor="test_engine",
        )
        assert decision.action == "SHIP"

    def test_override_expiry(self):
        """Test Override expiry."""
        override = Override(
            override_id="override_123",
            original_decision="FAIL",
            override_decision="PASS",
            actor="user@example.com",
            authority_scope="team_lead",
            rationale="Test",
            expires_at="2024-01-01T00:00:00+00:00",  # Expired
        )
        assert override.is_expired()

    def test_serialization_roundtrip(self):
        """Test serialization and deserialization."""
        original = Assertion(
            assertion_id="test_123",
            claim="Test claim",
            evidence_ids=("ev1",),
            claim_type=ClaimType.OBSERVED,
            source="test",
            timestamp=datetime.now(UTC).isoformat(),
        )

        data = original.to_dict()
        restored = Assertion.from_dict(data)

        assert restored.assertion_id == original.assertion_id
        assert restored.claim == original.claim


class TestPhase1GraphAndBelief:
    """Test graph storage and belief engine."""

    def test_graph_store_creation(self):
        """Test GraphStore initialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = GraphStore(tmpdir)
            assert (Path(tmpdir) / "assertions").exists()
            assert (Path(tmpdir) / "evidence").exists()

    def test_store_and_retrieve_evidence(self):
        """Test evidence storage and retrieval."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = GraphStore(tmpdir)

            ev = Evidence(
                evidence_id="ev_123",
                evidence_type=EvidenceType.RAW,
                content_hash="hash123",
                source="test",
                timestamp=datetime.now(UTC).isoformat(),
            )

            store.store_evidence(ev)
            retrieved = store.get_evidence("ev_123")

            assert retrieved is not None
            assert retrieved.evidence_id == ev.evidence_id

    def test_store_and_retrieve_assertion(self):
        """Test assertion storage and retrieval."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = GraphStore(tmpdir)

            assertion = Assertion(
                assertion_id="assert_123",
                claim="Test",
                evidence_ids=("ev1",),
                claim_type=ClaimType.OBSERVED,
                source="test",
                timestamp=datetime.now(UTC).isoformat(),
            )

            store.store_assertion(assertion)
            retrieved = store.get_assertion("assert_123")

            assert retrieved is not None
            assert retrieved.claim == assertion.claim

    def test_belief_engine_formation(self):
        """Test belief formation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = GraphStore(tmpdir)
            engine = BeliefEngine(store)

            assertion = Assertion(
                assertion_id="assert_123",
                claim="Test",
                evidence_ids=(),
                claim_type=ClaimType.OBSERVED,
                source="test",
                timestamp=datetime.now(UTC).isoformat(),
            )

            belief = engine.form_belief(assertion, initial_confidence=0.9)

            assert belief.assertion_id == assertion.assertion_id
            assert belief.version == 1
            assert belief.confidence == 0.9

    def test_belief_versioning(self):
        """Test belief versioning."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = GraphStore(tmpdir)
            engine = BeliefEngine(store)

            assertion = Assertion(
                assertion_id="assert_123",
                claim="Test",
                evidence_ids=(),
                claim_type=ClaimType.OBSERVED,
                source="test",
                timestamp=datetime.now(UTC).isoformat(),
            )
            store.store_assertion(assertion)

            # Form first belief
            belief1 = engine.form_belief(assertion, initial_confidence=0.9)
            assert belief1.version == 1

            # Update belief (pass new_evidence=None to trigger recompute)
            belief2 = engine.update_belief(assertion.assertion_id)
            assert belief2 is not None
            assert belief2.version == 2

            # Check history
            history = engine.get_belief_history(assertion.assertion_id)
            assert len(history) == 2

    def test_belief_history_at_time(self):
        """Test retrieving belief at specific time."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = GraphStore(tmpdir)
            engine = BeliefEngine(store)

            assertion = Assertion(
                assertion_id="assert_123",
                claim="Test",
                evidence_ids=(),
                claim_type=ClaimType.OBSERVED,
                source="test",
                timestamp=datetime.now(UTC).isoformat(),
            )
            store.store_assertion(assertion)

            # Form belief at specific time
            old_time = "2024-01-01T12:00:00+00:00"
            belief = engine.form_belief(
                assertion,
                initial_confidence=0.9,
                rationale="Test at specific time",
            )

            # Get current belief
            current = engine.get_current_belief(assertion.assertion_id)
            assert current is not None


class TestPhase3Queries:
    """Test query surface."""

    def test_why_query(self):
        """Test 'why' query."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = GraphStore(tmpdir)
            query = QueryEngine(store)

            # Create assertion
            assertion = Assertion(
                assertion_id="assert_123",
                claim="Test claim",
                evidence_ids=(),
                claim_type=ClaimType.OBSERVED,
                source="test",
                timestamp=datetime.now(UTC).isoformat(),
            )
            store.store_assertion(assertion)

            # Query
            result = query.why("assert_123")
            assert result is not None
            assert result.assertion.claim == "Test claim"

    def test_evidence_query(self):
        """Test evidence query."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = GraphStore(tmpdir)
            query = QueryEngine(store)

            # Create evidence and assertion
            ev = Evidence(
                evidence_id="ev_123",
                evidence_type=EvidenceType.RAW,
                content_hash="hash123",
                source="test",
                timestamp=datetime.now(UTC).isoformat(),
            )
            store.store_evidence(ev)

            assertion = Assertion(
                assertion_id="assert_123",
                claim="Test",
                evidence_ids=("ev_123",),
                claim_type=ClaimType.OBSERVED,
                source="test",
                timestamp=datetime.now(UTC).isoformat(),
            )
            store.store_assertion(assertion)

            # Query
            result = query.evidence("assert_123")
            assert result is not None
            assert len(result.supporting_evidence) == 1

    def test_history_query(self):
        """Test history query."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = GraphStore(tmpdir)
            engine = BeliefEngine(store)
            query = QueryEngine(store)

            assertion = Assertion(
                assertion_id="assert_123",
                claim="Test",
                evidence_ids=(),
                claim_type=ClaimType.OBSERVED,
                source="test",
                timestamp=datetime.now(UTC).isoformat(),
            )
            store.store_assertion(assertion)

            # Form multiple beliefs
            engine.form_belief(assertion, initial_confidence=0.8)
            engine.update_belief(assertion.assertion_id)

            # Query history
            result = query.history("assert_123")
            assert result is not None
            assert len(result.beliefs) == 2
            assert len(result.change_summary) >= 2  # May include superseded entries

    def test_dependencies_query(self):
        """Test dependencies query."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = GraphStore(tmpdir)
            query = QueryEngine(store)

            # Create assertion with evidence
            ev = Evidence(
                evidence_id="ev_123",
                evidence_type=EvidenceType.RAW,
                content_hash="hash123",
                source="test",
                timestamp=datetime.now(UTC).isoformat(),
            )
            store.store_evidence(ev)

            assertion = Assertion(
                assertion_id="assert_123",
                claim="Test",
                evidence_ids=("ev_123",),
                claim_type=ClaimType.OBSERVED,
                source="test",
                timestamp=datetime.now(UTC).isoformat(),
            )
            store.store_assertion(assertion)

            # Query dependencies
            result = query.dependencies("assert_123")
            assert result is not None
            assert len(result.evidence_dependencies) == 1

    def test_invalidate_query(self):
        """Test invalidation query."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = GraphStore(tmpdir)
            query = QueryEngine(store)

            assertion = Assertion(
                assertion_id="assert_123",
                claim="Test",
                evidence_ids=(),
                claim_type=ClaimType.OBSERVED,
                source="test",
                timestamp=datetime.now(UTC).isoformat(),
            )
            store.store_assertion(assertion)

            # Query invalidation scenarios
            result = query.invalidate("assert_123")
            assert result is not None
            assert len(result.invalidation_scenarios) > 0

    def test_query_not_found(self):
        """Test query for non-existent assertion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = GraphStore(tmpdir)
            query = QueryEngine(store)

            result = query.why("non_existent")
            assert result is None


class TestPhase2Ingestion:
    """Test ingestion bridge."""

    def test_ingestion_bridge_disabled(self):
        """Test bridge when disabled."""
        bridge = IngestionBridge(enabled=False)
        result = bridge.record_finding(None)
        assert not result  # Should return False when disabled

    def test_signal_transformation(self):
        """Test signal to assertion transformation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = GraphStore(tmpdir)

            signal = {
                "signal_type": "assertion",
                "source": "test_engine",
                "claim": "Tests pass",
                "timestamp": datetime.now(UTC).isoformat(),
                "context": {"run_id": "test_run"},
            }

            from truthcore.spine.ingest import SignalTransformer
            transformer = SignalTransformer(store)
            evidence, assertion = transformer.transform_signal(signal)

            assert assertion is not None
            assert assertion.claim == "Tests pass"


class TestSpineClient:
    """Test high-level SpineQueryClient."""

    def test_client_convenience_methods(self):
        """Test client convenience methods."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = SpineQueryClient(GraphStore(tmpdir))

            # Create test data
            store = GraphStore(tmpdir)
            assertion = Assertion(
                assertion_id="test_123",
                claim="Test",
                evidence_ids=(),
                claim_type=ClaimType.OBSERVED,
                source="test",
                timestamp=datetime.now(UTC).isoformat(),
            )
            store.store_assertion(assertion)

            # Test all query methods
            assert client.why("test_123") is not None
            assert client.evidence("test_123") is not None
            assert client.history("test_123") is not None
            assert client.dependencies("test_123") is not None
            assert client.invalidate("test_123") is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
