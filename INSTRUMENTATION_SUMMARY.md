# Silent Instrumentation Layer — Quick Reference
**Last Updated:** 2026-02-01

> **Full Design:** See `SILENT_INSTRUMENTATION_LAYER.md` for complete specification

---

## What Is This?

A **zero-impact observability adapter** that lets existing TruthCore applications emit cognitive signals to the Shared Cognitive Substrate without changing behavior, logic, outcomes, or performance.

**Core Guarantee:** Application runs identically with or without instrumentation.

---

## Design Principles

```
┌──────────────────────────┐
│ EXISTING APPLICATION     │ ← Unchanged behavior
└────────┬─────────────────┘
         │ Events flow outward only →
         ▼
   ┌─────────────────┐
   │ INSTRUMENTATION │ ← Feature-flagged (default: OFF)
   │ (observe-only)  │ ← Never blocks, never throws
   └────────┬────────┘
            │ Telemetry (if enabled) →
            ▼
   ┌────────────────────┐
   │ COGNITIVE SUBSTRATE│ ← Optional consumer
   │ (may not exist)    │ ← Never required
   └────────────────────┘
```

**Mantras:**
- **Emit, don't infer** — Record what happened, not what it means
- **Drop data, never block** — Telemetry loss is acceptable, behavioral change is not
- **Fail internally, never propagate** — Exceptions absorbed at boundary
- **Attach at boundaries, not within** — Engines, CLI, verdicts—not internal logic

---

## Absolute Constraints (Non-Negotiable)

| Constraint | Implementation |
|------------|----------------|
| **Observe-Only** | No enforcement, no branching, no decisions |
| **Feature-Flagged** | `COGNITIVE_OBSERVE=false` (default) |
| **Zero Hard Failures** | Try-catch all, drop events on error, auto-disable after 10 failures |
| **No Semantic Assumptions** | Record raw signals, allow contradictions |
| **Minimal Overhead** | <1μs disabled, <100μs enabled |
| **No Refactors** | Single decorator per boundary, optional import |
| **Fully Removable** | Delete imports, app runs identically |

---

## What Gets Observed (8 Signal Types)

| Signal Type | What It Captures | Example |
|-------------|------------------|---------|
| **Assertions** | Claims system is making | `"deployment_ready": True` |
| **Evidence** | Data inputs | File read, API response, test result |
| **Belief Changes** | Confidence shifts | Verdict changes PASS→FAIL |
| **Semantic Usage** | How terms are actually used | `"ready" = score >= 90` |
| **Decisions** | Actions taken | System verdict: FAIL |
| **Overrides** | Human interventions | Ship despite FAIL |
| **Economic** | Cost/risk signals | Token usage, time spent |
| **Policy References** | Policies consulted | Policy evaluated but not enforced |

---

## Where It Attaches (System Boundaries Only)

```python
# 1. Engine Entry/Exit
@instrument_engine  # Single line added
def run_readiness_engine(inputs, profile):
    # ... existing logic UNCHANGED ...
    return results

# 2. Finding Creation
class Finding:
    def __init__(self, rule_id, severity, message):
        # ... existing init UNCHANGED ...
        self._notify_instrumentation()  # Single line added

# 3. Verdict Decision
def aggregate_verdict(findings, policy):
    # ... existing logic UNCHANGED ...
    result = VerdictResult(...)
    _notify_verdict_decision(result)  # Single line added
    return result

# 4. CLI Commands
@click.command()
@instrument_command  # Single line added
def judge(inputs, profile, out):
    # ... existing CLI logic UNCHANGED ...
    pass
```

**Integration Checklist:**
- ✅ Single import (try/except for safety)
- ✅ Single function call (never blocks, never throws)
- ✅ Zero logic changes
- ✅ Runs identically if instrumentation missing/disabled
- ✅ Fully removable by deleting one line

---

## Feature Flags

### Default (Disabled)

```bash
# Environment variable
export COGNITIVE_OBSERVE=false  # Default

# Or config file
# truthcore.config.yaml
instrumentation:
  enabled: false  # Master switch
```

### Observe-Only (Safe for Production)

```yaml
# truthcore.config.yaml
instrumentation:
  enabled: true

  signals:
    assertions: true
    decisions: true
    overrides: true
    evidence: false     # Skip high-volume signals
    economics: false    # Not yet needed

  sampling_rate: 0.1    # 10% sampling

  output_mode: "log"

  safety:
    queue_size: 10000
    auto_disable_threshold: 10  # Auto-disable after 10 failures
```

