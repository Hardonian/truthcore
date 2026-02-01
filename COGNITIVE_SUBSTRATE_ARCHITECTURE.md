# Shared Cognitive Substrate Architecture
**Design Document v1.0**
**Created:** 2026-02-01
**Status:** Design Phase — Not Yet Implemented

---

## Executive Summary

The **Shared Cognitive Substrate** is a foundational engine-level architecture that introduces truth representation, belief formation, semantic versioning, decision governance, and economic reasoning as first-class primitives. It is designed to be adopted across multiple applications (Settler, ReadyLayer, Keys, AIAS) **without forcing activation**.

**Design Philosophy:** This is a spinal cord, not a brain. It provides infrastructure for reasoning, not reasoning itself.

**Key Characteristics:**
- **Opt-in by default:** All features are feature-flagged; default mode is observe-only
- **Zero-overhead when disabled:** No runtime cost for inactive features
- **Non-breaking:** Existing builds, flows, and contracts remain unchanged
- **Deterministic:** All operations support replay and inspection
- **Signal-based:** Emits graded signals and reports, never hard failures

---

## 1. CORE ARCHITECTURE

### 1.1 Module Structure

```
truthcore/
├── src/truthcore/
│   ├── substrate/                    # NEW: Cognitive Substrate
│   │   ├── __init__.py
│   │   ├── primitives/               # Core abstractions
│   │   │   ├── assertion.py          # Claims and evidence
│   │   │   ├── belief.py             # Versioned beliefs with confidence
│   │   │   ├── meaning.py            # Semantic versioning of meaning
│   │   │   ├── decision.py           # Decision modeling with governance
│   │   │   ├── policy.py             # Policy constraints (extends existing)
│   │   │   └── economic.py           # Cost/risk/value signals
│   │   ├── graph/                    # Assertion graph engine
│   │   │   ├── assertion_graph.py    # DAG of assertions and evidence
│   │   │   ├── belief_engine.py      # Belief formation and decay
│   │   │   ├── contradiction.py      # Conflict detection
│   │   │   └── lineage.py            # Provenance tracking
│   │   ├── governance/               # Decision governance
│   │   │   ├── human_override.py     # Scoped human decisions
│   │   │   ├── authority.py          # Authorization and expiry
│   │   │   └── reconciliation.py     # System vs. human alignment
│   │   ├── economic/                 # Economic reasoning
│   │   │   ├── signals.py            # Cost/risk/value primitives
│   │   │   ├── invariants.py         # Economic constraints
│   │   │   └── budget.py             # Budget tracking (observe-only)
│   │   ├── learning/                 # Organizational pattern detection
│   │   │   ├── pattern_detector.py   # Usage pattern recognition
│   │   │   ├── stage_gate.py         # Lifecycle stage detection
│   │   │   └── mismatch.py           # Tooling vs. stage alignment
│   │   ├── telemetry/                # Observability layer
│   │   │   ├── metrics.py            # Cognitive operation metrics
│   │   │   ├── reports.py            # Human-readable summaries
│   │   │   └── replay.py             # Deterministic replay support
│   │   ├── config/                   # Configuration and flags
│   │   │   ├── flags.py              # Feature flags
│   │   │   ├── substrate_config.py   # Substrate parameters
│   │   │   └── profiles.py           # Per-app profiles
│   │   └── integrations/             # Bridge to existing engines
│   │       ├── verdict_bridge.py     # Connect to verdict system
│   │       ├── policy_bridge.py      # Extend policy engine
│   │       └── manifest_bridge.py    # Extend provenance manifests
│   ├── engines/                      # EXISTING: No changes
│   ├── policy/                       # EXISTING: Extended by substrate
│   ├── verdict/                      # EXISTING: Bridged by substrate
│   └── ...                           # EXISTING: Unchanged
```

### 1.2 Design Principles

1. **Composability:** All primitives are independent and composable
2. **Inspectability:** Everything is serializable to JSON/YAML
3. **Versionability:** All primitives carry version metadata
4. **Immutability:** Core primitives are frozen dataclasses
5. **Observability:** All state changes emit telemetry
6. **Non-enforcement:** Default behavior is to observe and report, not block

---

## 2. CORE PRIMITIVES

### 2.1 Assertion

**Definition:** A claim the system believes to be true, backed by evidence.

```python
@dataclass(frozen=True)
class Assertion:
    """
    A claim about the world that the system holds.

    Assertions are content-addressed and immutable. They reference
    evidence that supports or weakens them and can be chained into
    a directed acyclic graph (DAG).
    """
    assertion_id: str              # Content hash of claim + evidence
    claim: str                     # What is being asserted
    evidence_ids: list[str]        # References to Evidence objects
    transformation: str | None     # How evidence was transformed into claim
    source: str                    # Origin (engine, human, external)
    timestamp: str                 # ISO 8601
    metadata: dict[str, Any]       # Extensible context

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict) -> "Assertion": ...
```

**Responsibilities:**
- Represent atomic claims
- Link to supporting/weakening evidence
- Support content-addressed caching
- Enable deterministic replay

