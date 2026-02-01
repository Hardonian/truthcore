# TruthCore Milestone 1: Read-Only Truth Spine
**Status:** Defined → Ready for Implementation  
**Target:** v0.3.0  
**Estimated Duration:** 4-6 weeks  
**Success Criteria:** Engineers voluntarily consult TruthCore for explanation queries

---

## EXECUTIVE SUMMARY

This milestone transforms TruthCore from a point-in-time verdict system into a **read-only, consultative truth spine**. It provides explanation without authority, lineage without enforcement, and memory without presumption.

**The Core Contract:**
- Systems may consult TruthCore; TruthCore never pushes
- TruthCore explains; it does not decide
- TruthCore remembers; it does not enforce
- TruthCore detects contradictions; it does not resolve them

**Success is measured by adoption:** If engineers and operators do not voluntarily query TruthCore, this milestone has failed.

---

## WHAT EXISTS vs. WHAT WE BUILD

### Current State (Reality)
- **Verdict aggregation:** Point-in-time scoring with no memory
- **Finding model:** Clean evidence containers with hashes
- **Determinism:** Achieved through canonical JSON and content addressing
- **Silent Instrumentation:** Designed, not yet implemented (emits raw signals)
- **Cognitive Substrate:** Designed, not yet implemented (reasons over signals)

### Gap This Milestone Closes
TruthCore currently answers "What is the verdict now?" but cannot answer:
- "Why do we believe this?"
- "What evidence supports it?"
- "When did this belief change?"
- "Who overrode this decision?"

This milestone implements the infrastructure to answer those questions.

---

## MILESTONE SCOPE: BUILD vs. DEFER

### IN SCOPE (Must Deliver)

#### 1. Core Primitives Module (`src/truthcore/spine/primitives/`)
- [ ] **Assertion** - Immutable claims with evidence linkage
- [ ] **Evidence** - Content-addressed data inputs
- [ ] **Belief** - Versioned assertions with confidence decay
- [ ] **MeaningVersion** - Semantic versioning for concepts
- [ ] **Decision** - Recorded choices with provenance
- [ ] **Override** - Scoped human interventions

#### 2. Assertion Graph Storage (`src/truthcore/spine/graph/`)
- [ ] DAG storage with lineage tracking
- [ ] Content-addressed persistence
- [ ] Contradiction detection (report only, never resolve)
- [ ] Deterministic replay support

#### 3. Belief Engine (`src/truthcore/spine/belief/`)
- [ ] Confidence computation with decay
- [ ] Version history for belief changes
- [ ] Dependency propagation
- [ ] Staleness detection

#### 4. Telemetry Ingestion (`src/truthcore/spine/ingest/`)
- [ ] Ingest from Silent Instrumentation Layer
- [ ] Signal transformation to assertions
- [ ] Deduplication via content hashing
- [ ] Async, non-blocking ingestion

#### 5. Query Surface (`src/truthcore/spine/query/`)
- [ ] **Why Query** - Belief provenance and lineage
- [ ] **Evidence Query** - Supporting/weakening evidence
- [ ] **History Query** - Belief version timeline
- [ ] **Meaning Query** - Semantic version resolution
- [ ] **Override Query** - Human intervention tracking
- [ ] **Dependency Query** - Assumption tracing
- [ ] **Invalidation Query** - Counter-evidence identification

#### 6. Integration Bridge (`src/truthcore/spine/bridge/`)
- [ ] Finding → Assertion conversion
- [ ] Verdict → Decision recording
- [ ] Manifest enrichment with lineage
- [ ] Backward-compatible metadata extension

#### 7. CLI Extension (`truthctl spine`)
- [ ] `truthctl spine why <assertion-id>` - Explain belief
- [ ] `truthctl spine lineage <assertion-id>` - Show provenance
- [ ] `truthctl spine history <assertion-id>` - Belief versions
- [ ] `truthctl spine contradicts` - List detected contradictions
- [ ] `truthctl spine meaning <concept>` - Semantic resolution

