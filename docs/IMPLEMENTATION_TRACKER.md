# TruthCore Spine Implementation Tracker
**Milestone:** Read-Only Truth Spine (v0.3.0)
**Status:** Not Started → Phase 0 Ready
**Last Updated:** 2026-02-01

---

## Week-by-Week Progress

### Phase 0: Foundation [Week 1]
**Goal:** Core primitives and storage layer

| Task | Status | Owner | Notes |
|------|--------|-------|-------|
| Create `src/truthcore/spine/` module structure | 🔲 Not Started | TBD | Follow existing pattern |
| Implement Assertion dataclass | 🔲 Not Started | TBD | Frozen, content-addressed |
| Implement Evidence dataclass | 🔲 Not Started | TBD | Frozen, content-addressed |
| Implement Belief dataclass | 🔲 Not Started | TBD | Frozen, versioned |
| Implement MeaningVersion dataclass | 🔲 Not Started | TBD | Frozen, semantic versioning |
| Implement Decision dataclass | 🔲 Not Started | TBD | Frozen, provenance |
| Implement Override dataclass | 🔲 Not Started | TBD | Frozen, time-bounded |
| Create content-addressed storage layer | 🔲 Not Started | TBD | blake2b hashing |
| Implement deterministic JSON serialization | 🔲 Not Started | TBD | Sort keys, canonical format |
| Write unit tests for all primitives | 🔲 Not Started | TBD | 100% coverage |
| **Phase 0 Acceptance** | 🔲 Not Started | TBD | All tests pass |

**Deliverable:** `truthcore.spine.primitives` module with full test coverage

---

### Phase 1: Graph & Belief Engine [Week 2]
**Goal:** Assertion graph and belief computation

| Task | Status | Owner | Notes |
|------|--------|-------|-------|
| Implement GraphStore (DAG storage) | 🔲 Not Started | TBD | Content-addressed |
| Implement lineage tracking | 🔲 Not Started | TBD | Upstream/downstream |
| Implement BeliefEngine | 🔲 Not Started | TBD | Confidence computation |
| Implement confidence decay logic | 🔲 Not Started | TBD | Time-based decay |
| Implement belief versioning | 🔲 Not Started | TBD | Append-only history |
| Implement ContradictionDetector | 🔲 Not Started | TBD | Detection only |
| Write integration tests | 🔲 Not Started | TBD | Graph operations |
| **Phase 1 Acceptance** | 🔲 Not Started | TBD | Lineage queries work |

**Deliverable:** `truthcore.spine.graph` and `truthcore.spine.belief` modules

---

### Phase 2: Ingestion Bridge [Week 3]
**Goal:** Connect to Silent Instrumentation

| Task | Status | Owner | Notes |
|------|--------|-------|-------|
| Create IngestionQueue (bounded, async) | 🔲 Not Started | TBD | Drop when full |
| Implement signal transformation layer | 🔲 Not Started | TBD | Finding → Assertion |
| Implement deduplication pipeline | 🔲 Not Started | TBD | Hash-based |
| Create error handling (fail silent) | 🔲 Not Started | TBD | Never propagate |
| Implement health monitoring | 🔲 Not Started | TBD | Auto-disable on failure |
| Write stress tests | 🔲 Not Started | TBD | Queue saturation |
| **Phase 2 Acceptance** | 🔲 Not Started | TBD | Ingest without blocking |

**Deliverable:** `truthcore.spine.ingest` module with async processing

---

### Phase 3: Query Surface [Week 4]
**Goal:** All 7 MVP query types

| Query | Status | Endpoint | Complexity |
|-------|--------|----------|------------|
| Why Query (lineage) | 🔲 Not Started | `truthctl spine why` | Medium |
| Evidence Query | 🔲 Not Started | `truthctl spine evidence` | Low |
| History Query | 🔲 Not Started | `truthctl spine history` | Low |
| Meaning Query | 🔲 Not Started | `truthctl spine meaning` | Low |
| Override Query | 🔲 Not Started | `truthctl spine override` | Low |
| Dependencies Query | 🔲 Not Started | `truthctl spine dependencies` | Medium |
| Invalidation Query | 🔲 Not Started | `truthctl spine invalidate` | High |

**Deliverable:** `truthcore.spine.query` module with all MVP queries

