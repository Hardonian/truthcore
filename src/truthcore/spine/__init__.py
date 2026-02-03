"""TruthCore Spine - Read-only truth spine for explanation and lineage.

The Spine module provides:
- Core primitives (Assertion, Evidence, Belief, etc.)
- Graph storage with content-addressed persistence
- Belief engine with confidence decay
- Query surface (7 MVP query types)
- Ingestion from instrumentation layer
- Integration bridges

Usage:
    from truthcore.spine import SpineClient

    client = SpineClient()

    # Query why something is believed
    result = client.query.why("assertion_id")

    # Get belief history
    history = client.query.history("assertion_id")
"""

from truthcore.spine.belief import BeliefEngine
from truthcore.spine.bridge import SpineBridge, SpineConfig
from truthcore.spine.graph import AssertionLineage, GraphStore
from truthcore.spine.ingest import (
    IngestionBridge,
    IngestionEngine,
    SignalTransformer,
)
from truthcore.spine.primitives import (
    Assertion,
    Belief,
    ClaimType,
    Decision,
    DecisionType,
    Evidence,
    EvidenceType,
    MeaningVersion,
    Override,
)
from truthcore.spine.query import (
    DependenciesResult,
    EvidenceResult,
    HistoryResult,
    InvalidationResult,
    MeaningResult,
    OverrideResult,
    QueryEngine,
    SpineQueryClient,
    WhyResult,
)

__all__ = [
    # Primitives
    "Assertion",
    "Belief",
    "ClaimType",
    "Decision",
    "DecisionType",
    "Evidence",
    "EvidenceType",
    "MeaningVersion",
    "Override",
    # Graph
    "GraphStore",
    "AssertionLineage",
    # Belief
    "BeliefEngine",
    # Query
    "QueryEngine",
    "SpineQueryClient",
    "WhyResult",
    "EvidenceResult",
    "HistoryResult",
    "MeaningResult",
    "OverrideResult",
    "DependenciesResult",
    "InvalidationResult",
    # Ingestion
    "IngestionBridge",
    "IngestionEngine",
    "SignalTransformer",
    # Bridge
    "SpineBridge",
    "SpineConfig",
]