### OUT OF SCOPE (Explicitly Deferred)

#### Deferred to Milestone 2+
- ❌ Economic signal processing (cost/risk/value tracking)
- ❌ Pattern detection and organizational learning
- ❌ Stage-gate detection (early/scaling/mature)
- ❌ Tooling mismatch detection
- ❌ Human governance UI (override management interface)
- ❌ Automated recommendation engine
- ❌ Enforcement mechanisms (any BLOCK mode)
- ❌ Real-time alerting on contradictions

#### Never in Scope (Per Charter)
- ❌ Write access to upstream systems
- ❌ Decision-making authority
- ❌ Scoring or ranking systems
- ❌ Ambiguity collapse (auto-resolution)
- ❌ Single source of truth (controlling sense)
- ❌ Behavioral mutation or blocking

---

## ARCHITECTURE: READ-ONLY TRUTH SPINE

### System Context Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     EXISTING SYSTEMS                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │   Settler   │  │  ReadyLayer │  │    Keys     │             │
│  │  (releases) │  │    (PR/CI)  │  │  (secrets)  │             │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘             │
└─────────┼────────────────┼────────────────┼───────────────────┘
          │                │                │
          │ Produces       │ Produces       │ Produces
          ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│              SILENT INSTRUMENTATION LAYER                       │
│         (Observe-only, feature-flagged, zero-overhead)          │
│  • Captures assertions, evidence, decisions, overrides         │
│  • Emits structured signals without blocking                   │
│  • Safe to deploy, safe to remove                              │
└───────────────────────────┬─────────────────────────────────────┘
                            │ Signals flow downstream only
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    TRUTHCORE SPINE (THIS MILESTONE)             │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │   Ingest    │  │    Graph    │  │   Belief    │             │
│  │  Transform  │→ │   Storage   │→ │   Engine    │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
│          │              │                │                      │
│          ▼              ▼                ▼                      │
│  ┌─────────────────────────────────────────────────────┐       │
│  │                 QUERY SURFACE                       │       │
│  │  Why? / Evidence? / History? / Meaning? / Override? │       │
│  └─────────────────────────────────────────────────────┘       │
│                           │                                    │
└───────────────────────────┼────────────────────────────────────┘
                            │ READ-ONLY (systems consult spine)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CONSULTING SYSTEMS                           │
│  • Engineers via CLI: `truthctl spine why ...`                 │
│  • Dashboard: Visualization of belief lineage                  │
│  • Other services: API queries for explanation                 │
│  • Future enforcement systems (if any): Read justification     │
└─────────────────────────────────────────────────────────────────┘
```

### Key Architectural Decisions

#### 1. Content-Addressed Storage
- All assertions, evidence, and beliefs stored by content hash
- Enables deduplication and deterministic replay
- Schema: `blake2b(serialized_json)`

#### 2. Append-Only Log Structure
- New beliefs create new versions; old versions immutable
- Contradictions recorded, not resolved
- Decisions append to history; overrides append to decision

#### 3. Zero Write-Back Guarantee
- TruthCore accepts telemetry via queue
- TruthCore never writes to source systems
- Query results are read-only views

#### 4. Deterministic Replay
- All operations produce same output for same input
- No random sampling in core logic
- Timestamps normalized to UTC

---

## CORE PRIMITIVES

### 1. Assertion
```python
@dataclass(frozen=True)
class Assertion:
    """
    A claim backed by evidence. Immutable and content-addressed.
    
    Assertions do not have confidence - they are statements of what
    the system observed or calculated. Confidence belongs to Beliefs.
    """
    assertion_id: str           # blake2b hash of claim + evidence_ids
    claim: str                  # Human-readable claim text
    evidence_ids: List[str]     # References to Evidence objects
    claim_type: ClaimType       # OBSERVED, DERIVED, INFERRED
    source: str                 # Origin (engine, human, external)
    timestamp: str              # ISO 8601 UTC
    context: Dict[str, Any]     # Run ID, profile, etc.
    
    def lineage(self, store: GraphStore) -> AssertionLineage: ...
