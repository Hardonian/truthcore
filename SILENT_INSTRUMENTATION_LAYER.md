# Silent Instrumentation Layer
**Design Document v1.0**
**Created:** 2026-02-01
**Status:** Design Phase — Ready for Implementation

---

## Executive Summary

The **Silent Instrumentation Layer** is a zero-impact observability adapter that connects existing TruthCore applications to the Shared Cognitive Substrate without modifying behavior, logic, outcomes, or performance characteristics. It is designed to be **safe to deploy immediately into production systems**.

**Core Principle:** Reality speaks. We listen. We never interrupt.

---

## Design Philosophy

```
┌─────────────────────────────────────────────────┐
│  EXISTING APPLICATION                           │
│  (unchanged behavior, unchanged logic)          │
└──────────────────┬──────────────────────────────┘
                   │
                   │ Events flow outward only →
                   ▼
         ┌─────────────────────┐
         │ INSTRUMENTATION     │ ← Feature-flagged
         │ LAYER (observe-only)│ ← Never blocks
         │                     │ ← Never throws
         └──────────┬──────────┘
                    │
                    │ Telemetry (if enabled) →
                    ▼
         ┌──────────────────────┐
         │ COGNITIVE SUBSTRATE  │ ← May not exist
         │ (optional consumer)  │ ← Never required
         └──────────────────────┘
```

**Guarantees:**
- Application behavior identical with or without instrumentation
- Zero exceptions propagate upward
- Telemetry loss is acceptable, behavioral change is not
- Complete removal leaves no artifacts
- Works even if Cognitive Substrate is disabled or absent

---

## Absolute Constraints (Non-Negotiable)

### 1. Observe-Only
- **No enforcement** — Instrumentation never blocks, rejects, or modifies outcomes
- **No branching** — Application logic never checks instrumentation state
- **No decisions** — Layer records what happened, not what should happen

### 2. Feature-Flagged
- **Master flag** — `COGNITIVE_OBSERVE` (default: `false`)
- **Scoped flags** — Per-signal-type granularity
- **Runtime toggle** — No redeploy required to enable/disable
- **Graceful no-op** — When disabled, single boolean check exits immediately

### 3. Zero Hard Failures
- **Try-catch all** — Every instrumentation call wrapped in error handler
- **Drop, don't throw** — Telemetry failures logged internally only
- **Never propagate** — Exceptions absorbed at instrumentation boundary
- **Degrade gracefully** — Auto-disable on repeated failures

### 4. No Semantic Assumptions
- **Record what exists** — Not what "should" exist
- **Capture raw signals** — Not interpreted meanings
- **Allow contradictions** — Multiple sources may conflict
- **Timestamp everything** — Let future analysis resolve

### 5. Minimal Overhead
- **<100μs per event** when enabled
- **<1μs per event** when disabled (single flag check)
- **Async emission** — Never block caller
- **Bounded queues** — Drop old events if queue full
- **Sampling support** — Configurable sampling rates

### 6. No Refactors Required
- **Attach at boundaries** — API entry/exit, engine start/finish
- **Use existing hooks** — Leverage decorators, context managers, signals
- **Backward compatible** — Works with all existing code
- **Optional import** — If instrumentation module missing, code runs unchanged

### 7. Fully Removable
- **No persistence dependencies** — Application state never relies on instrumentation
- **No schema changes** — Existing data models unchanged
- **Clean uninstall** — Remove imports, application runs identically
- **No side effects** — Removal is instant and complete

---

## What This Layer Observes

The instrumentation layer captures **raw signals** about system behavior without interpreting them:

### 1. Assertions Being Made
**What:** Claims the system is making (explicit or implicit)

**Examples:**
- Engine produces Finding with severity=BLOCKER
- Verdict aggregator returns PASS with score=95
- Policy evaluator asserts "coverage >= 80%"
- Human marks deployment as "ready to ship"

**Captured:**
```python
{
  "signal_type": "assertion",
  "source": "readiness_engine",
  "claim": "deployment_ready",
  "claim_value": True,
  "confidence_hint": 0.95,  # If available
  "timestamp": "2026-02-01T12:00:00.000000Z",
  "context": {"run_id": "abc123", "profile": "settler"}
}
```

