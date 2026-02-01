"""Tests for instrumentation core."""

import json
import time
import pytest

from truthcore.instrumentation.config import InstrumentationConfig, SignalFlags
from truthcore.instrumentation.core import (
    InstrumentationCore,
    BoundedQueue,
    content_hash,
    utc_now_iso,
)


def test_utc_now_iso():
    """Test UTC timestamp generation."""
    timestamp = utc_now_iso()
    assert isinstance(timestamp, str)
    assert "T" in timestamp
    assert timestamp.endswith(("Z", "+00:00"))


def test_content_hash():
    """Test content hashing."""
    obj1 = {"key": "value", "num": 42}
    obj2 = {"num": 42, "key": "value"}  # Different order

    hash1 = content_hash(obj1)
    hash2 = content_hash(obj2)

    assert hash1 == hash2  # Should be identical (sorted keys)
    assert hash1.startswith("sha256:")

    # Complex object (threading.Lock gets serialized via default=str)
    # Just verify it returns a valid hash
    import threading
    lock = threading.Lock()
    hash3 = content_hash(lock)
    assert hash3.startswith("sha256:")
    assert len(hash3) > len("sha256:")


def test_bounded_queue():
    """Test bounded queue with drop-on-full."""
    queue = BoundedQueue(maxsize=2)

    # Add items
    assert queue.try_put("item1") is True
    assert queue.try_put("item2") is True

    # Queue is full, should drop
    assert queue.try_put("item3", timeout=0) is False

    # Queue size
    assert queue.qsize() == 2
    assert queue.empty() is False

    # Remove items
    assert queue.get() == "item1"
    assert queue.get() == "item2"
    assert queue.empty() is True


def test_instrumentation_disabled():
    """Test instrumentation when disabled (fast path)."""
    config = InstrumentationConfig(enabled=False)
    core = InstrumentationCore(config)

    # Should be instant (<1μs), no queue created
    assert core._queue is None
    assert core._emitter is None

    # Emit should be no-op
    start = time.perf_counter()
    for _ in range(1000):
        core.emit({"signal_type": "test"})
    duration_ms = (time.perf_counter() - start) * 1000

    # Should be < 1ms for 1000 calls (< 1μs per call)
    assert duration_ms < 1.0

    # Health status
    status = core.get_health_status()
    assert status["enabled"] is False
    assert status["queue_depth"] == 0


def test_instrumentation_enabled():
    """Test instrumentation when enabled."""
    config = InstrumentationConfig(enabled=True)
    core = InstrumentationCore(config)

    try:
        # Queue and emitter created
        assert core._queue is not None
        assert core._emitter is not None

        # Emit event
        core.emit({"signal_type": "test", "data": "value"})

        # Should be queued
        time.sleep(0.01)  # Let emitter process
        status = core.get_health_status()
        assert status["enabled"] is True

    finally:
        core.shutdown()


def test_instrumentation_signal_type_filtering():
    """Test filtering by signal type."""
    config = InstrumentationConfig(
        enabled=True,
        signals=SignalFlags(assertions=True, decisions=False),
    )
    core = InstrumentationCore(config)

    try:
        # Enabled signal type
        core.emit({"signal_type": "assertions", "data": "test"})
        time.sleep(0.01)
        assert core.health.get_stats()["events_queued"] >= 1

        # Disabled signal type (should be filtered out)
        initial_count = core.health.get_stats()["events_queued"]
        core.emit({"signal_type": "decisions", "data": "test"})
        time.sleep(0.01)
        assert core.health.get_stats()["events_queued"] == initial_count

    finally:
        core.shutdown()


def test_instrumentation_sampling():
    """Test sampling rate."""
    config = InstrumentationConfig(enabled=True, sampling_rate=0.0)
    core = InstrumentationCore(config)

    try:
        # With 0% sampling, all events should be sampled out
        for _ in range(100):
            core.emit({"signal_type": "test"})

        time.sleep(0.1)
        stats = core.health.get_stats()
        assert stats["events_sampled_out"] == 100
        assert stats["events_queued"] == 0

    finally:
        core.shutdown()


def test_instrumentation_auto_timestamp():
    """Test automatic timestamp addition."""
    config = InstrumentationConfig(enabled=True)
    core = InstrumentationCore(config)

    try:
        # Emit without timestamp
        core.emit({"signal_type": "test", "data": "value"})

        time.sleep(0.05)

        # Event should have timestamp added
        # (We can't easily check the queued event, but we verify no crash)
        assert core.get_health_status()["enabled"] is True

    finally:
        core.shutdown()