```

### 2. Evidence
```python
@dataclass(frozen=True)
class Evidence:
    """
    Raw or derived data that supports assertions.
    
    Evidence is the foundation - assertions are built upon it.
    Both are immutable and content-addressed.
    """
    evidence_id: str            # blake2b hash of content
    evidence_type: EvidenceType # RAW, DERIVED, EXTERNAL
    content_hash: str           # Hash of actual data
    source: str                 # Where it came from
    timestamp: str              # When captured
    validity_seconds: int       # How long this evidence remains valid
    metadata: Dict[str, Any]    # Schema version, format, etc.
    
    def is_stale(self, now: datetime) -> bool: ...
```

### 3. Belief
```python
@dataclass(frozen=True)
class Belief:
    """
    A versioned belief in an assertion with confidence scoring.
    
    Beliefs are NOT mutable - each update creates a new Belief
    with incremented version number. Previous beliefs retained
    for history queries.
    """
    belief_id: str              # assertion_id + version
    assertion_id: str           # What we believe
    version: int                # Monotonically increasing
    confidence: float           # [0.0, 1.0]
    confidence_method: str      # How computed (rule-based, ML, human)
    formed_at: str              # ISO 8601
    superseded_at: str          # ISO 8601 (when newer belief formed)
    upstream_belief_ids: List[str]  # Beliefs this depends on
    rationale: str              # Why this confidence level
    
    def current_confidence(self, now: datetime, decay_rate: float) -> float: ...
```

### 4. MeaningVersion
```python
@dataclass(frozen=True)
class MeaningVersion:
    """
    Semantic versioning for the *meaning* of concepts.
    
    When "deployment ready" changes from "score >= 90" to
    "score >= 90 AND all reviews complete", this captures
    that semantic drift explicitly.
    """
    meaning_id: str             # Semantic identifier
    version: str                # SemVer (e.g., "2.1.0")
    definition: str             # Human-readable definition
    computation: Optional[str]  # Formula or algorithm
    examples: List[Dict]        # Exemplars
    valid_from: str             # ISO 8601
    valid_until: Optional[str]  # ISO 8601 or None (current)
    
    def is_current(self, timestamp: str) -> bool: ...
    def is_compatible_with(self, other: "MeaningVersion") -> bool: ...
```

### 5. Decision
```python
@dataclass(frozen=True)
class Decision:
    """
    A recorded choice made by system or human.
    
    Decisions reference the beliefs that informed them.
    They do not require TruthCore's permission to be made.
    """
    decision_id: str            # Content hash
    decision_type: DecisionType # SYSTEM, HUMAN_OVERRIDE
    action: str                 # What was decided
    belief_ids: List[str]       # Beliefs that informed this
    context: Dict[str, Any]     # Run context, thresholds, etc.
    actor: str                  # Who/what decided
    timestamp: str              # ISO 8601
    
    def get_beliefs(self, store: GraphStore) -> List[Belief]: ...
```

### 6. Override
```python
@dataclass(frozen=True)
class Override:
    """
    Human intervention that contradicts system recommendation.
    
    All overrides are scoped, authorized, and time-bounded.
    """
    override_id: str            # Unique identifier
    original_decision: str      # Decision being overridden
    override_decision: str      # New decision
    actor: str                  # Who authorized
    authority_scope: str        # What they can override
    rationale: str              # Why override
    expires_at: str             # ISO 8601 (REQUIRED - no permanent overrides)
    created_at: str             # ISO 8601
    
    def is_expired(self, now: datetime) -> bool: ...
```

---

## REQUIRED QUERY CAPABILITIES (MVP)

### Q1: Why is this believed to be true?
```
Query: truthctl spine why <assertion-id>
Response: Lineage graph showing:
  - Root evidence
  - Transformations applied
  - Confidence computation
  - Assumptions made