### 2. Evidence Inputs
**What:** Data sources, signals, heuristics used in reasoning

**Examples:**
- File read during policy evaluation
- API response from external service
- Git commit metadata
- Build system outputs
- Test results

**Captured:**
```python
{
  "signal_type": "evidence",
  "evidence_type": "file_read",
  "source": "policy_engine",
  "content_hash": "sha256:abc123...",
  "size_bytes": 4096,
  "timestamp": "2026-02-01T12:00:01.000000Z",
  "context": {"file_path": "src/main.py"}
}
```

### 3. Belief Changes
**What:** Confidence shifts, recalculations, verdict changes

**Examples:**
- Verdict changes from PASS to FAIL
- Confidence score drops from 95 to 72
- Readiness status transitions
- Override changes belief

**Captured:**
```python
{
  "signal_type": "belief_change",
  "source": "verdict_aggregator",
  "subject": "deployment_readiness",
  "old_value": {"verdict": "PASS", "score": 95},
  "new_value": {"verdict": "FAIL", "score": 72},
  "trigger": "new_blocker_finding",
  "timestamp": "2026-02-01T12:00:02.000000Z"
}
```

### 4. Semantic Usage
**What:** How labels, metrics, statuses are actually used in practice

**Examples:**
- "deployment_ready" defined as score >= 90 in code
- "high severity" mapped to blocker vs. critical
- "coverage" computed as line-based vs. branch-based
- Status transitions (draft → ready → shipped)

**Captured:**
```python
{
  "signal_type": "semantic_usage",
  "term": "deployment_ready",
  "definition_source": "settler.config",
  "actual_usage": "score >= 90 and blockers == 0",
  "usage_context": "verdict_aggregation",
  "timestamp": "2026-02-01T12:00:03.000000Z"
}
```

### 5. Decisions Taken
**What:** Actions chosen by system or human

**Examples:**
- System verdict: FAIL → block deployment
- Human verdict: PASS → approve deployment
- Policy action: WARN → log but continue
- Cache decision: HIT → reuse prior result

**Captured:**
```python
{
  "signal_type": "decision",
  "decision_type": "system",
  "actor": "verdict_aggregator",
  "action": "block_deployment",
  "rationale": ["blocker_severity_found", "score_below_threshold"],
  "inputs": ["finding_ids: [...]", "threshold: 90"],
  "timestamp": "2026-02-01T12:00:04.000000Z"
}
```

### 6. Overrides and Manual Interventions
**What:** Human choices that contradict system recommendations

**Examples:**
- Ship despite FAIL verdict
- Override policy violation
- Manual status change
- Force cache bypass

**Captured:**
```python
{
  "signal_type": "override",
  "override_type": "human",
  "actor": "user@example.com",
  "original_decision": "FAIL",
  "override_decision": "PASS",
  "rationale": "urgent hotfix, risk accepted",
  "scope": "deployment_xyz",
  "authority": "team_lead",
  "timestamp": "2026-02-01T12:00:05.000000Z"
}
```

### 7. Economic Signals
**What:** Cost, risk, budget pressure, resource usage

**Examples:**
- Token usage during AI agent run
- Time spent in verification
- Cache storage size
- API call costs
- Human time invested

**Captured:**
```python
{
  "signal_type": "economic",
  "metric": "token_usage",
  "amount": 1500,
  "unit": "tokens",
  "cost_estimate": 0.015,  # USD
  "currency": "USD",
  "applies_to": "run_abc123",
  "timestamp": "2026-02-01T12:00:06.000000Z"
}
```

### 8. Policy References
**What:** Which policies consulted, even if unenforced

**Examples:**
- Policy evaluated but enforcement=observe
- Policy skipped due to flag
- Policy matched but overridden
- Policy version mismatch detected

**Captured:**
```python
{
  "signal_type": "policy_reference",
  "policy_id": "coverage.min",
  "policy_version": "2.1.0",
  "evaluation_result": "FAIL",
  "enforcement_mode": "observe",
  "action_taken": "logged_only",
  "timestamp": "2026-02-01T12:00:07.000000Z"
}
```

