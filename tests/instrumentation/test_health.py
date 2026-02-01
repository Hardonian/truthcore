"""Tests for instrumentation health monitoring."""

import threading
import time
import pytest

from truthcore.instrumentation.health import InstrumentationHealth, InstrumentationStats


def test_instrumentation_stats():
    """Test instrumentation statistics data structure."""
    stats = InstrumentationStats()

    assert stats.events_queued == 0
    assert stats.events_emitted == 0
    assert stats.events_dropped == 0
    assert stats.failures == 0

    # Modify
    stats.events_queued = 10
    stats.events_emitted = 8
    stats.events_dropped = 2

    # to_dict
    data = stats.to_dict()
    assert data["events_queued"] == 10
    assert data["events_emitted"] == 8
    assert data["events_dropped"] == 2


def test_health_initial_state():
    """Test initial health state."""
    health = InstrumentationHealth()
    stats = health.get_stats()

    assert stats["events_queued"] == 0
    assert stats["events_emitted"] == 0
    assert stats["events_dropped"] == 0
    assert stats["events_sampled_out"] == 0
    assert stats["failures"] == 0
    assert stats["emission_errors"] == 0
    assert stats["auto_disable_count"] == 0


def test_health_record_events():
    """Test recording events."""
    health = InstrumentationHealth()

    # Record various events
    health.record_event_queued()
    health.record_event_queued()
    health.record_event_emitted()
    health.record_event_dropped()
    health.record_event_sampled_out()

    stats = health.get_stats()
    assert stats["events_queued"] == 2
    assert stats["events_emitted"] == 1
    assert stats["events_dropped"] == 1
    assert stats["events_sampled_out"] == 1


def test_health_record_failures():
    """Test recording failures."""
    health = InstrumentationHealth()

    health.record_failure()
    health.record_failure()
    health.record_emission_error("test error")
    health.record_auto_disable()

    stats = health.get_stats()
    assert stats["failures"] == 2
    assert stats["emission_errors"] == 1
    assert stats["auto_disable_count"] == 1


def test_health_reset():
    """Test resetting health stats."""
    health = InstrumentationHealth()

    # Record some events
    health.record_event_queued()
    health.record_event_emitted()
    health.record_failure()

    # Reset
    health.reset()

    stats = health.get_stats()
    assert stats["events_queued"] == 0
    assert stats["events_emitted"] == 0
    assert stats["failures"] == 0


def test_health_report():
    """Test comprehensive health report."""
    health = InstrumentationHealth()

    # Record events
    for _ in range(100):
        health.record_event_queued()

    for _ in range(90):
        health.record_event_emitted()

    for _ in range(10):
        health.record_event_dropped()

    health.record_failure()

    # Get report
    report = health.get_health_report()

    assert report["events_queued"] == 100
    assert report["events_emitted"] == 90
    assert report["events_dropped"] == 10
    assert report["failures"] == 1

    # Calculated metrics
    assert "drop_rate" in report
    assert "failure_rate" in report
    assert "health_status" in report

    # 10 dropped out of 110 total = ~0.09 drop rate
    assert 0.08 < report["drop_rate"] < 0.10


def test_health_status_healthy():
    """Test health status when healthy."""
    health = InstrumentationHealth()

    # Low drop rate, low failure rate
    for _ in range(100):
        health.record_event_queued()
        health.record_event_emitted()

    health.record_event_dropped()  # 1/101 = ~0.01 drop rate

    report = health.get_health_report()
    assert report["health_status"] == "healthy"


def test_health_status_degraded():
    """Test health status when degraded (high drop rate)."""
    health = InstrumentationHealth()

    # High drop rate (>10%)
    for _ in range(50):
        health.record_event_queued()

    for _ in range(50):
        health.record_event_dropped()

    report = health.get_health_report()
    assert report["health_status"] == "degraded"
    assert report["drop_rate"] >= 0.1


def test_health_status_warning():
    """Test health status with high failure rate."""
    health = InstrumentationHealth()

    # High failure rate (>1%)
    for _ in range(100):
        health.record_event_queued()

    for _ in range(5):
        health.record_failure()

    report = health.get_health_report()

    # Should be warning (5/105 = ~4.8% failure rate)
    assert report["health_status"] in ["warning", "degraded"]
    assert report["failure_rate"] > 0.01


def test_health_status_auto_disabled():
    """Test health status when auto-disabled."""
    health = InstrumentationHealth()

    health.record_auto_disable()

    report = health.get_health_report()
    assert report["health_status"] == "auto_disabled"


def test_health_thread_safety():
    """Test health monitoring is thread-safe."""
    health = InstrumentationHealth()
    num_threads = 10
    events_per_thread = 100

    def worker():
        for _ in range(events_per_thread):
            health.record_event_queued()
            health.record_event_emitted()

    threads = [threading.Thread(target=worker) for _ in range(num_threads)]

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    stats = health.get_stats()

    # Should have exactly num_threads * events_per_thread
    expected = num_threads * events_per_thread
    assert stats["events_queued"] == expected
    assert stats["events_emitted"] == expected


def test_health_zero_division_safety():
    """Test health report handles zero totals."""
    health = InstrumentationHealth()

    # No events recorded
    report = health.get_health_report()

    # Should not crash, rates should be 0
    assert report["drop_rate"] == 0.0
    assert report["failure_rate"] == 0.0
    assert report["health_status"] == "healthy"