```

### Q2: What evidence supports or weakens it?
```
Query: truthctl spine evidence <assertion-id> [--strength supporting|weakening]
Response: List of evidence with:
  - Evidence content (by hash)
  - Relationship type (direct, derived, inferred)
  - Staleness status
```

### Q3: When and why did this belief change?
```
Query: truthctl spine history <assertion-id>
Response: Timeline of belief versions:
  - Version 1: confidence=0.95 at T1 (initial evidence)
  - Version 2: confidence=0.72 at T2 (stale evidence)
  - Version 3: confidence=0.89 at T3 (new evidence)
```

### Q4: Which meaning version applies?
```
Query: truthctl spine meaning <concept> [--at <timestamp>]
Response: MeaningVersion with:
  - Current definition
  - Version history
  - Compatibility warnings (if multiple versions in use)
```

### Q5: Who overrode this, when, and with what scope?
```
Query: truthctl spine override <decision-id>
Response: Override record with:
  - Actor and authority
  - Scope of override
  - Expiry status
  - Rationale
```

### Q6: What assumptions does this depend on?
```
Query: truthctl spine dependencies <assertion-id> [--recursive]
Response: Dependency graph of:
  - Upstream beliefs
  - Evidence sources
  - Semantic definitions
```

### Q7: What would invalidate this belief?
```
Query: truthctl spine invalidate <assertion-id>
Response: Counter-evidence patterns:
  - Evidence types that would contradict
  - Semantic version incompatibilities
  - Dependency failures
```

---

## STORAGE MODEL

### Physical Storage
```
.truthcore/
├── spine/
│   ├── assertions/           # Content-addressed assertion files
│   │   └── <hash_prefix>/
│   │       └── <full_hash>.json
│   ├── evidence/             # Content-addressed evidence files
│   │   └── <hash_prefix>/
│   │       └── <full_hash>.json
│   ├── beliefs/              # Versioned belief records
│   │   └── <assertion_id>/
│   │       ├── v001.json
│   │       ├── v002.json
│   │       └── current.json  # Symlink to latest
│   ├── decisions/            # Decision records
│   │   └── <timestamp>/
│   │       └── <decision_id>.json
│   ├── overrides/            # Override records
│   │   └── <timestamp>/
│   │       └── <override_id>.json
│   ├── meanings/             # Meaning version registry
│   │   └── <meaning_id>/
│   │       ├── v1.0.0.json
│   │       ├── v2.0.0.json
│   │       └── current.json
│   └── contradictions/       # Detected contradictions
│       └── <detection_timestamp>.json
```

### Index Structure
```
.truthcore/
├── spine/
│   ├── indices/
│   │   ├── by_timestamp.json      # Time-series index
│   │   ├── by_source.json         # Source → assertions
│   │   ├── by_claim_type.json     # Type → assertions
│   │   ├── contradictions.json    # Active contradictions
│   │   └── meaning_registry.json  # Concept → versions
```

### Data Retention
- **Raw assertions:** Permanent (content-addressed, deduplicated)
- **Belief versions:** Keep all versions (append-only)
- **Evidence:** Configurable TTL (default: 90 days)
- **Contradictions:** Permanent with resolution status
- **Decisions:** Permanent (provenance requirement)
- **Overrides:** Permanent (authority tracking)

---

## REPLAY AND DETERMINISM

### Replay Capability
```python
class SpineReplay:
    """
    Deterministic replay of belief formation.
    
    Given the same evidence and assertions, produces
    identical belief confidence scores.
    """
    
    def replay_assertion(
        self,
        assertion_id: str,
        up_to_version: Optional[int] = None
    ) -> List[Belief]:
        """
        Replay belief formation for an assertion.
        
        Returns belief history deterministically.
        """
        ...
    
    def simulate_contrafactual(
        self,
        assertion_id: str,
        hypothetical_evidence: List[Evidence]
    ) -> Belief:
        """
        What would we believe if evidence were different?
        
        Does not modify stored beliefs. Returns hypothetical.
        """
        ...