---

## Integration Shape

### Architecture

```python
# LAYER 1: Instrumentation Core (always present, may be dormant)
class InstrumentationCore:
    """
    Zero-overhead event emission layer.

    When disabled: Single flag check, immediate return
    When enabled: Async event queue, non-blocking emission
    """

    def __init__(self, config: InstrumentationConfig):
        self._enabled = config.master_flag  # COGNITIVE_OBSERVE
        self._queue = BoundedQueue(maxsize=10000) if self._enabled else None
        self._emitter = AsyncEmitter() if self._enabled else None
        self._failure_count = 0
        self._auto_disable_threshold = 10

    def emit(self, signal: dict) -> None:
        """
        Emit a signal. Never raises exceptions.

        Guarantees:
        - If disabled: <1μs overhead (single flag check)
        - If enabled: <100μs overhead (queue push)
        - Never blocks caller
        - Never propagates errors
        """
        if not self._enabled:
            return  # Fast path: immediate exit

        try:
            # Add timestamp if missing
            if "timestamp" not in signal:
                signal["timestamp"] = utc_now_iso()

            # Non-blocking queue push (drops if full)
            if not self._queue.try_put(signal, timeout=0):
                # Queue full, drop event silently
                self._log_internal("event_dropped", "queue_full")
                return

        except Exception as e:
            # NEVER propagate exceptions upward
            self._handle_failure(e)

    def _handle_failure(self, exc: Exception) -> None:
        """Handle instrumentation failure internally."""
        self._failure_count += 1
        self._log_internal("instrumentation_error", str(exc))

        # Auto-disable after repeated failures
        if self._failure_count >= self._auto_disable_threshold:
            self._enabled = False
            self._log_internal("auto_disabled", "too_many_failures")


# LAYER 2: Boundary Adapters (attach at system boundaries)
class BoundaryAdapter:
    """
    Attaches to system boundaries to capture events.

    Uses decorators, context managers, and hooks.
    Never modifies behavior.
    """

    def __init__(self, core: InstrumentationCore):
        self.core = core

    def on_engine_start(self, engine_name: str, inputs: dict) -> None:
        """Called when an engine begins execution."""
        self.core.emit({
            "signal_type": "engine_lifecycle",
            "event": "engine_start",
            "engine": engine_name,
            "inputs_hash": content_hash(inputs),
        })

    def on_engine_finish(self, engine_name: str, outputs: dict, duration_ms: float) -> None:
        """Called when an engine completes execution."""
        self.core.emit({
            "signal_type": "engine_lifecycle",
            "event": "engine_finish",
            "engine": engine_name,
            "outputs_hash": content_hash(outputs),
            "duration_ms": duration_ms,
        })

    def on_finding_created(self, finding: Finding) -> None:
        """Called when a Finding is created."""
        self.core.emit({
            "signal_type": "assertion",
            "source": finding.rule_id,
            "claim": finding.message,
            "severity": finding.severity.value,
            "confidence_hint": getattr(finding, "confidence", None),
        })

    def on_verdict_decided(self, verdict: VerdictResult) -> None:
        """Called when a Verdict is computed."""
        self.core.emit({
            "signal_type": "decision",
            "decision_type": "system",
            "actor": "verdict_aggregator",
            "action": verdict.verdict.value,
            "score": verdict.value,
            "rationale": verdict.summary,
        })

    def on_human_override(self, original: str, override: str, actor: str, rationale: str) -> None:
        """Called when a human overrides a system decision."""
        self.core.emit({
            "signal_type": "override",
            "override_type": "human",
            "actor": actor,
            "original_decision": original,
            "override_decision": override,
            "rationale": rationale,
        })


# LAYER 3: Application Integration (minimal changes to existing code)
def integrate_with_existing_engine(engine_fn):
    """
    Decorator that instruments an engine function.

    Safe to apply even if instrumentation is disabled.
    """
    @functools.wraps(engine_fn)
    def wrapper(*args, **kwargs):
        # Optional import: if instrumentation module missing, this is a no-op
        try:
            from truthcore.instrumentation import get_adapter
            adapter = get_adapter()
        except (ImportError, AttributeError):
            # Instrumentation not available, run normally
            return engine_fn(*args, **kwargs)

        engine_name = engine_fn.__name__
        start_time = time.perf_counter()

        # Record start (never blocks, never throws)
        adapter.on_engine_start(engine_name, kwargs)

        try:
            # Execute original function (unchanged)
            result = engine_fn(*args, **kwargs)

            # Record finish (never blocks, never throws)
            duration_ms = (time.perf_counter() - start_time) * 1000
            adapter.on_engine_finish(engine_name, result, duration_ms)

            return result

        except Exception as e:
            # Application exception, not instrumentation
            # Record failure signal, then re-raise unchanged
            adapter.on_engine_finish(engine_name, {"error": str(e)},
                                    (time.perf_counter() - start_time) * 1000)
            raise  # Original exception propagates unchanged

    return wrapper
```

