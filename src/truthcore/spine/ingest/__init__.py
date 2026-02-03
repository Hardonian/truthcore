"""Ingestion bridge for TruthCore Spine.

Transforms signals from Silent Instrumentation Layer into assertions
and evidence. Async, non-blocking, with deduplication.
"""

from __future__ import annotations

import json
import queue
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from truthcore.spine.graph import GraphStore
from truthcore.spine.primitives import Assertion, ClaimType, Evidence, EvidenceType


@dataclass
class IngestionConfig:
    """Configuration for ingestion."""
    queue_size: int = 10000
    batch_size: int = 100
    flush_interval_seconds: float = 5.0
    dedup_window_seconds: float = 60.0
    max_retries: int = 3
    enabled: bool = True


class IngestionQueue:
    """Bounded queue for async ingestion.

    Drops signals when full rather than blocking.
    """

    def __init__(self, config: IngestionConfig):
        self.config = config
        self._queue: queue.Queue[dict] = queue.Queue(maxsize=config.queue_size)
        self._dropped_count = 0
        self._processed_count = 0
        self._lock = threading.Lock()

    def put(self, signal: dict) -> bool:
        """Add signal to queue. Returns False if dropped.

        Never blocks - drops signal if queue full.
        """
        if not self.config.enabled:
            return False

        try:
            self._queue.put_nowait(signal)
            return True
        except queue.Full:
            with self._lock:
                self._dropped_count += 1
            return False

    def get_batch(self, max_size: int | None = None) -> list[dict]:
        """Get batch of signals from queue."""
        max_size = max_size or self.config.batch_size
        batch = []

        while len(batch) < max_size:
            try:
                signal = self._queue.get_nowait()
                batch.append(signal)
            except queue.Empty:
                break

        with self._lock:
            self._processed_count += len(batch)

        return batch

    def get_stats(self) -> dict[str, Any]:
        """Get queue statistics."""
        with self._lock:
            return {
                "queue_size": self._queue.qsize(),
                "dropped_count": self._dropped_count,
                "processed_count": self._processed_count,
                "max_size": self.config.queue_size,
            }


class SignalTransformer:
    """Transforms instrumentation signals into spine primitives."""

    def __init__(self, store: GraphStore):
        self.store = store
        self._recent_hashes: set[str] = set()

    def transform_signal(self, signal: dict) -> tuple[Evidence | None, Assertion | None]:
        """Transform a signal into evidence and/or assertion.

        Returns (evidence, assertion) tuple. Either may be None.
        """
        signal_type = signal.get("signal_type")

        if signal_type == "assertion":
            return self._transform_assertion_signal(signal)
        elif signal_type == "evidence":
            return self._transform_evidence_signal(signal), None
        elif signal_type == "decision":
            return self._transform_decision_signal(signal)
        else:
            # Unknown signal type - skip
            return None, None

    def _transform_assertion_signal(self, signal: dict) -> tuple[Evidence | None, Assertion]:
        """Transform an assertion signal."""
        # Create evidence for the raw signal data
        signal_content = json.dumps(signal, sort_keys=True)
        evidence_id = Evidence.compute_hash(signal_content)

        evidence = Evidence(
            evidence_id=evidence_id,
            evidence_type=EvidenceType.RAW,
            content_hash=evidence_id,
            source=signal.get("source", "unknown"),
            timestamp=signal.get("timestamp", datetime.now(UTC).isoformat()),
            metadata={"signal_type": "assertion", "original_signal": signal},
        )

        # Create assertion from signal
        claim = signal.get("claim", signal.get("message", "Unknown claim"))
        assertion_id = Assertion.compute_id(claim, [evidence_id])

        assertion = Assertion(
            assertion_id=assertion_id,
            claim=claim,
            evidence_ids=(evidence_id,),
            claim_type=ClaimType.OBSERVED,
            source=signal.get("source", "unknown"),
            timestamp=signal.get("timestamp", datetime.now(UTC).isoformat()),
            context={
                "run_id": signal.get("context", {}).get("run_id"),
                "profile": signal.get("context", {}).get("profile"),
                "confidence_hint": signal.get("confidence_hint"),
            },
        )

        return evidence, assertion

    def _transform_evidence_signal(self, signal: dict) -> Evidence:
        """Transform an evidence signal."""
        content_hash = signal.get("content_hash", signal.get("hash", ""))

        return Evidence(
            evidence_id=content_hash or Evidence.compute_hash(
                json.dumps(signal, sort_keys=True)
            ),
            evidence_type=EvidenceType(signal.get("evidence_type", "raw")),
            content_hash=content_hash,
            source=signal.get("source", "unknown"),
            timestamp=signal.get("timestamp", datetime.now(UTC).isoformat()),
            metadata=signal.get("context", {}),
        )

    def _transform_decision_signal(self, signal: dict) -> tuple[Evidence | None, Assertion]:
        """Transform a decision signal into an assertion."""
        # Create evidence
        signal_content = json.dumps(signal, sort_keys=True)
        evidence_id = Evidence.compute_hash(signal_content)

        evidence = Evidence(
            evidence_id=evidence_id,
            evidence_type=EvidenceType.RAW,
            content_hash=evidence_id,
            source=signal.get("actor", "system"),
            timestamp=signal.get("timestamp", datetime.now(UTC).isoformat()),
            metadata={"signal_type": "decision", "original_signal": signal},
        )

        # Create assertion about the decision
        action = signal.get("action", "unknown_action")
        claim = f"Decision made: {action}"

        assertion_id = Assertion.compute_id(claim, [evidence_id])

        assertion = Assertion(
            assertion_id=assertion_id,
            claim=claim,
            evidence_ids=(evidence_id,),
            claim_type=ClaimType.DERIVED,
            source=signal.get("actor", "system"),
            timestamp=signal.get("timestamp", datetime.now(UTC).isoformat()),
            context={
                "action": action,
                "rationale": signal.get("rationale", []),
                "score": signal.get("score"),
            },
        )

        return evidence, assertion

    def is_duplicate(self, content_hash: str) -> bool:
        """Check if we've recently processed this content."""
        return content_hash in self._recent_hashes

    def mark_processed(self, content_hash: str) -> None:
        """Mark content as processed (for deduplication)."""
        self._recent_hashes.add(content_hash)
        # TODO: Expire old entries periodically