def test_instrumentation_event_size_limit():
    """Test event size validation."""
    config = InstrumentationConfig(enabled=True)
    core = InstrumentationCore(config)

    try:
        # Create oversized event
        large_data = "x" * (config.safety.max_event_size_bytes + 1000)
        core.emit({"signal_type": "test", "data": large_data})

        time.sleep(0.05)

        # Should have recorded a failure
        stats = core.health.get_stats()
        assert stats["failures"] > 0

    finally:
        core.shutdown()


def test_instrumentation_queue_overflow():
    """Test queue overflow handling."""
    config = InstrumentationConfig(enabled=True)
    config.safety.queue_size = 5  # Very small queue

    core = InstrumentationCore(config)

    try:
        # Fill queue beyond capacity
        for i in range(20):
            core.emit({"signal_type": "test", "index": i})

        time.sleep(0.1)

        # Some events should be dropped
        stats = core.health.get_stats()
        assert stats["events_dropped"] > 0

    finally:
        core.shutdown()


def test_instrumentation_auto_disable():
    """Test auto-disable after repeated failures."""
    config = InstrumentationConfig(enabled=True)
    config.safety.auto_disable_threshold = 3

    core = InstrumentationCore(config)

    try:
        # Initial state
        assert core._enabled is True

        # Trigger failures by creating invalid events
        for i in range(5):
            # Simulate internal failure
            core._handle_failure(Exception(f"Test failure {i}"))

        # Should auto-disable after threshold
        assert core._enabled is False
        assert core._failure_count >= config.safety.auto_disable_threshold

        # Health status should reflect auto-disable
        status = core.get_health_status()
        assert status["auto_disabled"] is True

    finally:
        core.shutdown()


def test_instrumentation_internal_log():
    """Test internal failure logging."""
    config = InstrumentationConfig(enabled=True)
    core = InstrumentationCore(config)

    try:
        # Trigger a failure
        core._handle_failure(Exception("Test error"))

        # Check internal log
        log = core.get_internal_log()
        assert len(log) > 0
        assert any("instrumentation_error" in entry["event"] for entry in log)

    finally:
        core.shutdown()


def test_instrumentation_health_status():
    """Test health status reporting."""
    config = InstrumentationConfig(enabled=True)
    core = InstrumentationCore(config)

    try:
        status = core.get_health_status()

        # Check required fields
        assert "enabled" in status
        assert "failure_count" in status
        assert "auto_disabled" in status
        assert "queue_depth" in status
        assert "queue_capacity" in status
        assert "events_queued" in status
        assert "events_emitted" in status

        # Initial state
        assert status["enabled"] is True
        assert status["failure_count"] == 0
        assert status["auto_disabled"] is False

    finally:
        core.shutdown()


def test_instrumentation_shutdown():
    """Test graceful shutdown."""
    config = InstrumentationConfig(enabled=True)
    core = InstrumentationCore(config)

    # Emit some events
    for i in range(5):
        core.emit({"signal_type": "test", "index": i})

    # Shutdown
    core.shutdown()

    # Should be disabled
    assert core._enabled is False

    # Should not crash on subsequent emit
    core.emit({"signal_type": "test"})


def test_instrumentation_exception_safety():
    """Test that exceptions never propagate from emit()."""
    config = InstrumentationConfig(enabled=True)
    core = InstrumentationCore(config)

    try:
        # These should never raise, even with invalid data
        core.emit(None)  # type: ignore
        core.emit({"signal_type": 123})  # Invalid type
        core.emit({"signal_type": "test", "timestamp": object()})  # Un-serializable

        # Should still be running (may have failures logged)
        status = core.get_health_status()
        assert "enabled" in status

    finally:
        core.shutdown()


@pytest.mark.parametrize("num_events", [10, 100, 1000])
def test_instrumentation_performance(num_events):
    """Test performance at different scales."""
    config = InstrumentationConfig(enabled=True, sampling_rate=1.0)
    core = InstrumentationCore(config)

    try:
        start = time.perf_counter()

        for i in range(num_events):
            core.emit({"signal_type": "test", "index": i})

        duration_ms = (time.perf_counter() - start) * 1000
        per_event_us = (duration_ms * 1000) / num_events

        # Should be < 100μs per event on average
        assert per_event_us < 100, f"Performance: {per_event_us:.2f}μs per event"

    finally:
        core.shutdown()
