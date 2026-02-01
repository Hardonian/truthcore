# Cognitive Substrate — Quick Reference
**Last Updated:** 2026-02-01

> **Full Design:** See `COGNITIVE_SUBSTRATE_ARCHITECTURE.md` for complete specification

---

## What Is This?

A **dormant, opt-in engine** for truth representation, belief formation, and decision governance that lives in truthcore but activates ONLY when explicitly enabled by applications.

**Key Principle:** Spinal cord, not brain. Infrastructure for reasoning, not reasoning itself.

---

## Core Primitives (7 Total)

| Primitive | Purpose | Key Features |
|-----------|---------|--------------|
| **Assertion** | A claim the system believes | Content-addressed, evidence-linked, immutable |
| **Evidence** | Data supporting assertions | Versioned, can expire, tracks provenance |
| **Belief** | Assertion + confidence + decay | Versioned, decays over time, depends on upstream |
| **MeaningVersion** | Semantic definition of concepts | Separate from schema versions, detects drift |
| **Decision** | System or human action | Tracks rationale, authority, expiry |
| **CognitivePolicy** | Constraints on decisions | Extends existing policy engine |
| **EconomicSignal** | Cost/risk/value indicators | First-class input, not billing metadata |

---

## Architecture Layers (6 Total)

```
┌─────────────────────────────────────────────────────────┐
│  LEARNING LAYER (observe-only)                          │
│  • Pattern detection • Stage-gate • Mismatch warnings   │
├─────────────────────────────────────────────────────────┤
│  ECONOMIC LAYER                                         │
│  • Signals • Invariants • Budget tracking               │
├─────────────────────────────────────────────────────────┤
│  GOVERNANCE LAYER                                       │
│  • Human overrides • Authority • Reconciliation         │
├─────────────────────────────────────────────────────────┤
│  GRAPH LAYER                                            │
│  • Assertion graph • Belief engine • Contradictions     │
├─────────────────────────────────────────────────────────┤
│  PRIMITIVES LAYER                                       │
│  • 7 core abstractions • Serializable • Versioned       │
├─────────────────────────────────────────────────────────┤
│  INTEGRATION BRIDGES                                    │
│  • Verdict • Policy • Manifest (backward-compatible)    │
└─────────────────────────────────────────────────────────┘
```

---

## Feature Flags (Default: ALL OFF)

```yaml
# Default configuration (zero overhead)
substrate:
  enabled: false                      # Master switch: OFF
  telemetry_enabled: true             # Minimal logging only
  telemetry_sampling_rate: 0.1        # 10% sample

# Observe-only mode (safe activation)
substrate:
  enabled: true
  assertion_graph_enabled: true       # Track assertions
  belief_engine_enabled: true         # Form beliefs
  contradiction_detection: true       # Detect conflicts
  enforcement_mode: "observe"         # NEVER block
  telemetry_sampling_rate: 1.0        # Full telemetry

# Enforcement mode (requires explicit opt-in)
substrate:
  enabled: true
  # ... all features enabled ...
  enforcement_mode: "block"           # Hard enforcement
```

---

## Key Flows

### 1. Assertion → Belief → Decision
```
Finding (existing)
  → Assertion (new)
  → Belief with confidence (new)
  → Decision input (enriched)
  → VerdictResult (backward-compatible)
```

### 2. Human Override
```
System decision: NO_SHIP
  → Human override: SHIP (with authority, expiry, rationale)
  → Divergence detected and tracked
  → Override expires after N days
  → Next decision uses system default (unless renewed)
```

### 3. Contradiction Detection
```
Engine A: "Coverage = 85%"
Engine B: "Coverage = 72%"
  → Contradiction detected (HIGH severity)
  → Report emitted (not auto-resolved)
  → Human investigates and resolves
```

### 4. Economic Integration
```
External tracker: Cost = $1500
  → EconomicSignal recorded
  → Belief confidence adjusted (0.85 → 0.70)
  → Decision rationale includes cost
  → Human can override with authority
```

---

## Telemetry & Reports

### Events Emitted (when enabled)
- `assertion.created` — New claim made
- `belief.updated` — Confidence changed
- `contradiction.detected` — Conflict found
- `economic.signal` — Cost/risk/value recorded
- `pattern.detected` — Organizational behavior identified
- `override.created` — Human intervention
- `divergence.detected` — System vs. human mismatch

### Reports Generated
```markdown
# Cognitive Substrate Report

## Belief Health
- Total beliefs: 1,245
- High confidence (>0.8): 71.6%
- Decayed beliefs: 3.6%

## Contradictions
- Total: 12 (8 resolved, 4 active)
- Most common: Coverage data mismatch

## Human Overrides
- Total: 56 (12 active, 44 expired)
- Most overridden rule: coverage.min (15x)
- **Recommendation:** Adjust threshold

## Economic
- Total cost: $12,450 (avg $89/deploy)
- Budget pressure: MEDIUM (78%)

## Organizational Stage
- Detected: SCALING (confidence 0.85)
- No tooling mismatch
```

---

## Phased Implementation (16 Week Plan)