---

### Phase 4: CLI & API [Week 5]
**Goal:** Human interfaces

| Task | Status | Owner | Notes |
|------|--------|-------|-------|
| Extend `truthctl` with `spine` subcommand | 🔲 Not Started | TBD | Follow existing CLI pattern |
| Implement all query commands | 🔲 Not Started | TBD | 7 query types |
| Add JSON and Markdown output formats | 🔲 Not Started | TBD | Human + machine readable |
| Create REST API endpoints | 🔲 Not Started | TBD | Server mode |
| Write CLI documentation | 🔲 Not Started | TBD | Man pages, help text |
| **Phase 4 Acceptance** | 🔲 Not Started | TBD | CLI usable without docs |

**Deliverable:** Full CLI and REST API for all queries

---

### Phase 5: Integration & Hardening [Week 6]
**Goal:** Production readiness

| Task | Status | Owner | Notes |
|------|--------|-------|-------|
| Integrate with existing dashboard | 🔲 Not Started | TBD | Lineage visualization |
| Feature flag testing (all levels) | 🔲 Not Started | TBD | Dormant → Full |
| Performance optimization | 🔲 Not Started | TBD | < 100ms p99 |
| Write operational documentation | 🔲 Not Started | TBD | Runbook |
| Create examples and use cases | 🔲 Not Started | TBD | 3+ examples |
| **Phase 5 Acceptance** | 🔲 Not Started | TBD | Zero incidents |

**Deliverable:** Production-ready system with documentation

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation | Status |
|------|------------|--------|------------|--------|
| Nobody uses it | Medium | High | Dashboard integration, compelling examples | 🔲 Monitoring |
| Performance overhead | Low | Medium | Async, bounded queues, profiling | 🔲 Monitoring |
| Storage explosion | Low | Medium | Evidence TTL, dedup, compaction | 🔲 Monitoring |
| Privacy leakage | Low | High | Hash-based refs, redaction, audit | 🔲 Monitoring |
| Contradiction overload | Medium | Medium | Severity filtering, dedup | 🔲 Monitoring |

---

## Success Metrics Tracker

| Metric | Baseline | Target | Current | Status |
|--------|----------|--------|---------|--------|
| Query usage | 0 | > 100/week | 0 | 🔲 Not Started |
| Adoption rate | 0% | > 30% | 0% | 🔲 Not Started |
| Performance (p99) | N/A | < 100ms | N/A | 🔲 Not Started |
| Storage growth | N/A | < 100MB/day | N/A | 🔲 Not Started |
| Error rate | N/A | < 0.1% | N/A | 🔲 Not Started |
| Test coverage | N/A | > 90% | 0% | 🔲 Not Started |

---

## Decisions Log

| Date | Decision | Rationale | Status |
|------|----------|-----------|--------|
| 2026-02-01 | blake2b for hashing | Fast, 256-bit, standard | ✅ Approved |
| 2026-02-01 | Frozen dataclasses | Immutability, safety | ✅ Approved |
| 2026-02-01 | Append-only beliefs | History preservation | ✅ Approved |
| 2026-02-01 | Detection w/o resolution | Non-enforcement charter | ✅ Approved |
| 2026-02-01 | Feature-flagged default off | Safe deployment | ✅ Approved |
| 2026-02-01 | No real-time alerts | Observe-only scope | ✅ Approved |

---

## Open Questions

1. **Q:** Should queries support time-travel ("what did we believe at T-7 days")?
   **Status:** 🔲 Pending - Add to Phase 3 if time permits

2. **Q:** How to handle evidence that expires mid-query?
   **Status:** 🔲 Pending - Define staleness behavior

3. **Q:** Should we integrate with existing Parquet store?
   **Status:** 🔲 Pending - Evaluate during Phase 1

4. **Q:** CLI output format - default JSON or Markdown?
   **Status:** 🔲 Pending - User research needed

---

## Blockers

| Blocker | Impact | Resolution | ETA |
|---------|--------|------------|-----|
| Silent Instrumentation not implemented | Phase 2 | Can mock for testing | Week 2 |
| Need clarification on evidence TTL | Phase 0 | Decision needed | Week 1 |

---

**Next Action:** Begin Phase 0 - Create module structure and Assertion dataclass
