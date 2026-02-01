"""Integration tests for instrumentation layer."""

import time
import pytest

from truthcore.instrumentation import (
    get_config,
    get_core,
    get_adapter,
    set_enabled,
    set_sampling_rate,
    reset,
)
from truthcore.instrumentation.config import InstrumentationConfig
from truthcore.instrumentation.decorators import instrument_engine


def test_full_integration_flow():
    """Test full instrumentation flow end-to-end."""
    reset()

    # Start disabled
    config = get_config()
    assert config.enabled is False

    # Enable
    set_enabled(True)

    # Get components
    core = get_core()
    adapter = get_adapter()

    # Emit various signals
    adapter.on_engine_start("test_engine", {"param": "value"})
    adapter.on_finding_created(MockFinding())
    adapter.on_verdict_decided(MockVerdict())
    adapter.on_human_override(
        original_decision="FAIL",
        override_decision="PASS",
        actor="user",
        rationale="test"
    )

    time.sleep(0.1)

    # Check health
    health = core.get_health_status()
    assert health["enabled"] is True
    assert health["events_queued"] >= 4
    assert health["health_status"] == "healthy"

    # Shutdown
    core.shutdown()
    reset()


def test_integration_with_decorator():
    """Test integration using decorators."""
    reset()
    set_enabled(True)

    @instrument_engine
    def test_workflow(x: int, y: int) -> dict:
        # Simulate engine work
        adapter = get_adapter()

        # Record finding
        adapter.on_finding_created(MockFinding())

        # Record verdict
        adapter.on_verdict_decided(MockVerdict())

        return {"result": x + y}

    result = test_workflow(x=10, y=20)

    assert result == {"result": 30}

    # Check instrumentation
    core = get_core()
    time.sleep(0.1)

    stats = core.health.get_stats()
    # Should have: engine_start, finding, verdict, engine_finish
    assert stats["events_queued"] >= 4

    core.shutdown()
    reset()


def test_integration_sampling():
    """Test sampling works end-to-end."""
    reset()
    set_enabled(True)
    set_sampling_rate(0.5)  # 50% sampling

    adapter = get_adapter()

    # Emit many events
    for i in range(100):
        adapter.on_engine_start(f"test_{i}", {})

    time.sleep(0.1)

    core = get_core()
    stats = core.health.get_stats()

    # Should have some queued and some sampled out
    assert stats["events_queued"] > 0
    assert stats["events_sampled_out"] > 0

    # Approximately 50% sampled out (allow variance)
    total = stats["events_queued"] + stats["events_sampled_out"]
    sample_rate = stats["events_queued"] / total
    assert 0.3 < sample_rate < 0.7  # 50% ± 20%

    core.shutdown()
    reset()


def test_integration_auto_disable():
    """Test auto-disable integration."""
    reset()

    # Configure with low threshold
    config = InstrumentationConfig(enabled=True)
    config.safety.auto_disable_threshold = 3

    # Reset to use new config
    reset()
    set_enabled(True)

    core = get_core()
    core.config.safety.auto_disable_threshold = 3

    # Trigger failures
    for i in range(5):
        core._handle_failure(Exception(f"Test {i}"))

    # Should auto-disable
    assert core._enabled is False

    health = core.get_health_status()
    assert health["auto_disabled"] is True

    core.shutdown()
    reset()


def test_integration_multiple_signal_types():
    """Test handling multiple signal types."""
    reset()
    set_enabled(True)

    adapter = get_adapter()

    # Emit different signal types
    adapter.on_engine_start("test", {})
    adapter.on_finding_created(MockFinding())
    adapter.on_verdict_decided(MockVerdict())
    adapter.on_policy_evaluated("test.policy", True)
    adapter.on_human_override("FAIL", "PASS", "user", "test")
    adapter.on_cache_decision("key", True)
    adapter.on_evidence_input("file_read", "engine", "hash123")
    adapter.on_belief_change("ready", True, False, "trigger")
    adapter.on_economic_signal("tokens", 100, "tokens")
    adapter.on_semantic_usage("ready", "config", "score >= 90")

    time.sleep(0.1)

    core = get_core()
    stats = core.health.get_stats()

    # All events should be queued
    assert stats["events_queued"] >= 10

    core.shutdown()
    reset()


def test_integration_selective_signals():
    """Test selective signal type filtering."""
    reset()

    # Only enable assertions and decisions
    config = InstrumentationConfig(enabled=True)
    config.signals.assertions = True
    config.signals.decisions = True
    config.signals.overrides = False
    config.signals.evidence = False

    reset()
    set_enabled(True, signals=config.signals)

    adapter = get_adapter()
    core = get_core()
    core.config.signals = config.signals

    # Emit different types
    adapter.on_finding_created(MockFinding())  # assertion - should queue
    adapter.on_verdict_decided(MockVerdict())  # decision - should queue
    adapter.on_human_override("F", "P", "u", "r")  # override - should skip
    adapter.on_evidence_input("file", "src", "hash")  # evidence - should skip

    time.sleep(0.1)

    stats = core.health.get_stats()

    # Only assertions and decisions should be queued
    assert stats["events_queued"] == 2

    core.shutdown()
    reset()


def test_integration_concurrent_access():
    """Test concurrent access to instrumentation."""
    import threading

    reset()
    set_enabled(True)

    adapter = get_adapter()

    def worker(thread_id: int):
        for i in range(50):
            adapter.on_engine_start(f"thread_{thread_id}_op_{i}", {})

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    time.sleep(0.2)

    core = get_core()
    stats = core.health.get_stats()

    # Should have queued most/all events (5 threads * 50 events = 250)
    assert stats["events_queued"] > 200

    core.shutdown()
    reset()


def test_integration_graceful_degradation():
    """Test graceful degradation on errors."""
    reset()
    set_enabled(True)

    adapter = get_adapter()
    core = get_core()

    # Emit normal event
    adapter.on_engine_start("test", {})
    time.sleep(0.05)

    initial_queued = core.health.get_stats()["events_queued"]

    # Emit invalid events (should not crash)
    adapter.on_finding_created(None)  # type: ignore
    adapter.on_verdict_decided(object())  # type: ignore

    time.sleep(0.05)

    # Should still work
    adapter.on_engine_finish("test", {}, 0.0, True)
    time.sleep(0.05)

    final_queued = core.health.get_stats()["events_queued"]

    # At least the valid events should be queued
    assert final_queued > initial_queued

    core.shutdown()
    reset()


# Mock objects for testing
class MockFinding:
    def __init__(self):
        self.rule_id = "test.rule"
        self.severity = type("Severity", (), {"value": "INFO"})()
        self.message = "Test finding"


class MockVerdict:
    def __init__(self):
        self.verdict = type("Verdict", (), {"value": "PASS"})()
        self.value = 100
        self.summary = "Test verdict"