| Phase | Weeks | Deliverable | Status |
|-------|-------|-------------|--------|
| **0. Foundation** | 1-2 | Primitives, flags, telemetry | Not started |
| **1. Graph Layer** | 3-4 | Assertion graph, beliefs, contradictions | Not started |
| **2. Integration** | 5-6 | Verdict/policy/manifest bridges | Not started |
| **3. Governance** | 7-8 | Human overrides, reconciliation | Not started |
| **4. Economic** | 9-10 | Signals, invariants, budget | Not started |
| **5. Learning** | 11-12 | Patterns, stage-gate, mismatch | Not started |
| **6. Reporting** | 13-14 | Reports, dashboard, CLI | Not started |
| **7. Hardening** | 15-16 | Security, docs, testing | Not started |
| **8. Pilot** | 17-20 | Settler observe-only deployment | Not started |
| **9. Activation** | 21+ | Gradual feature enablement | Not started |

---

## Non-Breaking Guarantees

✅ **All existing CLI commands work identically**
✅ **All existing APIs unchanged**
✅ **All existing tests pass**
✅ **All existing output formats preserved**
✅ **Zero overhead when disabled (<1ms)**
✅ **Opt-in only, never forced**
✅ **Graceful degradation on errors**

---

## Integration Example (Settler)

```python
# 1. Enable substrate in profile
# profiles/settler.yaml
substrate:
  enabled: true
  assertion_graph_enabled: true
  belief_engine_enabled: true
  enforcement_mode: "observe"

# 2. Existing code unchanged
finding = policy_engine.run(files)
verdict = verdict_aggregator.aggregate([finding])

# 3. Substrate automatically enriches (when enabled)
# - Finding → Assertion → Belief
# - Verdict enriched with cognitive metadata
# - Manifest extended with assertion lineage
# - Telemetry emitted
# - Reports generated

# 4. Access cognitive data
if verdict.metadata.get("cognitive"):
    avg_confidence = verdict.metadata["cognitive"]["average_confidence"]
    contradictions = verdict.metadata["cognitive"]["contradictions"]
    total_cost = verdict.metadata["cognitive"]["economic_total_cost"]
```

---

## Quick Start (When Ready)

### Step 1: Review Design
- Read `COGNITIVE_SUBSTRATE_ARCHITECTURE.md`
- Validate primitives and flows
- Approve phased plan

### Step 2: Implement Phase 0 (Week 1-2)
```bash
# Create substrate module structure
mkdir -p src/truthcore/substrate/{primitives,graph,governance,economic,learning,telemetry,config,integrations}

# Implement primitives
# • assertion.py, belief.py, meaning.py, decision.py, policy.py, economic.py

# Implement flags
# • flags.py, substrate_config.py, profiles.py

# Write tests
pytest tests/substrate/test_primitives.py
```

### Step 3: Validate Zero Overhead
```bash
# Benchmark with substrate disabled
truthctl judge --profile settler --no-substrate
# Expected: <1ms overhead

# Benchmark with substrate enabled (observe-only)
truthctl judge --profile settler --substrate-observe
# Expected: <10ms overhead
```

### Step 4: Iterate Through Phases
- Complete Phase 1 (Graph Layer)
- Complete Phase 2 (Integration Bridges)
- ... continue through Phase 9

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Adoption** | 3+ apps in 6mo | App count using substrate |
| **Overhead (disabled)** | <1ms | Benchmark comparison |
| **Overhead (enabled)** | <10ms | Benchmark comparison |
| **Value** | 20%+ reduction | Contradiction/misalignment count |
| **Governance** | 100% tracked | Override audit coverage |
| **Learning** | 80%+ accuracy | Stage detection validation |

---

## Next Steps

### Immediate (This Week)
1. ✅ Design complete
2. ⏳ Stakeholder review
3. ⏳ Approve Phase 0
4. ⏳ Set up project structure

### Short-Term (Q1 2026)
- Implement Phases 0-4 (Foundation → Governance)
- All core primitives functional
- Integration bridges working
- Human override tracking operational

### Mid-Term (Q2-Q3 2026)
- Implement Phases 5-7 (Economic → Hardening)
- Pilot deployment to Settler (observe-only)
- Data collection and analysis
- Iteration based on real usage

### Long-Term (Q4 2026+)
- Multi-app adoption (ReadyLayer, Keys, AIAS)
- Gradual activation of enforcement
- v2.0 planning with advanced features
- Industry-wide pattern sharing

---

## Questions & Decisions Needed

### Open Questions
1. **Confidence computation formula:** Use Bayesian, weighted average, or custom?
2. **Decay rate defaults:** What are sensible defaults for different evidence types?
3. **Authority model:** Who can override what? RBAC, team-based, or custom?
4. **Economic signal sources:** Which systems provide cost data?
5. **Stage-gate thresholds:** What team size = SCALING vs. MATURE?

### Decisions Needed
1. **Approve phased plan:** Is 16-week timeline acceptable?
2. **Pilot app:** Confirm Settler as pilot, or choose different app?
3. **Telemetry storage:** Where do events go? (local, S3, external service?)
4. **Report format:** Markdown sufficient, or add JSON/CSV/HTML?
5. **Dashboard integration:** Extend existing dashboard or build new UI?

---

## Resources

- **Full Design:** `COGNITIVE_SUBSTRATE_ARCHITECTURE.md`
- **Codebase:** `src/truthcore/substrate/` (not yet created)
- **Tests:** `tests/substrate/` (not yet created)
- **Examples:** `examples/substrate/` (not yet created)
- **Docs:** `docs/substrate/` (not yet created)

---

**Document Status:** Design Complete, Pending Implementation
**Owner:** Platform Engineering Team
**Contact:** architecture@truthcore.dev (placeholder)
