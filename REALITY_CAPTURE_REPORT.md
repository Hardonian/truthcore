# Reality Capture Report

**System:** TruthCore v0.2.0
**Observation Period:** Simulated 30-60 day observe-only analysis
**Method:** Static signal analysis of system boundaries, decision paths, and structural behavior
**Date:** 2026-02-01

---

## 1. Executive Summary: What Reality Looks Like

TruthCore is a verification system that produces verdicts (SHIP / NO_SHIP / CONDITIONAL) by aggregating weighted findings from multiple engines. In practice, the system behaves as a **point-in-time scoring machine** rather than a belief system. It assigns numeric weight to issues, sums them, compares against thresholds, and emits a verdict. There is no memory between runs, no confidence decay, no learning, and no record of human response to its outputs.

The system is honest about what it finds but silent about what it cannot see. It has no awareness of whether its verdicts were followed, overridden, or ignored. It does not know if the same finding has appeared fifty times or once. It treats every run as the first run.

The designed Cognitive Substrate and Silent Instrumentation Layer describe a fundamentally different system — one with beliefs, memory, contradiction detection, and organizational learning. None of this exists yet. The gap between the designed future and the operating present is the central dynamic of this system.

---

## 2. Top 5 Observed Dynamics Not Obvious at Design Time

### 2.1 The system has two separate severity ontologies that do not communicate

`findings.py` defines `Severity` (BLOCKER, HIGH, MEDIUM, LOW, INFO). `verdict/models.py` defines `SeverityLevel` with identical values but as a separate enum. Findings created by engines use the first. Verdict aggregation uses the second. The translation happens implicitly during JSON round-tripping — severity is serialized to a string and re-parsed. This means the type system provides no guarantee that a BLOCKER in one module means the same thing as a BLOCKER in the other. In practice they align, but the structural seam is real.

### 2.2 Category assignment is the most consequential and least governed decision

A security finding scores at 2.0x multiplier. A general finding scores at 1.0x. This means category assignment — which happens at finding creation time, often via string matching in `_extract_findings_from_data` — silently doubles or halves the weight of an issue. There is no audit trail for why a finding received a particular category. The system's most powerful lever has no governance.

### 2.3 The verdict defaults to SHIP and requires evidence to change its mind

`VerdictResult` initializes with `verdict=VerdictStatus.SHIP`. The aggregator then looks for reasons to downgrade. This is a philosophical stance embedded in code: the system is optimistic by default. Absence of findings is indistinguishable from absence of scanning. A run that processes zero input files returns SHIP.

### 2.4 The "override" concept exists in design but has no operational surface

The verdict model includes `max_highs_with_override` — a higher threshold that can be used when overrides are present. But there is no mechanism to register, track, or expire an override. The override path exists as a threshold number, not as a governance flow. In practice, overriding the system means ignoring its output, which is invisible to the system.

### 2.5 Engine-level pass/fail is computed but does not drive the verdict

Each `EngineContribution` gets a `passed` boolean computed from blocker count, high count, and a proportional point share. But `_determine_verdict` does not consult engine-level pass/fail at all — it operates on aggregate totals. An engine can fail while the overall verdict is SHIP. This information is available in reports but has no decision authority.

---

## 3. High-Risk Blind Spots Accumulating Quietly

### 3.1 No temporal awareness

The system cannot distinguish between a finding that appeared for the first time and one that has persisted for 60 days. Every run is stateless. This means chronic issues accumulate no additional urgency. A MEDIUM finding on day one and the same MEDIUM finding on day sixty score identically. The system cannot answer: "What is getting worse?"

### 3.2 Silence is indistinguishable from health

If an engine is not invoked, produces no findings, or fails silently, the verdict improves. There is no concept of "expected coverage" — no assertion that a certain engine *should* have run. The `aggregate_verdict` function catches `JSONDecodeError` and `FileNotFoundError`, prints a warning, and continues. A corrupted or missing input file makes the system more optimistic, not less.

### 3.3 Category multipliers encode organizational values that have no expiry or review cycle

Security and privacy findings carry permanent 2.0x weight. Finance carries 1.5x. These weights reflect a moment-in-time organizational judgment. There is no mechanism to review whether these weights still reflect actual risk priorities. They will silently drift from organizational reality as the context changes.

---

## 4. Areas of Unexpected Strength or Resilience

### 4.1 Determinism is genuinely achieved

The system's commitment to stable sorting, content-addressed hashing, canonical JSON, and normalized timestamps is not aspirational — it is enforced in the code. `Finding.to_dict()` sorts metadata keys. `FindingReport.write_json()` uses `sort_keys=True`. This means runs are reproducible and diffable. For a verification system, this is foundational and often neglected.

### 4.2 The finding model is surprisingly clean as a unit of truth

`Finding` is a well-bounded data structure: rule, severity, target, location, message, excerpt with hash, suggestion, metadata, timestamp. It carries its own evidence (excerpt + hash) and supports redaction without losing verifiability. This is a solid primitive on which the Cognitive Substrate's Assertion and Evidence types can build without replacing it.

### 4.3 The policy engine's scanner selection defaults are fail-safe in the right direction

When `_get_scanner` cannot match a rule's category, it falls back to `SecretScanner`. This means ambiguous rules err toward security scanning rather than skipping. The choice is opinionated but defensible — scanning for secrets when unsure is safer than scanning for nothing.

---

## 5. Signals Regarding Readiness for Partial Enforcement

**Readiness indicators (favorable):**
- The verdict model already supports three modes (PR/MAIN/RELEASE) with distinct thresholds. Enforcement can be graduated.
- Policy packs are YAML-defined and support enable/disable per rule. Enforcement can be scoped.
- The finding model supports all the metadata needed to trace enforcement decisions back to their source.

**Readiness indicators (unfavorable):**
- There is no override mechanism. Before enforcement can begin, the system needs a way for authorized humans to say "I acknowledge this and choose to proceed." Without it, enforcement will be binary and brittle.
- There is no temporal baseline. Enforcement against a system with no history will trigger on every existing issue simultaneously, creating an avalanche rather than a graduated response.
- The dual severity enum creates a type-safety gap that should be resolved before enforcement, when miscategorization becomes consequential rather than cosmetic.

**Net assessment:** The system is structurally ready for observe-mode instrumentation. It is not yet ready for enforcement. The Instrumentation Layer should be deployed first to establish baselines before any enforcement is considered.

---

## 6. Questions the System Can Now Ask (But Could Not Before)

These questions became articulable through this analysis. The system currently lacks the data to answer them, but the Instrumentation Layer was designed precisely to make them answerable.

1. **Which findings persist across runs?** (Requires temporal linking — not yet possible)
2. **Are verdicts being followed?** (Requires downstream signal capture — not yet instrumented)
3. **Which category assignments are contested or inconsistent?** (Requires tracking category assignment provenance)
4. **Does a SHIP verdict with warnings lead to different outcomes than a clean SHIP?** (Requires outcome tracking)
5. **Which engines are silently absent from runs that expect them?** (Requires expected-coverage declarations)
6. **Are the severity multipliers calibrated to actual organizational impact?** (Requires mapping findings to real incidents)
7. **How often does the system say NO_SHIP and something ships anyway?** (Requires override tracking)
8. **What is the half-life of a finding?** (Requires finding identity across runs)
9. **Are any policy packs consistently loaded but producing zero findings?** (Could indicate stale rules or scope mismatch)
10. **When a human looks at a verdict report, what do they actually look at first?** (Requires interaction telemetry)

---

*This report describes observed dynamics. It does not prescribe action. The appropriate next step is for the builders to decide which of these observations matter most for their context.*