```

### Determinism Guarantees
- Same evidence → Same assertion hash
- Same assertions → Same confidence (at same time)
- Same inputs → Same lineage
- Timestamps normalized to UTC microseconds
- JSON canonicalized (sorted keys)

---

## INTEGRATION CONTRACT

### How Systems Use TruthCore

#### Pattern: Consultative Query
```python
# System makes its own decision
decision = my_engine.evaluate(inputs)

# System consults TruthCore for explanation
if truthcore_spine.is_enabled():
    beliefs = truthcore_spine.query.beliefs_for(
        assertion_ids=decision.assertions
    )
    decision.explanation = beliefs.to_explanation()

# Decision proceeds with or without TruthCore input
return decision
```

#### Pattern: Decision Recording
```python
# System records decision after making it
if truthcore_spine.is_enabled():
    truthcore_spine.record.decision(
        Decision(
            action=decision.verdict,
            belief_ids=decision.assertions,
            actor="my_engine",
            timestamp=utc_now()
        )
    )

# Recording is fire-and-forget; never blocks
```

### API Surface

#### Internal API (Python)
```python
from truthcore.spine import SpineClient

spine = SpineClient()

# Queries
lineage = spine.query.lineage(assertion_id="abc123")
beliefs = spine.query.history(assertion_id="abc123")
evidence = spine.query.evidence(assertion_id="abc123")
meaning = spine.query.meaning(concept="deployment_ready", at="2026-02-01")

# Recording (fire-and-forget)
spine.record.assertion(assertion)
spine.record.decision(decision)
spine.record.override(override)
```

#### CLI Interface
```bash
# Query commands
truthctl spine why <assertion-id> [--format json|md]
truthctl spine lineage <assertion-id> [--depth N]
truthctl spine history <assertion-id> [--since YYYY-MM-DD]
truthctl spine evidence <assertion-id> [--type raw|derived]
truthctl spine meaning <concept> [--version X.Y.Z]
truthctl spine contradicts [--severity blocker|high|medium]
truthctl spine dependencies <assertion-id> [--recursive]
truthctl spine invalidate <assertion-id> [--format json]

# Admin commands
truthctl spine stats                    # Spine statistics
truthctl spine health                   # Health check
truthctl spine compact                  # Remove expired evidence
```

#### REST API (Server Mode)
```
GET /spine/v1/assertion/{id}/lineage
GET /spine/v1/assertion/{id}/history
GET /spine/v1/assertion/{id}/evidence
GET /spine/v1/meaning/{concept}?at={timestamp}
GET /spine/v1/contradictions?severity={level}
POST /spine/v1/query/dependencies  { assertion_ids: [...] }
```

---

## FEATURE FLAG STRATEGY

### Flag Hierarchy
```yaml
# truthcore.config.yaml
spine:
  enabled: false              # Master switch (default: OFF)
  
  # Component flags
  assertions: false           # Accept assertions
  beliefs: false              # Form/update beliefs
  contradictions: false       # Detect contradictions
  decisions: false            # Record decisions
  overrides: false            # Track overrides
  meanings: false             # Version semantic meanings
  
  # Query flags
  queries_enabled: false      # Enable query API
  query_depth_max: 10         # Max lineage depth
  
  # Ingestion flags
  ingest_enabled: false       # Accept telemetry
  ingest_queue_size: 10000    # Bounded queue
  ingest_async: true          # Non-blocking
  
  # Storage
  storage_path: ".truthcore/spine"
  evidence_ttl_days: 90
```

### Activation Levels

**Level 0: Dormant (Default)**
```yaml
spine:
  enabled: false
```
- Zero overhead
- No storage allocation
- Code paths not executed

**Level 1: Observe-Only**
```yaml
spine:
  enabled: true
  assertions: true
  ingest_enabled: true
  queries_enabled: false    # No query API yet
```
- Records telemetry
- Forms assertions
- No beliefs computed
- Queries not available

**Level 2: Belief Formation**
```yaml
spine:
  enabled: true
  assertions: true
  beliefs: true
  contradictions: true
  ingest_enabled: true
  queries_enabled: true     # Queries now available