**Non-responsibilities:**
- Does NOT compute confidence (that's Belief)
- Does NOT resolve contradictions (that's graph layer)
- Does NOT enforce truth (observe only)

---

### 2.2 Evidence

**Definition:** Input data that supports or weakens assertions.

```python
@dataclass(frozen=True)
class Evidence:
    """
    Raw or derived data that influences belief in assertions.

    Evidence is versioned and content-addressed. It can be raw input
    (file contents, API responses) or derived (analysis results).
    """
    evidence_id: str               # Content hash
    evidence_type: EvidenceType    # RAW, DERIVED, HUMAN_INPUT, EXTERNAL
    content_hash: str              # Hash of actual data
    source: str                    # Where it came from
    timestamp: str                 # When captured
    validity_period: int | None    # Seconds until stale (None = forever)
    metadata: dict[str, Any]       # Schema version, provenance, etc.

    def is_stale(self, current_time: datetime) -> bool: ...
```

**Evidence Types:**
```python
class EvidenceType(Enum):
    RAW = "raw"                    # Direct input (file, API response)
    DERIVED = "derived"            # Computed from other evidence
    HUMAN_INPUT = "human_input"    # Explicit human assertion
    EXTERNAL = "external"          # Third-party system
```

---

### 2.3 Belief

**Definition:** An assertion with confidence, temporal validity, and decay characteristics.

```python
@dataclass
class Belief:
    """
    A versioned belief in an assertion with confidence scoring.

    Beliefs are NOT frozen because confidence decays over time.
    Each update creates a new version in the belief history.
    """
    belief_id: str                 # Unique identifier
    assertion_id: str              # What we believe
    confidence: float              # [0.0, 1.0]
    version: int                   # Monotonically increasing
    created_at: str                # ISO 8601
    updated_at: str                # ISO 8601
    decay_rate: float              # Confidence loss per day (0.0 = no decay)
    validity_until: str | None     # Explicit expiry (ISO 8601)
    upstream_dependencies: list[str]  # Assertion/belief IDs this depends on
    metadata: dict[str, Any]

    def current_confidence(self, now: datetime) -> float:
        """Compute confidence with time-based decay."""
        ...

    def is_valid(self, now: datetime) -> bool:
        """Check if belief is still within validity period."""
        ...

    def to_dict(self) -> dict[str, Any]: ...
```

**Confidence Model:**
- **1.0:** Provable truth (cryptographic, mathematical)
- **0.9-0.99:** Strong evidence, low uncertainty
- **0.7-0.89:** Moderate confidence
- **0.5-0.69:** Weak confidence
- **0.0-0.49:** Low confidence or contradicted
- **0.0:** Disproven or expired

**Decay Characteristics:**
- Static facts: `decay_rate = 0.0`
- Volatile data: `decay_rate > 0.0`
- Upstream changes propagate decay downstream

---

### 2.4 MeaningVersion

**Definition:** Machine-readable definition of what a concept, metric, or field *means*.

```python
@dataclass(frozen=True)
class MeaningVersion:
    """
    Semantic versioning for the *meaning* of concepts, separate from schema versions.

    When the interpretation of "deployment success" or "coverage" changes,
    this captures that semantic drift explicitly.
    """
    meaning_id: str                # Semantic identifier (e.g., "deployment.success")
    version: str                   # Semantic version (e.g., "2.1.0")
    definition: str                # Human-readable definition
    computation: str | None        # How it's computed (formula, algorithm)
    examples: list[dict[str, Any]] # Exemplars of this meaning
    deprecated: bool               # True if superseded
    superseded_by: str | None      # New meaning_id if deprecated
    valid_from: str                # ISO 8601
    valid_until: str | None        # ISO 8601 or None
    metadata: dict[str, Any]

    def is_compatible_with(self, other: "MeaningVersion") -> bool:
        """Check if two meanings are semantically compatible."""
        ...
```

**Use Cases:**
- **Metric drift:** "Code coverage" changes from line-based to branch-based
- **Policy evolution:** "High severity" threshold changes from 50 to 75 points
- **UI copy changes:** "Deployment ready" now means "passed AND approved"
- **Cross-system alignment:** Ensure Settler and Keys interpret "readiness" identically

**Detection:**
- Compare `meaning_id` versions across artifacts
- Warn when old and new meanings coexist
- Flag when computation changes without version bump

---

### 2.5 Decision

**Definition:** An action taken by the system or a human, with governance metadata.

```python
@dataclass
class Decision:
    """
    An explicit choice made by the system or a human.

    Decisions reference the beliefs and policies that influenced them
    and can be overridden by humans within defined scopes.
    """
    decision_id: str               # Content hash
    decision_type: DecisionType    # SYSTEM, HUMAN_OVERRIDE, POLICY_ENFORCED
    action: str                    # What was decided (e.g., "ship", "block", "approve")
    rationale: list[str]           # Why this decision was made
    belief_ids: list[str]          # Beliefs that influenced this
    policy_ids: list[str]          # Policies that constrained this
    authority: Authority | None    # Who authorized (for human overrides)
    scope: str | None              # What this decision applies to
    expires_at: str | None         # When override expires
    created_at: str                # ISO 8601
    metadata: dict[str, Any]

    def is_expired(self, now: datetime) -> bool: ...
    def conflicts_with(self, other: "Decision") -> bool: ...
```

**Decision Types:**
```python
class DecisionType(Enum):
    SYSTEM = "system"              # Automated decision
    HUMAN_OVERRIDE = "human_override"  # Human intervention
    POLICY_ENFORCED = "policy_enforced"  # Hard policy constraint
    ECONOMIC = "economic"          # Cost/budget-driven
```

**Authority Model:**
```python
@dataclass(frozen=True)
class Authority:
    """Who can make this decision."""
    actor: str                     # User, team, or role
    scope: str                     # What they can decide on
    valid_until: str | None        # Expiry of authority
    requires_renewal: bool         # Must be explicitly renewed
```

---

### 2.6 Policy (Extension)

**Definition:** Constraints governing decisions (extends existing `truthcore.policy`).

```python
@dataclass
class CognitivePolicy:
    """
    Policy rules for the cognitive substrate.

    Extends the existing PolicyPack model to include belief, economic,
    and governance constraints.
    """
    policy_id: str
    policy_type: PolicyType        # BELIEF, ECONOMIC, GOVERNANCE, SEMANTIC
    rule: dict[str, Any]           # DSL rule (reuses InvariantDSL)
    enforcement: EnforcementMode   # OBSERVE, WARN, BLOCK
    applies_to: str                # Scope (engine, org, user)
    priority: int                  # For conflict resolution
    metadata: dict[str, Any]

class PolicyType(Enum):
    BELIEF = "belief"              # Confidence thresholds
    ECONOMIC = "economic"          # Cost/budget limits
    GOVERNANCE = "governance"      # Authority requirements
    SEMANTIC = "semantic"          # Meaning version compatibility
```

**Example Rules:**
```yaml
# Belief policy: Don't ship on low confidence
- id: "belief.min_confidence"
  type: "belief"
  rule:
    operator: ">="
    left: "belief.ship_ready.confidence"
    right: 0.8
  enforcement: "warn"

# Economic policy: Warn on high cost
- id: "economic.cost_ceiling"
  type: "economic"
  rule:
    operator: "<="
    left: "decision.cost"
    right: 1000
  enforcement: "observe"

# Governance policy: Human override requires authority
- id: "governance.override_authority"
  type: "governance"
  rule:
    requires: "authority.role in ['lead', 'admin']"
  enforcement: "block"
```

---

### 2.7 EconomicSignal

**Definition:** Cost, risk, or value indicators that influence decisions.

```python
@dataclass
class EconomicSignal:
    """
    Financial or resource-based signal that affects decision-making.

    Economic signals are first-class inputs to the belief system,
    not just billing metadata.
    """
    signal_id: str
    signal_type: EconomicSignalType  # COST, RISK, VALUE, BUDGET_PRESSURE
    amount: float                  # Numeric value
    unit: str                      # Units (USD, tokens, CPU-seconds, etc.)
    source: str                    # Where signal came from
    applies_to: str                # What decision/action this affects
    confidence: float              # How certain is this signal
    timestamp: str                 # ISO 8601
    metadata: dict[str, Any]

    def influence_weight(self) -> float:
        """How much should this signal influence decisions."""
        ...

class EconomicSignalType(Enum):
    COST = "cost"                  # Direct expenditure
    RISK = "risk"                  # Potential loss
    VALUE = "value"                # Expected benefit
    BUDGET_PRESSURE = "budget_pressure"  # Constraint urgency
```

**Integration with Beliefs:**
- Economic signals become evidence for economic-aware beliefs
- High cost → lower confidence in "should proceed" belief
- Budget pressure → influences decision urgency
- Risk signals → decay confidence faster

**Observe-Only by Default:**
- Tracked and reported
- Never silently overrides truth
- Surfaced in decision rationale

---

## 3. GRAPH LAYER — ASSERTION GRAPH & BELIEF ENGINE

### 3.1 Assertion Graph

**Purpose:** Maintain a directed acyclic graph (DAG) of assertions and their evidence.

```python
class AssertionGraph:
    """
    DAG of assertions linked by evidence and transformations.

    Supports:
    - Adding assertions and evidence
    - Querying lineage (upstream/downstream)
    - Detecting cycles (should never happen)
    - Content-addressed storage
    """

    def add_assertion(self, assertion: Assertion) -> None: ...
    def add_evidence(self, evidence: Evidence) -> None: ...
    def get_lineage(self, assertion_id: str) -> AssertionLineage: ...
    def find_contradictions(self) -> list[Contradiction]: ...
    def to_dict(self) -> dict[str, Any]: ...

@dataclass
class AssertionLineage:
    """Provenance chain for an assertion."""
    root_assertion: Assertion
    upstream_assertions: list[Assertion]
    evidence_chain: list[Evidence]
    transformations: list[str]
```

**Operations:**
- **add_assertion:** Insert new claim into graph
- **add_evidence:** Link evidence to assertions
- **get_lineage:** Trace provenance back to root evidence
- **find_contradictions:** Detect conflicting assertions (see §3.3)

**Storage:**
- Content-addressed via existing `truthcore.cache`
- Supports deterministic replay
- Serializes to JSON for inspection

---

### 3.2 Belief Engine

**Purpose:** Form and update beliefs based on assertion graph and evidence.

```python
class BeliefEngine:
    """
    Computes and updates beliefs based on assertions and evidence.

    Responsibilities:
    - Form initial beliefs from assertions
    - Update confidence when evidence changes
    - Propagate decay through dependency chains
    - Version belief history
    """

    def form_belief(
        self,
        assertion: Assertion,
        initial_confidence: float,
        decay_rate: float = 0.0
    ) -> Belief: ...

    def update_belief(
        self,
        belief_id: str,
        new_evidence: Evidence
    ) -> Belief: ...

    def propagate_decay(
        self,
        upstream_belief_id: str
    ) -> list[Belief]:
        """When an upstream belief decays, update downstream."""
        ...

    def compute_confidence(
        self,
        assertion: Assertion,
        evidence_quality: float,
        time_delta: timedelta
    ) -> float: ...
```

**Confidence Computation:**
```python
confidence = base_confidence * evidence_weight * exp(-decay_rate * time_delta)
```

Where:
- **base_confidence:** Initial confidence from assertion strength
- **evidence_weight:** Quality/quantity of supporting evidence
- **decay_rate:** Time-based degradation
- **time_delta:** Time since belief created

**Decay Propagation:**
- When upstream belief confidence drops below threshold → propagate downstream
- Graph traversal ensures all dependent beliefs are updated
- Creates new belief versions (immutable history)

---

### 3.3 Contradiction Detection

**Purpose:** Identify conflicting assertions without auto-resolving.

```python
@dataclass
class Contradiction:
    """
    Detected conflict between assertions or beliefs.

    Contradictions are surfaced as signals, NOT resolved automatically.
    """
    contradiction_id: str
    contradiction_type: ContradictionType
    conflicting_items: list[str]   # Assertion/belief/decision IDs
    severity: Severity             # BLOCKER, HIGH, MEDIUM, LOW
    explanation: str               # Why these conflict
    detected_at: str               # ISO 8601
    resolution_status: ResolutionStatus
    metadata: dict[str, Any]

class ContradictionType(Enum):
    ASSERTION_CONFLICT = "assertion_conflict"      # A and ¬A both asserted
    BELIEF_DIVERGENCE = "belief_divergence"        # System vs. human beliefs differ
    POLICY_CONFLICT = "policy_conflict"            # Mutually exclusive policies
    SEMANTIC_DRIFT = "semantic_drift"              # Meaning version mismatch
    ECONOMIC_VIOLATION = "economic_violation"      # Cost exceeds constraints

class ResolutionStatus(Enum):
    UNRESOLVED = "unresolved"
    HUMAN_OVERRIDE = "human_override"
    POLICY_RULED = "policy_ruled"
    IGNORED = "ignored"
```

**Detection Strategies:**
```python
class ContradictionDetector:
    def detect_assertion_conflicts(
        self,
        graph: AssertionGraph
    ) -> list[Contradiction]:
        """Find A and ¬A in graph."""
        ...

    def detect_belief_divergence(
        self,
        system_belief: Belief,
        human_decision: Decision
    ) -> Contradiction | None:
        """Find system vs. human disagreements."""
        ...

    def detect_policy_conflicts(
        self,
        policies: list[CognitivePolicy]
    ) -> list[Contradiction]:
        """Find mutually exclusive policy rules."""
        ...

    def detect_semantic_drift(
        self,
        meanings: list[MeaningVersion]
    ) -> list[Contradiction]:
        """Find incompatible meaning versions in use."""
        ...
```

**Non-Resolution:**
- Contradictions are **reported**, not auto-resolved
- Surfaced in telemetry and reports
- Human or policy decides resolution
- Resolution is tracked as a Decision with governance

---

## 4. GOVERNANCE LAYER — HUMAN-IN-THE-LOOP

### 4.1 Human Override Model

**Purpose:** Allow humans to override system decisions within defined scopes and authority.

```python
@dataclass
class HumanOverride:
    """
    Explicit human intervention in system decision-making.

    All overrides are scoped, authorized, expiring, and auditable.
    """
    override_id: str
    original_decision: Decision    # What system decided
    override_decision: Decision    # What human decided
    authority: Authority           # Who authorized
    scope: OverrideScope           # What this applies to
    rationale: str                 # Why override was made
    expires_at: str                # ISO 8601 (REQUIRED)
    requires_renewal: bool         # Must be explicitly renewed
    renewal_history: list[str]     # Decision IDs of renewals
    created_at: str
    metadata: dict[str, Any]

    def is_expired(self, now: datetime) -> bool: ...
    def is_renewable(self) -> bool: ...

@dataclass(frozen=True)
class OverrideScope:
    """What the override applies to."""
    scope_type: ScopeType          # SINGLE_DECISION, RULE, ORG, TIME_WINDOW
    target: str                    # Specific identifier
    constraints: dict[str, Any]    # Additional limits

class ScopeType(Enum):
    SINGLE_DECISION = "single_decision"  # One-off override
    RULE = "rule"                  # Override policy rule
    ORG = "org"                    # Org-wide override
    TIME_WINDOW = "time_window"    # Temporary override
```

**Governance Rules:**
1. **No permanent overrides:** All have explicit expiry
2. **Authority required:** Must have valid Authority
3. **Scoped narrowly:** Broadest scope requires highest authority
4. **Auditable:** All overrides tracked in provenance
5. **Renewable:** Can be extended, but never automatic

---

### 4.2 Reconciliation

**Purpose:** Align system beliefs with human decisions and detect divergence.

```python
class ReconciliationEngine:
    """
    Reconciles system beliefs with human overrides.

    Does NOT enforce alignment, but surfaces divergence as signals.
    """

    def reconcile(
        self,
        system_belief: Belief,
        human_override: HumanOverride
    ) -> ReconciliationResult: ...

    def detect_divergence(
        self,
        beliefs: list[Belief],
        decisions: list[Decision]
    ) -> list[Divergence]: ...

@dataclass
class ReconciliationResult:
    """Result of reconciling system and human reasoning."""
    aligned: bool
    divergence_score: float        # [0.0, 1.0] - how far apart
    explanation: str
    suggested_actions: list[str]   # What could reduce divergence

@dataclass
class Divergence:
    """Detected mismatch between system and human reasoning."""
    divergence_type: DivergenceType
    system_belief_id: str
    human_decision_id: str
    magnitude: float               # How significant
    explanation: str
```

**Use Cases:**
- Human keeps overriding low-confidence beliefs → system should learn
- System high confidence contradicts human → flag for review
- Repeated divergence on same rule → policy may be wrong

---

## 5. ECONOMIC LAYER

### 5.1 Economic Signal Processing

**Purpose:** Track and surface economic signals without silent enforcement.

```python
class EconomicSignalProcessor:
    """
    Collects and processes cost/risk/value signals.

    OBSERVE-ONLY by default. Signals influence beliefs but don't block.
    """

    def record_signal(self, signal: EconomicSignal) -> None: ...

    def compute_total_cost(
        self,
        decision_id: str
    ) -> float:
        """Sum all cost signals for a decision."""
        ...

    def evaluate_budget_pressure(
        self,
        organization_id: str
    ) -> BudgetPressure: ...

    def influence_belief(
        self,
        belief: Belief,
        economic_signals: list[EconomicSignal]
    ) -> Belief:
        """Adjust belief confidence based on economic factors."""
        ...

@dataclass
class BudgetPressure:
    """How close to budget limits."""
    current_spend: float
    budget_limit: float | None     # None = no limit
    pressure_level: PressureLevel  # LOW, MEDIUM, HIGH, CRITICAL
    time_to_limit: timedelta | None
```

---

### 5.2 Economic Invariants

**Purpose:** Define economic constraints that should hold (but don't block by default).

```python
@dataclass
class EconomicInvariant:
    """
    Economic constraint that should be maintained.

    Violations are reported, not enforced (unless policy says otherwise).
    """
    invariant_id: str
    rule: dict[str, Any]           # DSL rule (e.g., "cost < 1000")
    enforcement: EnforcementMode   # OBSERVE, WARN, BLOCK
    applies_to: str
    metadata: dict[str, Any]

# Example invariants
COST_PER_DEPLOYMENT_MAX = EconomicInvariant(
    invariant_id="cost.deployment.max",
    rule={"operator": "<=", "left": "deployment.cost", "right": 100},
    enforcement=EnforcementMode.WARN,
    applies_to="org:*"
)

TOKEN_BUDGET_DAILY = EconomicInvariant(
    invariant_id="token.budget.daily",
    rule={"operator": "<=", "left": "daily_tokens", "right": 1_000_000},
    enforcement=EnforcementMode.OBSERVE,
    applies_to="org:*"
)
```

---

## 6. LEARNING LAYER — ORGANIZATIONAL PATTERN DETECTION

### 6.1 Pattern Detection (Observe-Only)

**Purpose:** Learn from usage patterns without enforcement.

```python
class PatternDetector:
    """
    Detects repeated user and organizational behaviors.

    OBSERVE-ONLY. Never enforces, only reports.
    """

    def detect_usage_patterns(
        self,
        organization_id: str,
        lookback_days: int = 30
    ) -> list[UsagePattern]: ...

    def detect_stage_gate(
        self,
        organization_id: str
    ) -> StageGate: ...

    def detect_tooling_mismatch(
        self,
        organization_id: str,
        current_usage: UsagePattern,
        current_stage: StageGate
    ) -> ToolingMismatch | None: ...

@dataclass
class UsagePattern:
    """Detected organizational behavior pattern."""
    pattern_type: PatternType
    frequency: str                 # "daily", "weekly", etc.
    confidence: float              # [0.0, 1.0]
    first_seen: str                # ISO 8601
    last_seen: str
    example_instances: list[str]   # Decision/event IDs
    metadata: dict[str, Any]

class PatternType(Enum):
    FREQUENT_OVERRIDE = "frequent_override"      # Often overrides same rule
    CONSISTENT_APPROVAL = "consistent_approval"  # Always approves X
    RISK_AVERSE = "risk_averse"                 # Avoids high-risk decisions
    COST_SENSITIVE = "cost_sensitive"           # Optimizes for cost
    VELOCITY_FOCUSED = "velocity_focused"       # Optimizes for speed
```

---

### 6.2 Stage-Gate Detection

**Purpose:** Identify where an organization is in its lifecycle.

```python
@dataclass
class StageGate:
    """
    Organizational lifecycle stage.

    Detected from usage patterns, not explicitly configured.
    """
    stage: Stage
    confidence: float              # How certain we are
    indicators: list[str]          # What signals led to this
    detected_at: str               # ISO 8601
    metadata: dict[str, Any]

class Stage(Enum):
    EARLY = "early"                # Small team, rapid iteration
    SCALING = "scaling"            # Growing team, more process
    MATURE = "mature"              # Large team, heavy governance

# Detection heuristics
EARLY_INDICATORS = [
    "few users (<10)",
    "high override rate",
    "low policy count",
    "fast iteration (daily deploys)"
]

SCALING_INDICATORS = [
    "growing team (10-50)",
    "increasing policy count",
    "more structured approvals",
    "moderate deploy frequency"
]

MATURE_INDICATORS = [
    "large team (>50)",
    "extensive policies",
    "formal governance",
    "slower, gated deploys"
]
```

---

### 6.3 Tooling Mismatch Detection

**Purpose:** Flag when current tooling doesn't match organizational stage.

```python
@dataclass
class ToolingMismatch:
    """
    Detected mismatch between stage and tooling.

    Example: Early-stage team with enterprise-level governance overhead.
    """
    mismatch_type: MismatchType
    current_stage: Stage
    current_tooling: str           # Description of current setup
    severity: Severity             # How problematic
    recommendation: str            # What to do
    detected_at: str
    metadata: dict[str, Any]

class MismatchType(Enum):
    OVER_ENGINEERED = "over_engineered"      # Too much process
    UNDER_GOVERNED = "under_governed"        # Too little process
    WRONG_FOCUS = "wrong_focus"              # Optimizing wrong thing
```

**Example Reports:**
```json
{
  "mismatch_type": "over_engineered",
  "current_stage": "early",
  "current_tooling": "120 active policies, manual approval gates",
  "severity": "MEDIUM",
  "recommendation": "Consider reducing policy count for faster iteration",
  "detected_at": "2026-02-01T12:00:00Z"
}
```

---

## 7. FEATURE FLAG STRATEGY

### 7.1 Flag Hierarchy

```python
class SubstrateFlags:
    """
    Feature flags for cognitive substrate.

    All flags default to observe-only or disabled.
    """

    # Master switch
    enabled: bool = False                  # Master on/off (default: OFF)

    # Layer-specific flags
    assertion_graph_enabled: bool = False  # Track assertions
    belief_engine_enabled: bool = False    # Form beliefs
    contradiction_detection: bool = False  # Detect conflicts
    human_governance: bool = False         # Track overrides
    economic_signals: bool = False         # Track cost/risk
    pattern_detection: bool = False        # Learn from usage

    # Enforcement modes (when enabled)
    enforcement_mode: EnforcementMode = EnforcementMode.OBSERVE

    # Telemetry
    telemetry_enabled: bool = True         # Always on (low overhead)
    telemetry_sampling_rate: float = 1.0   # Sample rate [0.0, 1.0]

    # Replay
    replay_enabled: bool = False           # Deterministic replay
    replay_storage_path: str | None = None

class EnforcementMode(Enum):
    OBSERVE = "observe"            # Track only, never block
    WARN = "warn"                  # Emit warnings
    BLOCK = "block"                # Hard enforcement (requires explicit opt-in)
```

### 7.2 Per-Application Profiles

```yaml
# profiles/settler.yaml
name: "Settler"
flags:
  enabled: true
  assertion_graph_enabled: true
  belief_engine_enabled: true
  contradiction_detection: true
  human_governance: false         # Not yet needed
  economic_signals: false         # Not yet needed
  pattern_detection: true         # Learn usage patterns
  enforcement_mode: "observe"     # Only observe
  telemetry_sampling_rate: 1.0    # Full telemetry

# profiles/keys.yaml
name: "Keys"
flags:
  enabled: false                  # Not activated yet
  telemetry_enabled: true         # But still observe
  telemetry_sampling_rate: 0.1    # Low sampling
```

### 7.3 Runtime Overhead When Disabled

**Overhead Budget:** <1ms per operation when flags are disabled.

**Implementation:**
```python
class SubstrateRuntime:
    """
    Zero-cost abstraction when disabled.

    All methods check flags before any work.
    """

    def __init__(self, flags: SubstrateFlags):
        self.flags = flags
        # Pre-compute flag combinations for fast checks
        self._any_enabled = (
            flags.assertion_graph_enabled or
            flags.belief_engine_enabled or
            # ... etc
        )

    def record_assertion(self, assertion: Assertion) -> None:
        if not self._any_enabled:
            return  # Immediate return, no allocation

        if not self.flags.assertion_graph_enabled:
            return

        # Actual work happens here
        ...

    def emit_telemetry(self, event: dict) -> None:
        # Telemetry has its own fast path
        if not self.flags.telemetry_enabled:
            return

        if random.random() > self.flags.telemetry_sampling_rate:
            return  # Sample out

        # Log event
        ...
```

---

## 8. INTERACTION FLOWS

### 8.1 Basic Assertion → Belief → Decision Flow

```
1. Engine produces Finding (existing truthcore)
   ↓
2. [SUBSTRATE] Finding → Assertion
   - Extract claim from finding
   - Link to evidence (file contents, scan results)
   - Add to assertion graph

3. [SUBSTRATE] Assertion → Belief
   - Compute initial confidence
   - Set decay rate based on evidence type
   - Version belief in history

4. [SUBSTRATE] Belief → Decision Input
   - Pass to existing Verdict system
   - Enrich VerdictResult with cognitive metadata

5. [SUBSTRATE] Decision → Provenance
   - Extend existing manifest with:
     - Assertion lineage
     - Belief confidence
     - Economic signals
     - Human overrides
```

**Code Example:**
```python
# Existing engine produces finding
finding = Finding(
    rule_id="secret.aws_key",
    severity=Severity.BLOCKER,
    message="AWS key detected",
    # ...
)

# Substrate bridge converts to assertion
if substrate.flags.assertion_graph_enabled:
    assertion = substrate.bridge.finding_to_assertion(finding)
    substrate.graph.add_assertion(assertion)

    # Form belief
    if substrate.flags.belief_engine_enabled:
        belief = substrate.belief_engine.form_belief(
            assertion=assertion,
            initial_confidence=0.95,  # High confidence for crypto match
            decay_rate=0.0            # Static fact
        )
        substrate.belief_store.save(belief)

# Existing verdict aggregation continues unchanged
verdict = verdict_aggregator.aggregate([finding])

# Substrate enriches provenance
if substrate.flags.enabled:
    manifest = substrate.bridge.enrich_manifest(
        base_manifest=existing_manifest,
        assertions=[assertion],
        beliefs=[belief],
        economic_signals=[]
    )
```

---

### 8.2 Human Override Flow

```
1. System produces VerdictResult = NO_SHIP
   ↓
2. Human decides to override and ship anyway
   ↓
3. [SUBSTRATE] Capture override as Decision
   - decision_type = HUMAN_OVERRIDE
   - authority = current_user
   - scope = this deployment only
   - expires_at = +7 days
   - rationale = "urgent hotfix, risk accepted"

4. [SUBSTRATE] Record divergence
   - system_belief = "should not ship" (confidence: 0.9)
   - human_decision = "ship" (authority: lead)
   - divergence_score = 0.9

5. [SUBSTRATE] Emit telemetry
   - Pattern: Frequent overrides on rule X
   - Report: "Consider adjusting rule threshold"

6. System ships (decision executed)

7. After 7 days, override expires
   - Next deployment uses system decision
   - Unless human renews override
```

---

### 8.3 Economic Signal Integration Flow

```
1. [APP] External cost tracking records token usage
   ↓
2. [SUBSTRATE] Record EconomicSignal
   - signal_type = COST
   - amount = 1500
   - unit = "USD"
   - applies_to = deployment_id

3. [SUBSTRATE] Influence belief confidence
   - Original belief: "should deploy" (confidence: 0.85)
   - Economic signal: cost exceeds budget
   - Adjusted belief: confidence → 0.70
   - Rationale: "High cost reduces confidence"

4. [SUBSTRATE] Decision reflects economic factor
   - System now recommends NO_SHIP
   - Rationale includes: "Cost ($1500) exceeds budget ($1000)"

5. [SUBSTRATE] Human can still override
   - Authority required for budget overruns
   - Override tracked with economic metadata
```

---

### 8.4 Contradiction Detection Flow

```
1. [ENGINE A] Asserts: "Code coverage = 85%"
   ↓
2. [ENGINE B] Asserts: "Code coverage = 72%"
   ↓
3. [SUBSTRATE] Detect contradiction
   - Two assertions with same meaning_id but different values
   - Check meaning versions: both use "coverage.line.v1"
   - Compute contradiction severity: HIGH

4. [SUBSTRATE] Emit Contradiction
   - type = ASSERTION_CONFLICT
   - conflicting_items = [assertion_a_id, assertion_b_id]
   - explanation = "Different engines report different coverage"
   - resolution_status = UNRESOLVED

5. [SUBSTRATE] Surface in report
   - Warning: "Coverage data conflict detected"
   - Recommendation: "Investigate engine configurations"

6. [HUMAN] Investigates and resolves
   - Finds Engine B has stale cache
   - Invalidates Engine B assertion
   - Contradiction resolved
```

---

## 9. TELEMETRY & REPORTS

### 9.1 Emitted Signals (When Enabled)

**Assertion Events:**
```json
{
  "event_type": "assertion.created",
  "assertion_id": "a1b2c3...",
  "claim": "Deployment is ready",
  "evidence_count": 5,
  "source": "readiness_engine",
  "timestamp": "2026-02-01T12:00:00Z"
}
```

**Belief Events:**
```json
{
  "event_type": "belief.updated",
  "belief_id": "b4e5f6...",
  "assertion_id": "a1b2c3...",
  "confidence": 0.85,
  "confidence_delta": -0.05,
  "reason": "upstream_decay",
  "timestamp": "2026-02-01T12:05:00Z"
}
```

**Contradiction Events:**
```json
{
  "event_type": "contradiction.detected",
  "contradiction_id": "c7d8e9...",
  "type": "assertion_conflict",
  "severity": "HIGH",
  "conflicting_items": ["a1b2c3...", "a9f8e7..."],
  "timestamp": "2026-02-01T12:10:00Z"
}
```

**Economic Events:**
```json
{
  "event_type": "economic.signal",
  "signal_type": "cost",
  "amount": 150.00,
  "unit": "USD",
  "applies_to": "deployment_xyz",
  "timestamp": "2026-02-01T12:15:00Z"
}
```

**Pattern Events:**
```json
{
  "event_type": "pattern.detected",
  "pattern_type": "frequent_override",
  "rule_id": "policy.coverage.min",
  "frequency": "daily",
  "confidence": 0.9,
  "timestamp": "2026-02-01T12:20:00Z"
}
```

---

### 9.2 Reports (Human-Readable)

**Cognitive Summary Report** (generated when enabled):
```markdown
# Cognitive Substrate Report
**Generated:** 2026-02-01 12:00:00 UTC
**Organization:** acme-corp
**Period:** Last 30 days

## Belief Health
- Total beliefs: 1,245
- High confidence (>0.8): 892 (71.6%)
- Low confidence (<0.5): 23 (1.8%)
- Decayed beliefs: 45 (3.6%)

## Contradictions
- Total detected: 12
- Resolved: 8
- Unresolved: 4
  - **HIGH:** Coverage data mismatch (2 instances)
  - **MEDIUM:** Policy conflict on approval gates

## Human Overrides
- Total overrides: 56
- Active: 12
- Expired: 44
- Most overridden rule: `policy.coverage.min` (15 times)
- **Recommendation:** Consider adjusting coverage threshold

## Economic Signals
- Total cost tracked: $12,450
- Average cost per deployment: $89
- Budget pressure: MEDIUM (78% of limit)
- High-cost deployments: 5 (flagged for review)

## Organizational Patterns
- Detected stage: **SCALING**
- Confidence: 0.85
- Key indicators:
  - Team size growing (now 22 members)
  - Increasing policy adoption
  - Moderate deploy frequency (2-3x per week)
- **Recommendation:** No tooling mismatch detected
```

---

## 10. DORMANCY MODEL

### 10.1 What Remains Dormant by Default

**Code exists but does nothing when:**
- `SubstrateFlags.enabled = False` (default)

**Minimal overhead when disabled:**
- Single flag check per operation
- No allocations
- No I/O
- No graph updates
- No belief computation

**What still runs (observe-only):**
- **Telemetry:** Basic event logging (configurable sampling)
- **No active features**

---

### 10.2 Activation Levels

**Level 0: Dormant (default)**
```yaml
enabled: false
telemetry_enabled: true
telemetry_sampling_rate: 0.1  # 10% sampling
```
- Zero functional overhead
- Minimal telemetry only

**Level 1: Observe-Only**
```yaml
enabled: true
assertion_graph_enabled: true
belief_engine_enabled: true
enforcement_mode: "observe"
telemetry_sampling_rate: 1.0
```
- Full tracking
- No enforcement
- All reports generated
- No impact on decisions

**Level 2: Warn**
```yaml
enabled: true
assertion_graph_enabled: true
belief_engine_enabled: true
contradiction_detection: true
enforcement_mode: "warn"
```
- Emit warnings on violations
- Still doesn't block
- Enrich verdicts with warnings

**Level 3: Enforce**
```yaml
enabled: true
# All features enabled
enforcement_mode: "block"
```
- Full enforcement of policies
- Requires explicit opt-in
- High confidence in substrate

---

## 11. INTEGRATION WITH EXISTING TRUTHCORE

### 11.1 Bridge to Verdict System

```python
class VerdictBridge:
    """
    Connects cognitive substrate to existing verdict aggregation.

    Enriches VerdictResult with cognitive metadata without breaking contract.
    """

    def enrich_verdict(
        self,
        base_verdict: VerdictResult,
        beliefs: list[Belief],
        contradictions: list[Contradiction],
        economic_signals: list[EconomicSignal]
    ) -> VerdictResult:
        """Add cognitive context to verdict metadata."""

        # Existing verdict unchanged
        enriched = base_verdict

        # Add cognitive metadata (backward-compatible)
        enriched.metadata["cognitive"] = {
            "beliefs": [b.to_dict() for b in beliefs],
            "average_confidence": sum(b.confidence for b in beliefs) / len(beliefs),
            "contradictions": [c.to_dict() for c in contradictions],
            "economic_total_cost": sum(s.amount for s in economic_signals if s.signal_type == EconomicSignalType.COST),
        }

        return enriched
```

---

### 11.2 Bridge to Policy Engine

```python
class PolicyBridge:
    """
    Extends existing policy engine with cognitive policies.

    Reuses InvariantDSL and PolicyPack models.
    """

    def convert_cognitive_policy(
        self,
        cognitive_policy: CognitivePolicy
    ) -> PolicyRule:
        """Convert cognitive policy to existing PolicyRule format."""

        return PolicyRule(
            id=cognitive_policy.policy_id,
            category=self._map_policy_type(cognitive_policy.policy_type),
            severity=Severity.MEDIUM,  # Default, can be overridden
            rule=cognitive_policy.rule,
            metadata={"cognitive": True, **cognitive_policy.metadata}
        )

    def evaluate_cognitive_policies(
        self,
        substrate: SubstrateRuntime,
        context: dict[str, Any]
    ) -> list[Finding]:
        """Evaluate cognitive policies and return findings."""

        findings = []
        for policy in substrate.get_active_policies():
            if not self._evaluate_rule(policy.rule, context):
                finding = Finding(
                    rule_id=policy.policy_id,
                    severity=self._policy_severity(policy),
                    message=f"Cognitive policy violation: {policy.policy_id}",
                    # ...
                )
                findings.append(finding)
        return findings
```

---

### 11.3 Bridge to Provenance Manifests

```python
class ManifestBridge:
    """
    Extends existing provenance manifests with cognitive lineage.

    Backward-compatible: adds cognitive section to metadata.
    """

    def enrich_manifest(
        self,
        base_manifest: RunManifest,
        assertions: list[Assertion],
        beliefs: list[Belief],
        decisions: list[Decision],
        economic_signals: list[EconomicSignal]
    ) -> RunManifest:
        """Add cognitive provenance to manifest."""

        enriched = base_manifest
        enriched.metadata["cognitive"] = {
            "assertions": [a.to_dict() for a in assertions],
            "beliefs": [b.to_dict() for b in beliefs],
            "decisions": [d.to_dict() for d in decisions],
            "economic": [e.to_dict() for e in economic_signals],
            "substrate_version": "1.0.0",
        }

        return enriched
```

---

## 12. EXPLICIT PHASED IMPLEMENTATION PLAN

### Phase 0: Foundation (Week 1-2)
**Goal:** Establish primitives and infrastructure without breaking anything.

**Deliverables:**
1. **Core Primitives** (`src/truthcore/substrate/primitives/`)
   - Define all dataclasses: Assertion, Evidence, Belief, MeaningVersion, Decision, EconomicSignal
   - Implement serialization (to_dict/from_dict)
   - Add comprehensive docstrings
   - Write unit tests for each primitive

2. **Configuration & Flags** (`src/truthcore/substrate/config/`)
   - Implement SubstrateFlags
   - Create profile system (YAML-based)
   - Add runtime flag checking (zero-cost when disabled)

3. **Telemetry Foundation** (`src/truthcore/substrate/telemetry/`)
   - Design event schema
   - Implement sampling
   - Add structured logging (use existing structlog)

**Acceptance Criteria:**
- All primitives serialize correctly
- Flags default to disabled
- Zero tests fail
- No existing functionality broken

---

### Phase 1: Graph Layer (Week 3-4)
**Goal:** Build assertion graph and belief engine (observe-only).

**Deliverables:**
1. **Assertion Graph** (`src/truthcore/substrate/graph/assertion_graph.py`)
   - Implement DAG storage (in-memory + cache)
   - Add lineage tracking
   - Support deterministic serialization

2. **Belief Engine** (`src/truthcore/substrate/graph/belief_engine.py`)
   - Implement confidence computation
   - Add decay propagation
   - Version belief history

3. **Contradiction Detector** (`src/truthcore/substrate/graph/contradiction.py`)
   - Detect assertion conflicts
   - Detect belief divergence
   - Generate contradiction reports

**Acceptance Criteria:**
- Assertion graph maintains DAG invariants
- Beliefs decay correctly over time
- Contradictions detected but not resolved
- All graph operations replay deterministically

---

### Phase 2: Integration Bridges (Week 5-6)
**Goal:** Connect substrate to existing truthcore systems.

**Deliverables:**
1. **Verdict Bridge** (`src/truthcore/substrate/integrations/verdict_bridge.py`)
   - Convert Findings → Assertions
   - Enrich VerdictResult with cognitive metadata
   - Maintain backward compatibility

2. **Policy Bridge** (`src/truthcore/substrate/integrations/policy_bridge.py`)
   - Extend PolicyPack with cognitive policies
   - Reuse InvariantDSL for belief/economic rules
   - Add cognitive policy evaluation

3. **Manifest Bridge** (`src/truthcore/substrate/integrations/manifest_bridge.py`)
   - Extend RunManifest with cognitive provenance
   - Add assertion lineage to manifests
   - Preserve existing manifest schema

**Acceptance Criteria:**
- Existing engines produce assertions when enabled
- Verdicts enriched with cognitive data
- Manifests contain full cognitive lineage
- All existing tests pass

---

### Phase 3: Governance Layer (Week 7-8)
**Goal:** Implement human override tracking and reconciliation.

**Deliverables:**
1. **Human Override** (`src/truthcore/substrate/governance/human_override.py`)
   - Implement HumanOverride model
   - Add authority validation
   - Track expiry and renewal

2. **Reconciliation Engine** (`src/truthcore/substrate/governance/reconciliation.py`)
   - Detect system vs. human divergence
   - Compute divergence scores
   - Generate reconciliation reports

3. **CLI Extensions** (`src/truthcore/cli.py`)
   - Add `truthctl override` command
   - Add `truthctl reconcile` command
   - Display override status in verdicts

**Acceptance Criteria:**
- Overrides tracked in provenance
- Expiry enforced (overrides auto-expire)
- Divergence reports generated
- CLI supports override management

---

### Phase 4: Economic Layer (Week 9-10)
**Goal:** Track economic signals and integrate with beliefs.

**Deliverables:**
1. **Economic Signal Processor** (`src/truthcore/substrate/economic/signals.py`)
   - Record cost/risk/value signals
   - Implement signal aggregation
   - Add budget pressure computation

2. **Economic Invariants** (`src/truthcore/substrate/economic/invariants.py`)
   - Define economic constraint DSL
   - Implement invariant evaluation
   - Generate economic violation reports

3. **Belief Integration**
   - Adjust belief confidence based on economic signals
   - Include economic rationale in decisions
   - Add economic metadata to verdicts

**Acceptance Criteria:**
- Economic signals tracked in telemetry
- Budget pressure computed correctly
- Beliefs influenced by cost (when enabled)
- Economic reports generated

---

### Phase 5: Learning Layer (Week 11-12)
**Goal:** Detect organizational patterns (observe-only).

**Deliverables:**
1. **Pattern Detector** (`src/truthcore/substrate/learning/pattern_detector.py`)
   - Detect frequent overrides
   - Identify risk/cost/velocity preferences
   - Generate pattern reports

2. **Stage-Gate Detector** (`src/truthcore/substrate/learning/stage_gate.py`)
   - Detect early/scaling/mature stages
   - Compute stage confidence
   - Track stage transitions

3. **Mismatch Detector** (`src/truthcore/substrate/learning/mismatch.py`)
   - Detect over-engineering
   - Detect under-governance
   - Generate recommendations

**Acceptance Criteria:**
- Patterns detected from historical data
- Stage detection works on real usage
- Mismatch reports actionable
- No enforcement, only observation

---

### Phase 6: Reporting & Dashboard (Week 13-14)
**Goal:** Human-readable reports and dashboard integration.

**Deliverables:**
1. **Report Generator** (`src/truthcore/substrate/telemetry/reports.py`)
   - Generate cognitive summary reports (Markdown)
   - Export belief graphs (JSON)
   - Create contradiction summaries

2. **Dashboard Integration** (`dashboard/src/substrate/`)
   - Add cognitive substrate view
   - Visualize assertion graphs
   - Display belief confidence trends
   - Show contradiction timeline

3. **CLI Reporting**
   - Add `truthctl substrate report` command
   - Add `truthctl substrate status` command
   - Display cognitive metrics in existing commands

**Acceptance Criteria:**
- Reports generated automatically
- Dashboard displays cognitive data
- CLI provides substrate visibility
- Reports are actionable

---

### Phase 7: Hardening & Documentation (Week 15-16)
**Goal:** Production readiness.

**Deliverables:**
1. **Security Hardening**
   - Apply SecurityLimits to substrate operations
   - Add input validation for all primitives
   - Implement resource quotas for graph size

2. **Documentation**
   - Architecture guide (this document)
   - API reference
   - Integration guide for new apps
   - Migration guide for existing apps

3. **Testing**
   - Integration tests across all layers
   - Performance benchmarks (overhead when disabled)
   - Replay determinism tests
   - Backward compatibility tests

**Acceptance Criteria:**
- Security review passed
- Documentation complete
- <1ms overhead when disabled
- 100% deterministic replay
- All backward compatibility tests pass

---

### Phase 8: Pilot Deployment (Week 17-20)
**Goal:** Deploy to Settler in observe-only mode.

**Deliverables:**
1. **Settler Integration**
   - Enable substrate with profile `settler.yaml`
   - Set enforcement_mode = OBSERVE
   - Collect telemetry for 2 weeks

2. **Data Analysis**
   - Analyze contradiction frequency
   - Review override patterns
   - Evaluate economic signal quality
   - Assess stage detection accuracy

3. **Iteration**
   - Adjust confidence thresholds based on data
   - Refine contradiction detection
   - Tune economic signal weights

**Acceptance Criteria:**
- Substrate running in production (observe-only)
- No performance degradation
- Telemetry flowing correctly
- Actionable insights generated

---

### Phase 9: Gradual Activation (Week 21+)
**Goal:** Enable features incrementally based on confidence.

**Activation Order:**
1. **Assertion Graph** (Week 21)
   - Enable for all Settler runs
   - Monitor graph size and performance

2. **Belief Engine** (Week 23)
   - Enable belief formation
   - Track confidence trends
   - Validate decay rates

3. **Contradiction Detection** (Week 25)
   - Enable soft contradiction warnings
   - Do not block on contradictions yet
   - Validate detection accuracy

4. **Economic Signals** (Week 27)
   - Enable cost tracking
   - Integrate with billing systems
   - Validate signal quality

5. **Human Governance** (Week 29)
   - Enable override tracking
   - Enforce expiry
   - Monitor divergence

6. **Enforcement Mode** (Week 31+)
   - Gradually shift from OBSERVE → WARN → BLOCK
   - Only for high-confidence policies
   - Require explicit approval for each policy

**Success Criteria:**
- Each feature proves value before next activation
- No unexpected failures
- User feedback incorporated
- Clear ROI demonstrated

---

## 13. NON-BREAKING GUARANTEES

### 13.1 Existing Contracts Unchanged

**Guarantees:**
1. All existing CLI commands work identically
2. All existing Python APIs unchanged
3. All existing output formats unchanged (JSON, Markdown, CSV)
4. All existing verdicts computed the same way
5. All existing tests pass

**How:**
- Substrate is additive only
- Enriches metadata, doesn't replace core fields
- Bridges are backward-compatible
- Feature flags default to disabled

---

### 13.2 Opt-In Activation

**Guarantees:**
1. No app is forced to use substrate
2. Apps can adopt layer-by-layer (graph → beliefs → governance → economic → learning)
3. Apps can disable substrate entirely with single flag
4. Apps that never enable substrate see zero overhead

**How:**
- Profile-based configuration
- Layer-specific flags
- Runtime flag checks
- Zero-cost abstraction when disabled

---

### 13.3 Graceful Degradation

**Guarantees:**
1. If substrate fails, existing functionality continues
2. No hard failures, only warnings
3. Telemetry failures don't block operations
4. Storage failures don't break verdicts

**How:**
- Try-catch around all substrate operations
- Fallback to base functionality on error
- Log failures but don't propagate
- Health checks with automatic disable on persistent failures

---

## 14. FUTURE EXTENSIONS (Out of Scope for v1.0)

### 14.1 Advanced Belief Reasoning
- Probabilistic belief networks
- Bayesian confidence updates
- Multi-agent belief consensus

### 14.2 Active Learning
- Reinforcement from human feedback
- Policy auto-tuning based on patterns
- Adaptive thresholds

### 14.3 Federated Learning
- Cross-organization pattern sharing (privacy-preserving)
- Industry benchmark comparison
- Collaborative policy development

### 14.4 LLM Integration
- Natural language policy authoring
- Semantic contradiction detection
- Automated reconciliation suggestions

### 14.5 Real-Time Adaptation
- Dynamic threshold adjustment during incidents
- Emergency override protocols
- Automatic rollback on detected anomalies

---

## 15. SUMMARY

### What This Is
A **foundational architecture** for truth representation, belief formation, and decision governance that can be adopted across multiple applications without breaking existing systems.

### What This Is Not
- Not a replacement for existing engines
- Not enforced by default
- Not required for core truthcore functionality
- Not a complete AI reasoning system

### Key Innovations
1. **Assertion graphs** for truth provenance
2. **Belief versioning** with temporal decay
3. **Semantic versioning** of meaning
4. **Economic signals** as first-class primitives
5. **Human governance** with expiry and scope
6. **Organizational learning** (observe-only)
7. **Zero-overhead** when disabled

### Success Metrics
- **Adoption:** 3+ apps using substrate within 6 months
- **Overhead:** <1ms when disabled, <10ms when enabled
- **Value:** 20%+ reduction in contradictions/misalignments
- **Governance:** 100% of human overrides tracked and auditable
- **Learning:** Accurate stage detection in 80%+ of orgs

---

## 16. NEXT STEPS

### Immediate Actions (Week 1)
1. **Review this design** with stakeholders
2. **Get approval** for Phase 0 implementation
3. **Set up project structure** in truthcore repo
4. **Define success criteria** for pilot

### Long-Term Roadmap
- **Q1 2026:** Phase 0-4 (Foundation, Graph, Integration, Governance)
- **Q2 2026:** Phase 5-7 (Economic, Learning, Hardening)
- **Q3 2026:** Phase 8-9 (Pilot, Activation)
- **Q4 2026:** Multi-app adoption, v2.0 planning

---

**Document Version:** 1.0
**Last Updated:** 2026-02-01
**Authors:** Claude Sonnet (Principal Systems Architect)
**Status:** Pending Review