### Attachment Points (System Boundaries)

The instrumentation layer attaches at **boundaries**, not deep within logic:

#### 1. Engine Entry/Exit
```python
# src/truthcore/engines/readiness/__init__.py

# BEFORE (no instrumentation):
def run_readiness_engine(inputs: dict, profile: str) -> dict:
    # ... engine logic ...
    return results

# AFTER (with instrumentation):
from truthcore.instrumentation import instrument_engine

@instrument_engine  # Single line added, behavior unchanged
def run_readiness_engine(inputs: dict, profile: str) -> dict:
    # ... engine logic UNCHANGED ...
    return results
```

#### 2. Finding Creation
```python
# src/truthcore/findings.py

class Finding:
    def __init__(self, rule_id: str, severity: Severity, message: str, **kwargs):
        self.rule_id = rule_id
        self.severity = severity
        self.message = message
        # ... existing fields ...

        # Instrumentation hook (only if available)
        self._notify_instrumentation()

    def _notify_instrumentation(self) -> None:
        """Notify instrumentation layer. Never fails."""
        try:
            from truthcore.instrumentation import get_adapter
            get_adapter().on_finding_created(self)
        except Exception:
            pass  # Silently ignore if instrumentation unavailable
```

#### 3. Verdict Aggregation
```python
# src/truthcore/verdict/aggregator.py

def aggregate_verdict(findings: list[Finding], policy: Policy) -> VerdictResult:
    # ... existing aggregation logic UNCHANGED ...
    result = VerdictResult(verdict=verdict, value=score, ...)

    # Instrumentation notification (never throws)
    _notify_verdict_decision(result)

    return result

def _notify_verdict_decision(verdict: VerdictResult) -> None:
    """Notify instrumentation. Safe no-op if disabled."""
    try:
        from truthcore.instrumentation import get_adapter
        get_adapter().on_verdict_decided(verdict)
    except Exception:
        pass
```

#### 4. CLI Command Boundaries
```python
# src/truthcore/cli.py

@click.command()
@instrument_command  # Decorator records command start/finish
def judge(inputs: str, profile: str, out: str) -> None:
    # ... existing CLI logic UNCHANGED ...
    pass
```

#### 5. Policy Evaluation
```python
# src/truthcore/policy/engine.py

def evaluate_policy(rule: PolicyRule, context: dict) -> PolicyResult:
    result = _evaluate_rule_internal(rule, context)

    # Record policy reference (even if unenforced)
    _record_policy_usage(rule, result)

    return result

def _record_policy_usage(rule: PolicyRule, result: PolicyResult) -> None:
    try:
        from truthcore.instrumentation import get_adapter
        get_adapter().on_policy_evaluated(rule, result)
    except Exception:
        pass
```

#### 6. Cache Operations
```python
# src/truthcore/cache.py

def cache_lookup(key: str) -> CacheResult:
    result = _internal_lookup(key)

    # Record cache decision
    _record_cache_decision(key, result.hit)

    return result

def _record_cache_decision(key: str, hit: bool) -> None:
    try:
        from truthcore.instrumentation import get_adapter
        get_adapter().on_cache_decision(key, hit)
    except Exception:
        pass
```