```
- Full belief engine
- Contradiction detection
- Query API enabled
- Still read-only

**Level 3: Decision Recording**
```yaml
spine:
  enabled: true
  assertions: true
  beliefs: true
  decisions: true
  overrides: true
  ingest_enabled: true
  queries_enabled: true
```
- Records decisions
- Tracks overrides
- Full query capability
- Still never enforces

---

## RESPONSIBILITY BOUNDARIES

### TruthCore Spine Is Responsible For:
1. **Storing** assertions with evidence linkage
2. **Computing** belief confidence (with decay)
3. **Versioning** beliefs and semantic meanings
4. **Detecting** contradictions (not resolving)
5. **Recording** decisions and overrides
6. **Answering** explanation queries
7. **Maintaining** deterministic replay capability

### TruthCore Spine Is NOT Responsible For:
1. **Enforcing** any policy or constraint
2. **Blocking** any operation
3. **Recommending** actions (unless explicitly queried)
4. **Resolving** contradictions it detects
5. **Modifying** upstream system behavior
6. **Making** go/no-go decisions
7. **Scoring** or ranking systems
8. **Alerting** or notifying (unless future extension)

### Upstream Systems Remain Responsible For:
1. **Deciding** what actions to take
2. **Enforcing** their own policies
3. **Choosing** whether to consult TruthCore
4. **Acting** on TruthCore explanations (or not)
5. **Handling** their own failures

---

## RISKS AND NON-GOALS

### Explicit Risks

#### Risk 1: Nobody Uses It
**Scenario:** Engineers don't find value in querying TruthCore.
**Mitigation:** 
- Integrate into existing dashboard
- Provide compelling use cases in docs
- Make CLI queries fast and useful
**Acceptance:** If adoption < 10% after 30 days, reconsider approach.

#### Risk 2: Performance Overhead
**Scenario:** Belief computation slows down ingestion.
**Mitigation:**
- Async processing
- Bounded queues
- Configurable sampling
**Measurement:** Target < 100ms per assertion when enabled.

#### Risk 3: Storage Explosion
**Scenario:** Content-addressed storage grows unbounded.
**Mitigation:**
- Evidence TTL
- Deduplication
- Optional compaction
**Measurement:** Target < 1GB per 10K assertions.

#### Risk 4: Privacy/Security Leakage
**Scenario:** Assertions contain sensitive data.
**Mitigation:**
- Hash-based evidence references
- Configurable redaction
- No raw content in queries (by default)
**Measurement:** Audit all stored fields for PII/sensitive data.

#### Risk 5: Contradiction Overload
**Scenario:** Too many contradictions detected, overwhelming users.
**Mitigation:**
- Severity filtering
- Noise reduction heuristics
- Deduplication
**Measurement:** Target < 5 contradictions per 1000 assertions.

### Explicit Non-Goals

1. **Not a Data Lake** - TruthCore stores structured assertions, not raw logs
2. **Not a Time-Series DB** - History tracked per-assertion, not global metrics
3. **Not an Alerting System** - No notifications (unless future extension)
4. **Not a Policy Engine** - No rule enforcement (see existing policy module)
5. **Not a Recommendation Engine** - No action suggestions (unless queried)
6. **Not a Monitoring Dashboard** - Visualization consumes queries, not built-in
7. **Not a Search Engine** - Full-text search deferred (use hashes/IDs)

---

## SUCCESS CRITERIA

### Technical Criteria (Required)
- [ ] All 7 MVP query types functional
- [ ] Deterministic replay verified (100% match)
- [ ] < 1ms overhead when disabled
- [ ] < 100ms per assertion when enabled
- [ ] Zero exceptions propagate upward
- [ ] All existing tests pass
- [ ] Storage grows < 1GB per 10K assertions

### Adoption Criteria (Critical)
- [ ] Engineers voluntarily run `truthctl spine why` queries
- [ ] Dashboard queries TruthCore for lineage visualization
- [ ] Documentation shows real query examples
- [ ] At least 3 distinct use cases documented

### Failure Modes (Acceptable)
- [ ] Query returns "unknown" for missing data
- [ ] Graceful degradation if evidence TTL'd
- [ ] Empty result set for invalid IDs
- [ ] 404 for non-existent assertions

### Success Metrics
| Metric | Target | Measurement |
|--------|--------|-------------|
| Query usage | > 100 queries/week | CLI/API logs |
| Adoption rate | > 30% of engineers | Survey + logs |
| Performance | < 100ms p99 | Timing middleware |
| Storage growth | < 100MB/day | Disk monitoring |
| Error rate | < 0.1% | Error logs |
| Contradiction signal | < 5% of assertions | Contradiction index |

---

## IMPLEMENTATION ROADMAP

### Phase 0: Foundation (Week 1)
**Goal:** Core primitives and storage

**Deliverables:**
- [ ] Assertion, Evidence, Belief, MeaningVersion, Decision dataclasses
- [ ] Content-addressed storage layer
- [ ] Deterministic JSON serialization
- [ ] Unit tests for all primitives

**Acceptance:**
- All primitives serialize/deserialize correctly
- Content hashes are deterministic
- Zero dependencies on external systems

### Phase 1: Graph & Belief Engine (Week 2)
**Goal:** Assertion graph and belief computation

**Deliverables:**
- [ ] DAG storage with lineage tracking
- [ ] Belief engine with confidence decay
- [ ] Contradiction detection (detection only)
- [ ] Version history management

**Acceptance:**
- Lineage queries return complete chains
- Belief decay computed correctly
- Contradictions detected (not resolved)

### Phase 2: Ingestion Bridge (Week 3)
**Goal:** Connect to Silent Instrumentation

**Deliverables:**
- [ ] Signal transformation layer
- [ ] Async ingestion queue
- [ ] Deduplication pipeline
- [ ] Error handling (drop, don't block)

**Acceptance:**
- Signals ingested without blocking
- Duplicates eliminated via hashing
- Failures contained internally

### Phase 3: Query Surface (Week 4)
**Goal:** Implement all 7 MVP query types

**Deliverables:**
- [ ] Why query (lineage)
- [ ] Evidence query
- [ ] History query
- [ ] Meaning query
- [ ] Override query
- [ ] Dependencies query
- [ ] Invalidation query

**Acceptance:**
- All query types return correct data
- Query performance < 100ms p99
- Results are deterministic

### Phase 4: CLI & API (Week 5)
**Goal:** Human interfaces

**Deliverables:**
- [ ] `truthctl spine` commands
- [ ] REST API endpoints
- [ ] Query result formatting (JSON, Markdown)
- [ ] Documentation and examples

**Acceptance:**
- CLI usable without reading source
- API documented
- Examples show real use cases

### Phase 5: Integration & Hardening (Week 6)
**Goal:** Production readiness

**Deliverables:**
- [ ] Dashboard integration
- [ ] Feature flag testing
- [ ] Performance optimization
- [ ] Documentation complete
- [ ] Runbook created

**Acceptance:**
- Zero performance degradation when disabled
- All tests pass
- Documentation answers "why should I use this?"

---

## CONCLUSION

TruthCore earns legitimacy only if engineers and operators voluntarily consult it.

This milestone implements a read-only truth spine that:
- **Records** what the system believes and why
- **Remembers** how beliefs have changed
- **Explains** its reasoning when asked
- **Detects** contradictions without resolving them
- **Degrades** gracefully and silently
- **Removes** cleanly with zero side effects

**The success criterion is simple:** If no one asks TruthCore questions, this milestone has failed.

---

**Document Status:** Complete  
**Next Step:** Phase 0 Implementation  
**Decision:** Proceed with implementation  
**Risk Level:** Low (observe-only, feature-flagged, removable)  
**Last Updated:** 2026-02-01  