### Full Observability

```yaml
instrumentation:
  enabled: true
  signals: {all: true}
  sampling_rate: 1.0
  output_mode: "substrate"  # Send to Cognitive Substrate
```

---

## Outputs (Observe-Only)

### Event Log Format (JSONL)

```jsonl
{"signal_type":"assertion","source":"readiness_engine","claim":"deployment_ready","timestamp":"2026-02-01T12:00:00Z"}
{"signal_type":"decision","actor":"verdict_aggregator","action":"FAIL","score":72,"timestamp":"2026-02-01T12:00:01Z"}
{"signal_type":"override","actor":"user@example.com","original":"FAIL","override":"PASS","rationale":"urgent hotfix","timestamp":"2026-02-01T12:00:02Z"}
```

### Output Modes

| Mode | Destination | Use Case |
|------|-------------|----------|
| `log` | Structured logger | Integrate with existing logs |
| `file` | JSONL file | Append to `/var/log/truthcore/instrumentation.jsonl` |
| `substrate` | Cognitive Substrate | Direct integration (falls back to `log` if unavailable) |
| `null` | Discard | Testing overhead |

---

## Failure & Safety Model

| Scenario | Behavior | Impact |
|----------|----------|--------|
| **Disabled** | Single flag check, immediate return | <1μs |
| **Queue full** | Drop event silently | None |
| **Emission fails** | Log internally, continue | None |
| **10+ failures** | Auto-disable instrumentation | None |
| **Substrate unavailable** | Fallback to logging | None |
| **Config missing** | Default to disabled | None |
| **Import error** | Code runs without instrumentation | None |

**Guarantee:** Telemetry loss is acceptable. Behavioral change is not.

---

## What Remains Unobserved (Intentionally)

The layer does **NOT** observe:
- ❌ Application-internal state (variables, memory)
- ❌ Performance profiling (CPU, GC)
- ❌ Intermediate computation steps
- ❌ User input validation
- ❌ External system internals
- ❌ Future predictions or recommendations
- ❌ Human intent (only stated rationale)
- ❌ Counterfactuals ("what if")

**Why:** Too invasive, high overhead, or out of scope. Observe at boundaries only.

---

## Confirmation: No Enforcement

This layer does **NOT**:
- ❌ Validate assertions
- ❌ Resolve contradictions
- ❌ Enforce policies
- ❌ Block operations
- ❌ Interpret semantic meaning
- ❌ Compute confidence scores
- ❌ Make recommendations
- ❌ Auto-correct deviations

**Role:** Instrumentation observes. Substrate reasons. Application decides.

---

## Implementation Roadmap

| Phase | Timeline | Deliverable | Status |
|-------|----------|-------------|--------|
| **0. Core** | Week 1 | InstrumentationCore, config, health | Not started |
| **1. Adapters** | Week 2 | Boundary adapters, decorators | Not started |
| **2. Integration** | Week 3 | Integrate engines, verdicts, CLI | Not started |
| **3. Outputs** | Week 4 | Log, file, substrate output modes | Not started |
| **4. Hardening** | Week 5 | Load testing, docs, validation | Not started |
| **5. Pilot** | Week 6+ | Deploy to Settler (observe-only) | Not started |

---

## Quick Start (When Ready)

### Step 1: Enable Instrumentation

```yaml
# truthcore.config.yaml
instrumentation:
  enabled: true
  signals: {assertions: true, decisions: true}
  sampling_rate: 0.1
  output_mode: "log"
```

### Step 2: Add Single-Line Integration

```python
# src/truthcore/engines/readiness/__init__.py
from truthcore.instrumentation import instrument_engine

@instrument_engine  # ← Single line added
def run_readiness_engine(inputs, profile):
    # ... existing code unchanged ...
    return results
```

### Step 3: Run and Verify

```bash
# Run with instrumentation
truthctl judge --inputs ./src --profile settler --out ./results

# Check logs for instrumentation events
grep "signal_type" /var/log/truthcore/app.log

# Verify behavior unchanged
diff <(truthctl judge --config old) <(truthctl judge --config new)
# Should be identical
```

### Step 4: View Signals