class IngestionEngine:
    """Main ingestion engine that processes signals asynchronously.

    Safe to use from multiple threads. Drops signals on failure.
    """

    def __init__(self, store: GraphStore, config: IngestionConfig | None = None):
        self.store = store
        self.config = config or IngestionConfig()
        self.queue = IngestionQueue(self.config)
        self.transformer = SignalTransformer(store)
        self._running = False
        self._worker_thread: threading.Thread | None = None
        self._on_error: Callable[[Exception], None] | None = None
        self._failure_count = 0

    def start(self) -> None:
        """Start the ingestion worker thread."""
        if self._running:
            return

        self._running = True
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()

    def stop(self) -> None:
        """Stop the ingestion worker."""
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=5.0)

    def ingest(self, signal: dict) -> bool:
        """Ingest a signal. Returns True if queued successfully.

        Never blocks or raises exceptions.
        """
        try:
            return self.queue.put(signal)
        except Exception as e:
            self._handle_error(e)
            return False

    def ingest_batch(self, signals: list[dict]) -> int:
        """Ingest multiple signals. Returns count successfully queued."""
        count = 0
        for signal in signals:
            if self.ingest(signal):
                count += 1
        return count

    def _worker_loop(self) -> None:
        """Main worker loop that processes signals."""
        while self._running:
            try:
                # Get batch of signals
                batch = self.queue.get_batch()

                if batch:
                    self._process_batch(batch)
                else:
                    # No signals, sleep briefly
                    time.sleep(0.1)

                # Periodic flush
                # (In production, also flush on timer)

            except Exception as e:
                self._handle_error(e)

    def _process_batch(self, signals: list[dict]) -> None:
        """Process a batch of signals."""
        for signal in signals:
            try:
                self._process_signal(signal)
            except Exception as e:
                self._handle_error(e)

    def _process_signal(self, signal: dict) -> None:
        """Process a single signal."""
        # Transform signal
        evidence, assertion = self.transformer.transform_signal(signal)

        # Check for duplicates
        if assertion and self.transformer.is_duplicate(assertion.assertion_id):
            return

        # Store evidence
        if evidence:
            self.store.store_evidence(evidence)

        # Store assertion
        if assertion:
            self.store.store_assertion(assertion)
            self.transformer.mark_processed(assertion.assertion_id)

    def _handle_error(self, error: Exception) -> None:
        """Handle ingestion error internally."""
        self._failure_count += 1

        if self._on_error:
            try:
                self._on_error(error)
            except Exception:
                pass  # Don't let error handler errors propagate

        # Auto-disable after repeated failures
        if self._failure_count >= self.config.max_retries * 10:
            self.config.enabled = False

    def get_stats(self) -> dict[str, Any]:
        """Get ingestion statistics."""
        return {
            "enabled": self.config.enabled,
            "running": self._running,
            "failure_count": self._failure_count,
            **self.queue.get_stats(),
        }


class IngestionBridge:
    """High-level bridge for ingesting from Silent Instrumentation Layer.

    Provides simple interface for connecting existing engines to spine.
    """

    def __init__(self, store: GraphStore | None = None, enabled: bool = False):
        self.enabled = enabled
        self.store = store or GraphStore()
        self.engine = IngestionEngine(self.store) if enabled else None

        if self.engine:
            self.engine.start()

    def record_finding(self, finding: Any) -> bool:
        """Record a finding from existing TruthCore engine.

        Converts Finding to assertion signal and ingests.
        """
        if not self.enabled or not self.engine:
            return False

        signal = {
            "signal_type": "assertion",
            "source": getattr(finding, 'rule_id', 'unknown'),
            "claim": getattr(finding, 'message', str(finding)),
            "severity": getattr(getattr(finding, 'severity', None), 'value', 'unknown'),
            "timestamp": getattr(finding, 'timestamp', datetime.now(UTC).isoformat()),
            "context": {
                "target": getattr(finding, 'target', None),
                "location": getattr(getattr(finding, 'location', None), 'path', None),
            },
        }

        return self.engine.ingest(signal)

    def record_verdict(self, verdict: Any, actor: str = "system") -> bool:
        """Record a verdict as a decision signal."""
        if not self.enabled or not self.engine:
            return False

        signal = {
            "signal_type": "decision",
            "decision_type": "system",
            "actor": actor,
            "action": getattr(getattr(verdict, 'verdict', None), 'value', str(verdict)),
            "score": getattr(verdict, 'value', None),
            "rationale": getattr(verdict, 'summary', []),
            "timestamp": datetime.now(UTC).isoformat(),
        }

        return self.engine.ingest(signal)

    def record_override(
        self,
        original: str,
        override: str,
        actor: str,
        rationale: str,
    ) -> bool:
        """Record a human override."""
        if not self.enabled or not self.engine:
            return False

        signal = {
            "signal_type": "override",
            "override_type": "human",
            "actor": actor,
            "original_decision": original,
            "override_decision": override,
            "rationale": rationale,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        return self.engine.ingest(signal)

    def shutdown(self) -> None:
        """Shutdown the bridge."""
        if self.engine:
            self.engine.stop()
