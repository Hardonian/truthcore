"""
Core instrumentation engine.

Provides zero-overhead event emission with:
- Fast-path flag checks when disabled
- Bounded queues with drop-on-full
- Async emission (never blocks caller)
- Auto-disable on repeated failures
- Internal failure logging only
"""

import json
import queue
import random
import threading
import time
from datetime import datetime, timezone
from typing import Any

from truthcore.instrumentation.config import InstrumentationConfig, OutputMode
from truthcore.instrumentation.health import InstrumentationHealth


def utc_now_iso() -> str:
    """Get current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


class BoundedQueue:
    """
    Thread-safe bounded queue that drops on overflow.

    When full, try_put() returns False immediately rather than blocking.
    """

    def __init__(self, maxsize: int):
        self._queue: queue.Queue = queue.Queue(maxsize=maxsize)
        self._maxsize = maxsize

    def try_put(self, item: Any, timeout: float = 0) -> bool:
        """
        Try to put item in queue without blocking.

        Returns:
            True if item added, False if queue full
        """
        try:
            self._queue.put(item, block=(timeout > 0), timeout=timeout)
            return True
        except queue.Full:
            return False

    def get(self, timeout: float | None = None) -> Any:
        """Get item from queue (blocks until available)."""
        return self._queue.get(timeout=timeout)

    def qsize(self) -> int:
        """Approximate queue size."""
        return self._queue.qsize()

    def empty(self) -> bool:
        """Check if queue is empty."""
        return self._queue.empty()


class AsyncEmitter:
    """
    Async event emitter that consumes from queue in background thread.

    Events are emitted in a separate thread to avoid blocking the caller.
    """

    def __init__(self, config: InstrumentationConfig, health: InstrumentationHealth):
        self.config = config
        self.health = health
        self._running = False
        self._thread: threading.Thread | None = None
        self._event_queue: BoundedQueue | None = None

    def start(self, event_queue: BoundedQueue) -> None:
        """Start background emitter thread."""
        if self._running:
            return

        self._event_queue = event_queue
        self._running = True
        self._thread = threading.Thread(target=self._emit_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop background emitter thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None

    def _emit_loop(self) -> None:
        """Background thread loop that emits events."""
        while self._running:
            try:
                # Get event from queue with timeout
                event = self._event_queue.get(timeout=0.1)
                self._emit_event(event)
            except queue.Empty:
                continue
            except Exception as e:
                # Log internally but continue running
                self.health.record_emission_error(str(e))

    def _emit_event(self, event: dict[str, Any]) -> None:
        """
        Emit a single event to configured output.

        Never raises exceptions.
        """
        try:
            if self.config.output_mode == OutputMode.LOG:
                self._emit_to_log(event)
            elif self.config.output_mode == OutputMode.FILE:
                self._emit_to_file(event)
            elif self.config.output_mode == OutputMode.SUBSTRATE:
                self._emit_to_substrate(event)
            elif self.config.output_mode == OutputMode.NULL:
                pass  # Discard

            self.health.record_event_emitted()

        except Exception as e:
            # Fallback to secondary output mode
            try:
                if self.config.fallback_mode == OutputMode.LOG:
                    self._emit_to_log(event)
                self.health.record_emission_error(str(e))
            except Exception:
                # Complete failure, just track it
                self.health.record_emission_error(f"fallback_failed: {e}")

    def _emit_to_log(self, event: dict[str, Any]) -> None:
        """Emit event to structured logger."""
        # Use existing truthcore logging if available
        try:
            import logging
            logger = logging.getLogger("truthcore.instrumentation")
            logger.info("cognitive_signal", extra={"signal": event})
        except Exception:
            # Fallback to stderr
            import sys
            print(json.dumps(event), file=sys.stderr)

    def _emit_to_file(self, event: dict[str, Any]) -> None:
        """Emit event to JSONL file."""
        if not self.config.output_path:
            raise ValueError("output_path required for FILE mode")

        # Append to JSONL file (one event per line)
        with open(self.config.output_path, "a") as f:
            json.dump(event, f)
            f.write("\n")

    def _emit_to_substrate(self, event: dict[str, Any]) -> None:
        """Emit event directly to Cognitive Substrate."""
        try:
            # Import substrate (may not exist)
            from truthcore.substrate import get_substrate
            substrate = get_substrate()
            substrate.ingest_signal(event)
        except (ImportError, AttributeError):
            # Substrate not available, fallback to log
            self._emit_to_log(event)


class InstrumentationCore:
    """
    Core instrumentation engine.

    Zero-overhead when disabled (<1μs per call).
    Async emission when enabled (<100μs per call).
    Never propagates exceptions upward.
    Auto-disables after repeated failures.
    """

    def __init__(self, config: InstrumentationConfig):
        self.config = config
        self.health = InstrumentationHealth()
        self._enabled = config.enabled
        self._failure_count = 0

        # Only create queue and emitter if enabled
        if self._enabled:
            self._queue = BoundedQueue(maxsize=config.safety.queue_size)
            self._emitter = AsyncEmitter(config, self.health)
            self._emitter.start(self._queue)
        else:
            self._queue = None
            self._emitter = None

        # Internal log for failures (avoid recursion)
        self._internal_log: list[dict] = []

    def emit(self, signal: dict[str, Any]) -> None:
        """
        Emit a signal event.

        Guarantees:
        - If disabled: <1μs overhead (single flag check)
        - If enabled: <100μs overhead (queue push)
        - Never blocks caller
        - Never propagates errors
        - Auto-disables after repeated failures

        Args:
            signal: Signal dictionary with at minimum {"signal_type": "..."}
        """
        # Fast path: disabled
        if not self._enabled:
            return  # <1μs overhead

        # Fast path: invalid signal
        if not isinstance(signal, dict):
            return  # <1μs overhead (invalid, just ignore)

        # Fast path: signal type disabled
        signal_type = signal.get("signal_type")
        if signal_type and not self.config.signals.is_enabled(signal_type):
            return  # <1μs overhead

        # Fast path: sampled out
        if random.random() > self.config.sampling_rate:
            self.health.record_event_sampled_out()
            return  # <5μs overhead

        try:
            # Add timestamp if missing
            if "timestamp" not in signal:
                signal["timestamp"] = utc_now_iso()

            # Validate event size
            event_json = json.dumps(signal)
            if len(event_json) > self.config.safety.max_event_size_bytes:
                self._handle_failure(ValueError(f"Event too large: {len(event_json)} bytes"))
                return

            # Non-blocking queue push
            if not self._queue.try_put(signal, timeout=0):
                # Queue full, drop event
                self._log_internal("event_dropped", "queue_full")
                self.health.record_event_dropped()
                return

            self.health.record_event_queued()

        except Exception as e:
            # NEVER propagate exceptions upward
            self._handle_failure(e)

    def _handle_failure(self, exc: Exception) -> None:
        """
        Handle instrumentation failure internally.

        Strategy:
        1. Increment failure counter
        2. Log internally (never via main logger to avoid recursion)
        3. Auto-disable if threshold exceeded
        4. Emit health signal (if possible)
        """
        self._failure_count += 1

        # Internal logging only
        self._log_internal("instrumentation_error", str(exc))
        self.health.record_failure()

        # Auto-disable after threshold
        if self._failure_count >= self.config.safety.auto_disable_threshold:
            self._enabled = False
            self._log_internal(
                "auto_disabled",
                f"failure_threshold_exceeded: {self._failure_count}/{self.config.safety.auto_disable_threshold}"
            )
            self.health.record_auto_disable()

    def _log_internal(self, event: str, message: str) -> None:
        """
        Internal logging that never uses instrumentation.

        Stores in memory to avoid recursion and I/O during failure handling.
        """
        self._internal_log.append({
            "event": event,
            "message": message,
            "timestamp": utc_now_iso(),
            "failure_count": self._failure_count,
        })

        # Keep log bounded
        if len(self._internal_log) > 1000:
            self._internal_log = self._internal_log[-500:]

    def get_internal_log(self) -> list[dict]:
        """Get internal failure log (for debugging)."""
        return list(self._internal_log)

    def get_health_status(self) -> dict[str, Any]:
        """Get current health status with comprehensive report."""
        # Get comprehensive health report from health monitor
        health_report = self.health.get_health_report()

        # Add core-specific status
        return {
            "enabled": self._enabled,
            "failure_count": self._failure_count,
            "auto_disabled": self._failure_count >= self.config.safety.auto_disable_threshold,
            "queue_depth": self._queue.qsize() if self._queue else 0,
            "queue_capacity": self.config.safety.queue_size if self._enabled else 0,
            **health_report,
        }

    def shutdown(self) -> None:
        """Shutdown instrumentation gracefully."""
        if self._emitter:
            self._emitter.stop()
        self._enabled = False


# Utility function for content hashing (used in adapters)
def content_hash(obj: Any) -> str:
    """
    Compute content hash of an object for deduplication.

    Uses JSON serialization for consistency.
    Returns sha256 hex digest.
    """
    import hashlib
    try:
        # Try to serialize to JSON (will use default=str for non-JSON types)
        serialized = json.dumps(obj, sort_keys=True, default=str)
        return f"sha256:{hashlib.sha256(serialized.encode()).hexdigest()[:16]}"
    except (TypeError, ValueError, AttributeError):
        # Truly unhashable - use repr or type as fallback
        try:
            fallback = repr(obj)
        except Exception:
            fallback = f"<{type(obj).__name__}>"
        return f"sha256:{hashlib.sha256(fallback.encode()).hexdigest()[:16]}"
