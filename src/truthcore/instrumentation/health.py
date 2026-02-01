"""
Health monitoring for Silent Instrumentation Layer.

Tracks:
- Events queued, emitted, dropped, sampled out
- Failure count and auto-disable events
- Emission errors
- Queue saturation metrics
"""

import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass
class InstrumentationStats:
    """Statistics for instrumentation operations."""
    events_queued: int = 0
    events_emitted: int = 0
    events_dropped: int = 0
    events_sampled_out: int = 0
    failures: int = 0
    emission_errors: int = 0
    auto_disable_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "events_queued": self.events_queued,
            "events_emitted": self.events_emitted,
            "events_dropped": self.events_dropped,
            "events_sampled_out": self.events_sampled_out,
            "failures": self.failures,
            "emission_errors": self.emission_errors,
            "auto_disable_count": self.auto_disable_count,
        }


class InstrumentationHealth:
    """
    Health monitoring for instrumentation layer.

    Thread-safe counters for tracking instrumentation health.
    All operations are lock-protected for concurrent access.
    """

    def __init__(self):
        self._stats = InstrumentationStats()
        self._lock = threading.Lock()

    def record_event_queued(self) -> None:
        """Record event successfully queued."""
        with self._lock:
            self._stats.events_queued += 1

    def record_event_emitted(self) -> None:
        """Record event successfully emitted."""
        with self._lock:
            self._stats.events_emitted += 1

    def record_event_dropped(self) -> None:
        """Record event dropped (queue full)."""
        with self._lock:
            self._stats.events_dropped += 1

    def record_event_sampled_out(self) -> None:
        """Record event sampled out."""
        with self._lock:
            self._stats.events_sampled_out += 1

    def record_failure(self) -> None:
        """Record instrumentation failure."""
        with self._lock:
            self._stats.failures += 1

    def record_emission_error(self, error: str) -> None:
        """Record emission error."""
        with self._lock:
            self._stats.emission_errors += 1

    def record_auto_disable(self) -> None:
        """Record auto-disable event."""
        with self._lock:
            self._stats.auto_disable_count += 1

    def get_stats(self) -> dict[str, Any]:
        """Get current statistics (thread-safe copy)."""
        with self._lock:
            return self._stats.to_dict()

    def reset(self) -> None:
        """Reset all counters (mainly for testing)."""
        with self._lock:
            self._stats = InstrumentationStats()

    def get_health_report(self) -> dict[str, Any]:
        """
        Get comprehensive health report.

        Includes:
        - Current statistics
        - Calculated metrics (drop rate, failure rate)
        - Health status assessment
        """
        stats = self.get_stats()

        # Calculate rates
        total_events = stats["events_queued"] + stats["events_dropped"] + stats["events_sampled_out"]
        drop_rate = stats["events_dropped"] / total_events if total_events > 0 else 0.0
        failure_rate = stats["failures"] / total_events if total_events > 0 else 0.0

        # Assess health status
        if stats["auto_disable_count"] > 0:
            health_status = "auto_disabled"
        elif drop_rate > 0.1:  # >10% drop rate
            health_status = "degraded"
        elif failure_rate > 0.01:  # >1% failure rate
            health_status = "warning"
        else:
            health_status = "healthy"

        return {
            **stats,
            "drop_rate": round(drop_rate, 4),
            "failure_rate": round(failure_rate, 4),
            "health_status": health_status,
        }