### Integration Checklist

For each boundary point:
- ✅ **Single import statement** added (try/except for safety)
- ✅ **Single function call** added (never blocks, never throws)
- ✅ **Zero changes** to logic, conditionals, or return values
- ✅ **Runs identically** if instrumentation module is missing
- ✅ **Runs identically** if instrumentation is disabled
- ✅ **Fully removable** by deleting single line

---

## Feature Flag Strategy

### Master Flag

```bash
# Environment variable (runtime toggle)
export COGNITIVE_OBSERVE=false  # Default: disabled

# Or in config file
# truthcore.config.yaml
instrumentation:
  enabled: false  # Master switch
```

### Scoped Flags

```yaml
# truthcore.config.yaml
instrumentation:
  enabled: true  # Master switch

  # Per-signal-type flags
  signals:
    assertions: true       # Capture assertion signals
    evidence: true         # Capture evidence signals
    beliefs: true          # Capture belief change signals
    decisions: true        # Capture decision signals
    overrides: true        # Capture override signals
    economics: false       # Skip economic signals (example)
    policies: true         # Capture policy references
    semantics: false       # Skip semantic usage (example)

  # Sampling
  sampling_rate: 1.0       # 1.0 = 100%, 0.1 = 10%

  # Safety limits
  queue_size: 10000        # Max events in queue
  auto_disable_threshold: 10  # Auto-disable after N failures

  # Output
  output_mode: "log"       # Options: log, file, substrate, null
  output_path: "/var/log/truthcore/instrumentation.jsonl"
```

### Runtime Toggling

```python
# Toggle at runtime (no redeploy)
from truthcore.instrumentation import set_enabled

# Disable globally
set_enabled(False)

# Enable with scoped flags
set_enabled(True, signals={"assertions": True, "decisions": True})

# Adjust sampling rate
set_sampling_rate(0.1)  # 10% sampling
```

### Graceful No-Op Behavior

```python
class InstrumentationCore:
    def emit(self, signal: dict) -> None:
        # Fast path when disabled
        if not self._enabled:
            return  # <1μs overhead

        # Fast path when signal type disabled
        signal_type = signal.get("signal_type")
        if not self._is_signal_enabled(signal_type):
            return  # <1μs overhead

        # Fast path when sampled out
        if random.random() > self._sampling_rate:
            return  # <5μs overhead

        # Only now do actual work
        self._do_emit(signal)
```

---

## Outputs (Observe-Only)

The instrumentation layer emits **structured events** without blocking execution:

### Event Log Format

```jsonl
{"signal_type":"assertion","source":"readiness_engine","claim":"deployment_ready","timestamp":"2026-02-01T12:00:00.000000Z","run_id":"abc123"}
{"signal_type":"evidence","evidence_type":"file_read","source":"policy_engine","content_hash":"sha256:def456","timestamp":"2026-02-01T12:00:01.000000Z"}
{"signal_type":"decision","decision_type":"system","actor":"verdict_aggregator","action":"FAIL","score":72,"timestamp":"2026-02-01T12:00:02.000000Z"}
{"signal_type":"override","override_type":"human","actor":"user@example.com","original_decision":"FAIL","override_decision":"PASS","timestamp":"2026-02-01T12:00:03.000000Z"}
```

### Output Modes

#### 1. Log Mode (Default)
```yaml
output_mode: "log"
# Emits to structured logger (structlog)
# Integrates with existing logging infrastructure
```

#### 2. File Mode
```yaml
output_mode: "file"
output_path: "/var/log/truthcore/instrumentation.jsonl"
# Appends to JSONL file (one event per line)
```

#### 3. Substrate Mode
```yaml
output_mode: "substrate"
# Sends events directly to Cognitive Substrate (if enabled)
# Falls back to "log" if substrate unavailable
```

#### 4. Null Mode
```yaml
output_mode: "null"
# Discards all events (for testing overhead)
```

### What It Must NOT Do

