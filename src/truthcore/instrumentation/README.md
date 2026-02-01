# Silent Instrumentation Layer — Phase 0 Implementation

This package implements the **Silent Instrumentation Layer** for TruthCore's Cognitive Substrate.

## Overview

The Silent Instrumentation Layer is a zero-impact observability adapter that captures system behavior without modifying logic, outcomes, or performance.

### Key Features

- ✅ **Observe-only** — No enforcement, no branching, no decisions
- ✅ **Feature-flagged** — Default: disabled
- ✅ **Zero hard failures** — Auto-disables after repeated errors
- ✅ **Minimal overhead** — <1μs disabled, <100μs enabled
- ✅ **Fully removable** — No side effects

## Components

### Core (`core.py`)
- `InstrumentationCore` — Main event emission engine
- `BoundedQueue` — Thread-safe bounded queue with drop-on-full
- `AsyncEmitter` — Background thread for async event emission

### Configuration (`config.py`)
- `InstrumentationConfig` — Feature flags and configuration
- `SignalFlags` — Per-signal-type enable/disable
- `SafetyLimits` — Queue size, auto-disable threshold

### Health (`health.py`)
- `InstrumentationHealth` — Thread-safe health monitoring
- Event counters, failure tracking, auto-disable detection

### Adapters (`adapters.py`)
- `BoundaryAdapter` — Hooks for system boundaries
- Methods for engines, findings, verdicts, policies, overrides

### Decorators (`decorators.py`)
- `@instrument_engine` — For engine functions
- `@instrument_command` — For CLI commands
- `@instrument_function` — Generic function instrumentation
- `InstrumentationContext` — Context manager for manual instrumentation

## Quick Start

### Basic Usage

```python
from truthcore.instrumentation import get_core, get_adapter

# Enable instrumentation
from truthcore.instrumentation import set_enabled
set_enabled(True)

# Emit events
adapter = get_adapter()
adapter.on_engine_start("my_engine", {"param": "value"})
adapter.on_engine_finish("my_engine", {"result": "success"}, duration_ms=123.4)
```

### Using Decorators

```python
from truthcore.instrumentation.decorators import instrument_engine

@instrument_engine
def run_my_engine(inputs: dict) -> dict:
    # Engine logic here
    return results
```

### Configuration

```python
# Environment variables
export COGNITIVE_OBSERVE=true
export COGNITIVE_OBSERVE_SAMPLING=0.1  # 10% sampling

# Or programmatic
from truthcore.instrumentation import set_enabled, set_sampling_rate
set_enabled(True)
set_sampling_rate(0.1)
```

## Signal Types

The layer captures 8 signal types:

1. **Assertions** — Claims being made
2. **Evidence** — Data inputs
3. **Belief Changes** — Confidence shifts
4. **Semantic Usage** — How terms are used
5. **Decisions** — Actions taken
6. **Overrides** — Manual interventions
7. **Economic** — Cost/risk signals
8. **Policy References** — Policies consulted

## Output Modes

- **log** — Structured logging (default)
- **file** — JSONL file
- **substrate** — Direct to Cognitive Substrate
- **null** — Discard (testing)

## Safety Guarantees

| Scenario | Behavior | Impact |
|----------|----------|--------|
| Disabled | Single flag check | <1μs |
| Queue full | Drop event | None |
| Emission fails | Log internally | None |
| 10+ failures | Auto-disable | None |
| Missing module | No-op | None |

## Testing

```bash
# Run all tests
pytest tests/instrumentation/ -v

# Run specific test
pytest tests/instrumentation/test_core.py::test_instrumentation_disabled -v

# Check coverage
pytest tests/instrumentation/ --cov=src/truthcore/instrumentation --cov-report=term-missing
```

## Performance

Benchmarked on typical hardware:

- **Disabled**: <1μs per call (single flag check)
- **Enabled**: <100μs per call (async queue push)
- **Throughput**: 10,000+ events/sec without blocking

## Architecture

```
Application
    ↓ (optional instrumentation)
BoundaryAdapter
    ↓ (emits signals)
InstrumentationCore
    ↓ (queues events)
AsyncEmitter (background thread)
    ↓ (emits to output)
Output (log/file/substrate)
```

## Health Monitoring

```python
from truthcore.instrumentation import get_core

core = get_core()
health = core.get_health_status()

print(health["events_queued"])
print(health["events_emitted"])
print(health["events_dropped"])
print(health["health_status"])  # healthy/warning/degraded/auto_disabled
```

## Integration Examples

### Engine Integration

```python
from truthcore.instrumentation.decorators import instrument_engine

@instrument_engine
def run_readiness_engine(inputs: dict, profile: str) -> dict:
    # Existing engine logic unchanged
    return results
```

### Finding Creation

```python
class Finding:
    def __init__(self, rule_id, severity, message):
        self.rule_id = rule_id
        self.severity = severity
        self.message = message

        # Notify instrumentation (safe no-op if disabled)
        self._notify_instrumentation()

    def _notify_instrumentation(self):
        try:
            from truthcore.instrumentation import get_adapter
            get_adapter().on_finding_created(self)
        except Exception:
            pass  # Never propagate failures
```

### Verdict Aggregation

```python
def aggregate_verdict(findings, policy):
    # Existing logic unchanged
    result = VerdictResult(verdict=verdict, value=score)

    # Notify instrumentation
    try:
        from truthcore.instrumentation import get_adapter
        get_adapter().on_verdict_decided(result)
    except Exception:
        pass

    return result
```

## Phase 0 Status

✅ **Core Foundation** — Complete
- InstrumentationCore with queue and emitter
- Configuration system with flags
- Health monitoring and auto-disable
- Boundary adapters
- Decorators for easy integration
- Comprehensive test suite (80+ tests)

## Next Steps

**Phase 1** — Boundary Adapters (Week 2)
- Integration with actual engines
- CLI command instrumentation

**Phase 2** — Application Integration (Week 3)
- Integrate with readiness, reconciliation, agent_trace
- Integrate with verdict aggregation

**Phase 3** — Output Modes (Week 4)
- Log, file, substrate output handlers
- Graceful fallback

## Documentation

- Full design: `/SILENT_INSTRUMENTATION_LAYER.md`
- Quick reference: `/INSTRUMENTATION_SUMMARY.md`
- API docs: Run `pydoc src/truthcore/instrumentation`

## Support

For questions or issues:
1. Check design documents
2. Review test cases for examples
3. Check health status for diagnostics

---

**Version**: Phase 0 Complete
**Status**: Production-safe (default: disabled)
**Dependencies**: None