```bash
# Query instrumentation events
cat /var/log/truthcore/instrumentation.jsonl | jq -c 'select(.signal_type=="override")'

# Analyze patterns
cat /var/log/truthcore/instrumentation.jsonl | jq '.signal_type' | sort | uniq -c
```

---

## Success Metrics

| Metric | Target | How Measured |
|--------|--------|--------------|
| **Overhead (disabled)** | <1μs | Benchmark: 1M no-op calls |
| **Overhead (enabled)** | <100μs | Benchmark: 1M event emissions |
| **Failure rate** | <0.01% | Health monitoring |
| **Event drop rate** | <1% | Queue saturation stats |
| **Production incidents** | 0 | Incident tracking |
| **Behavioral changes** | 0 | Regression test suite |

---

## Example: Full Integration

```python
# src/truthcore/engines/readiness/__init__.py

from truthcore.instrumentation import instrument_engine, get_adapter

@instrument_engine  # Automatically records start/finish
def run_readiness_engine(inputs: dict, profile: str) -> dict:
    """Run readiness verification (UNCHANGED)."""

    # ... existing engine logic ...

    findings = policy_engine.run(inputs)

    # ... existing verdict logic ...

    return results


# src/truthcore/findings.py

class Finding:
    def __init__(self, rule_id: str, severity: Severity, message: str):
        self.rule_id = rule_id
        self.severity = severity
        self.message = message

        # Notify instrumentation (never fails)
        self._notify_instrumentation()

    def _notify_instrumentation(self) -> None:
        """Emit assertion signal. Safe no-op if disabled."""
        try:
            from truthcore.instrumentation import get_adapter
            get_adapter().on_finding_created(self)
        except Exception:
            pass  # Silently ignore all failures


# src/truthcore/verdict/aggregator.py

def aggregate_verdict(findings: list[Finding], policy: Policy) -> VerdictResult:
    """Aggregate findings into verdict (UNCHANGED)."""

    # ... existing aggregation logic ...

    result = VerdictResult(verdict=verdict, value=score, summary=summary)

    # Notify instrumentation (never fails)
    _notify_verdict_decision(result)

    return result

def _notify_verdict_decision(verdict: VerdictResult) -> None:
    """Emit decision signal. Safe no-op if disabled."""
    try:
        from truthcore.instrumentation import get_adapter
        get_adapter().on_verdict_decided(verdict)
    except Exception:
        pass
```

**Result:**
- ✅ Engines emit signals when enabled
- ✅ Engines run identically when disabled
- ✅ Zero behavioral changes
- ✅ Fully removable
- ✅ Safe for production

---

## Common Questions

### Q: Does this change application behavior?
**A:** No. Zero changes to logic, return values, or outcomes.

### Q: What if instrumentation fails?
**A:** Failures are caught internally, never propagated. After 10 failures, auto-disables.

### Q: What if I remove instrumentation?
**A:** Delete decorator/call, application runs identically.

### Q: Does this require Cognitive Substrate?
**A:** No. Works standalone. Substrate is optional consumer.

### Q: What's the performance impact?
**A:** <1μs when disabled (single flag check), <100μs when enabled (async queue push).

### Q: Can I enable/disable at runtime?
**A:** Yes. Set `COGNITIVE_OBSERVE=true/false` or use config file.

### Q: What if I only want some signals?
**A:** Use scoped flags: `signals: {assertions: true, decisions: true, evidence: false}`.

### Q: How do I know it's working?
**A:** Check logs for `signal_type` events, or query `instrumentation.jsonl` file.

---

## Resources

- **Full Design:** `SILENT_INSTRUMENTATION_LAYER.md`
- **Cognitive Substrate:** `COGNITIVE_SUBSTRATE_ARCHITECTURE.md`
- **Implementation:** `src/truthcore/instrumentation/` (not yet created)
- **Tests:** `tests/instrumentation/` (not yet created)

---

**Document Status:** Design Complete, Ready for Implementation
**Safety Level:** Production-safe (observe-only, feature-flagged, auto-disabling)
**Dependencies:** None (optional Cognitive Substrate integration)

---

**Next Actions:**
1. ✅ Design approved → Proceed to implementation
2. ⏳ Implement Phase 0 (InstrumentationCore) → Week 1
3. ⏳ Integrate with engines → Week 2-3
4. ⏳ Deploy to Settler (observe-only) → Week 6