❌ **Never block execution** — All emissions are async
❌ **Never alter return values** — Original results pass through unchanged
❌ **Never modify persistence** — Application state is untouched
❌ **Never change user-visible outcomes** — UI, API responses identical
❌ **Never create hard dependencies** — Application runs without instrumentation
❌ **Never retry or buffer persistently** — Drop events rather than block
❌ **Never assume correctness** — Record what happened, not what should happen

---

## Failure & Safety Model

### Failure Handling

```python
class InstrumentationCore:
    def _handle_failure(self, exc: Exception) -> None:
        """
        Handle instrumentation failure.

        Strategy:
        1. Log internally (never propagate)
        2. Increment failure counter
        3. Auto-disable if threshold exceeded
        4. Emit health signal (if possible)
        """
        self._failure_count += 1

        # Internal logging only (not via main logger to avoid recursion)
        self._internal_log.append({
            "event": "instrumentation_failure",
            "error": str(exc),
            "count": self._failure_count,
            "timestamp": utc_now_iso(),
        })

        # Auto-disable after repeated failures
        if self._failure_count >= self._auto_disable_threshold:
            self._enabled = False
            self._internal_log.append({
                "event": "auto_disabled",
                "reason": "failure_threshold_exceeded",
                "threshold": self._auto_disable_threshold,
                "timestamp": utc_now_iso(),
            })
```

### Safety Guarantees

| Scenario | Behavior | Impact on App |
|----------|----------|---------------|
| **Instrumentation disabled** | No-op (single flag check) | <1μs overhead |
| **Queue full** | Drop event silently | Zero impact |
| **Emission fails** | Log internally, continue | Zero impact |
| **Repeated failures** | Auto-disable instrumentation | Zero impact |
| **Substrate unavailable** | Fallback to logging | Zero impact |
| **Config missing** | Use safe defaults (disabled) | Zero impact |
| **Import error** | Code runs without instrumentation | Zero impact |
| **Exception in handler** | Caught, logged, never propagated | Zero impact |

### Health Monitoring

```python
class InstrumentationHealth:
    """
    Self-monitoring for instrumentation layer.

    Tracks:
    - Events emitted vs. dropped
    - Failure rate
    - Auto-disable events
    - Queue saturation
    """

    def get_health_status(self) -> dict:
        return {
            "enabled": self._core._enabled,
            "events_emitted": self._events_emitted,
            "events_dropped": self._events_dropped,
            "failures": self._core._failure_count,
            "queue_depth": self._core._queue.qsize() if self._core._queue else 0,
            "auto_disabled": self._core._failure_count >= self._core._auto_disable_threshold,
        }
```

---

## What Remains Intentionally Unobserved

The instrumentation layer is **deliberately limited** in scope:

### 1. Application-Internal State
**Not Observed:** Variables, memory, internal caches, threads
**Why:** Too invasive, high overhead, breaks abstraction
**Alternative:** Observe at boundaries (inputs/outputs) only

### 2. Performance Profiling
**Not Observed:** CPU usage, memory allocation, GC events
**Why:** Dedicated profiling tools exist (py-spy, memray)
**Alternative:** Use external profilers when needed

### 3. Intermediate Computation Steps
**Not Observed:** Loop iterations, function calls, stack traces
**Why:** Too noisy, high overhead, not deterministic
**Alternative:** Observe start/finish of engines only

### 4. User Input Validation
**Not Observed:** Keystrokes, mouse events, form submissions
**Why:** Privacy concerns, not relevant to system reasoning
**Alternative:** Observe final decisions only

### 5. External System Internals
**Not Observed:** Third-party API internals, database queries
**Why:** Out of scope, not observable without cooperation
**Alternative:** Observe request/response at boundary

### 6. Future Predictions
**Not Observed:** What *will* happen, what *should* happen
**Why:** Instrumentation records reality, not speculation
**Alternative:** Cognitive Substrate interprets signals

### 7. Human Intent
**Not Observed:** Why a human made a choice (internal reasoning)
**Why:** Cannot be observed, only inferred
**Alternative:** Record stated rationale (if provided)

### 8. Counterfactuals
**Not Observed:** What would have happened if...
**Why:** Cannot observe alternate realities
**Alternative:** Simulation layer (separate from instrumentation)

---

## Confirmation: No Enforcement, No Decisions

### Explicit Non-Capabilities

This layer does **NOT**:

- ❌ Validate assertions for correctness
- ❌ Resolve contradictions between signals
- ❌ Enforce policies or constraints
- ❌ Block operations based on observations
- ❌ Interpret semantic meaning
- ❌ Compute confidence scores
- ❌ Make recommendations
- ❌ Auto-correct deviations
- ❌ Reject invalid inputs
- ❌ Rate-limit based on cost
- ❌ Require schema compliance
- ❌ Perform access control

### Role Separation

```
┌─────────────────────────────────────────────────┐
│  APPLICATION                                    │
│  • Makes decisions                              │
│  • Enforces policies                            │
│  • Validates inputs                             │
│  • Returns verdicts                             │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
         ┌─────────────────────┐
         │ INSTRUMENTATION     │
         │ • Observes only     │
         │ • Records signals   │
         │ • Never decides     │
         │ • Never enforces    │
         └──────────┬──────────┘
                    │
                    ▼
         ┌──────────────────────┐
         │ COGNITIVE SUBSTRATE  │
         │ • Interprets signals │
         │ • Forms beliefs      │
         │ • Detects patterns   │
         │ • (May) enforce      │ ← Separate concern
         └──────────────────────┘
```

**Key Insight:** Instrumentation observes. Substrate reasons. Application decides.

---

## Implementation Roadmap

### Phase 0: Core Foundation (Week 1)

**Deliverables:**
1. **InstrumentationCore** (`src/truthcore/instrumentation/core.py`)
   - Master flag checking
   - Bounded queue
   - Async emitter
   - Failure handling

2. **Configuration** (`src/truthcore/instrumentation/config.py`)
   - Flag definitions
   - Scoped signal types
   - Sampling configuration
   - Output modes

3. **Health Monitoring** (`src/truthcore/instrumentation/health.py`)
   - Event counters
   - Failure tracking
   - Auto-disable logic

**Acceptance:**
- ✅ <1μs overhead when disabled
- ✅ Never throws exceptions upward
- ✅ Auto-disables after failures
- ✅ All tests pass

### Phase 1: Boundary Adapters (Week 2)

**Deliverables:**
1. **BoundaryAdapter** (`src/truthcore/instrumentation/adapters.py`)
   - Engine lifecycle hooks
   - Finding creation hooks
   - Verdict decision hooks
   - Policy evaluation hooks

2. **Decorators** (`src/truthcore/instrumentation/decorators.py`)
   - `@instrument_engine`
   - `@instrument_command`
   - `@instrument_function` (generic)

**Acceptance:**
- ✅ Decorators are optional (safe no-op if missing)
- ✅ Zero behavior changes to instrumented code
- ✅ All existing tests pass

### Phase 2: Application Integration (Week 3)

**Deliverables:**
1. **Engine Integration**
   - Add `@instrument_engine` to readiness, reconciliation, agent_trace
   - Test with instrumentation enabled/disabled

2. **Verdict Integration**
   - Add `_notify_verdict_decision()` to aggregator
   - Test verdict behavior unchanged

3. **CLI Integration**
   - Add `@instrument_command` to judge, recon, trace
   - Test CLI behavior unchanged

**Acceptance:**
- ✅ All engines emit signals when enabled
- ✅ All engines work identically when disabled
- ✅ No performance degradation
- ✅ All tests pass

### Phase 3: Output Modes (Week 4)

**Deliverables:**
1. **Log Output** (`src/truthcore/instrumentation/outputs/log.py`)
   - Structured logging integration
   - Sampling support

2. **File Output** (`src/truthcore/instrumentation/outputs/file.py`)
   - JSONL appending
   - Log rotation support

3. **Substrate Output** (`src/truthcore/instrumentation/outputs/substrate.py`)
   - Direct substrate integration
   - Fallback to logging

**Acceptance:**
- ✅ All output modes work correctly
- ✅ Graceful degradation on failure
- ✅ No blocking I/O in hot path

### Phase 4: Validation & Hardening (Week 5)

**Deliverables:**
1. **Load Testing**
   - High-volume event emission
   - Queue saturation testing
   - Failure injection testing

2. **Documentation**
   - Integration guide
   - Configuration reference
   - Troubleshooting guide

3. **Example Instrumentation**
   - Sample signals for each type
   - Example queries/analysis

**Acceptance:**
- ✅ Handles 10,000 events/sec without blocking
- ✅ Auto-disables gracefully under load
- ✅ Documentation complete

### Phase 5: Pilot Deployment (Week 6+)

**Deliverables:**
1. **Settler Integration**
   - Enable instrumentation in Settler
   - Collect 1 week of signals
   - Analyze signal quality

2. **Iteration**
   - Adjust sampling rates
   - Tune queue sizes
   - Refine signal schemas

**Acceptance:**
- ✅ Zero production incidents
- ✅ No performance degradation
- ✅ Signals flowing to substrate (if enabled)
- ✅ Actionable insights generated

---

## Configuration Reference

### Minimal Configuration (Disabled)

```yaml
# truthcore.config.yaml
instrumentation:
  enabled: false  # Default
```

### Observe-Only Configuration (Safe for Production)

```yaml
# truthcore.config.yaml
instrumentation:
  enabled: true

  signals:
    assertions: true
    decisions: true
    overrides: true
    evidence: false      # Skip for now (high volume)
    economics: false     # Not yet needed

  sampling_rate: 0.1     # 10% sampling to reduce load

  output_mode: "log"

  safety:
    queue_size: 10000
    auto_disable_threshold: 10
```

### Full Observability Configuration

```yaml
# truthcore.config.yaml
instrumentation:
  enabled: true

  signals:
    assertions: true
    evidence: true
    beliefs: true
    decisions: true
    overrides: true
    economics: true
    policies: true
    semantics: true

  sampling_rate: 1.0     # 100% capture

  output_mode: "substrate"  # Send to cognitive substrate
  fallback_mode: "file"
  output_path: "/var/log/truthcore/instrumentation.jsonl"

  safety:
    queue_size: 50000
    auto_disable_threshold: 20
```

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Overhead (disabled)** | <1μs per event | Benchmark comparison |
| **Overhead (enabled)** | <100μs per event | Benchmark comparison |
| **Failure rate** | <0.01% | Health monitoring |
| **Event drop rate** | <1% | Queue saturation stats |
| **Production incidents** | 0 | Incident tracking |
| **Behavioral changes** | 0 | Regression test suite |
| **Signal quality** | 95%+ actionable | Manual review |

---

## Summary

### What This Layer Is

A **transparent observability adapter** that:
- Captures raw signals about system behavior
- Attaches at system boundaries (engines, verdicts, CLI)
- Emits events without blocking or failing
- Works even if Cognitive Substrate is disabled
- Adds <1μs overhead when disabled, <100μs when enabled

### What This Layer Is Not

Not:
- An enforcement mechanism
- A decision-making system
- A performance profiler
- A correctness validator
- A required dependency

### Key Principles

1. **Observe, don't interfere** — Reality speaks, we listen
2. **Drop data, never block** — Telemetry loss is acceptable, behavioral change is not
3. **Fail internally, never propagate** — Instrumentation errors stay contained
4. **Attach at boundaries, not within** — Minimal invasiveness
5. **Feature-flag everything** — Default to off, enable incrementally
6. **Zero required infrastructure** — Works standalone or with substrate

### Next Steps

1. ✅ **This design approved** → Proceed to Phase 0
2. ⏳ **Implement InstrumentationCore** → Week 1
3. ⏳ **Integrate with engines** → Week 2-3
4. ⏳ **Deploy to Settler (observe-only)** → Week 6

---

**Design Status:** Complete, Ready for Implementation
**Risk Level:** Minimal (observe-only, feature-flagged, auto-disabling)
**Deployment Safety:** Safe for immediate production use (default: disabled)

---

**Document Version:** 1.0
**Last Updated:** 2026-02-01
**Author:** Claude Sonnet (Principal Systems Architect)
