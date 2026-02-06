"""Performance tests for TruthCore.

Asserts that key operations complete within reasonable bounds.
These are not strict benchmarks but regression guards.
"""

from __future__ import annotations

import json
import time

import pytest

from truthcore.canonical import canonical_hash, canonical_json
from truthcore.determinism import determinism_mode
from truthcore.manifest import hash_dict
from truthcore.memoize import clear_memo_cache, memo_stats, memoize_by_hash
from truthcore.severity import Category, EngineHealth, Severity
from truthcore.verdict.aggregator import VerdictAggregator
from truthcore.verdict.models import Mode, VerdictThresholds


class TestMemoization:
    """Test the memoization system."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_memo_cache()

    def test_cache_hit(self):
        """Second call with same data should be a cache hit."""
        data = {"key": "value", "num": 42}
        call_count = 0

        def compute():
            nonlocal call_count
            call_count += 1
            return {"result": True}

        r1 = memoize_by_hash(data, compute)
        r2 = memoize_by_hash(data, compute)

        assert r1 == r2
        assert call_count == 1  # compute() called only once
        stats = memo_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1

    def test_cache_miss_different_data(self):
        """Different data should trigger a new computation."""
        call_count = 0

        def compute():
            nonlocal call_count
            call_count += 1
            return {"run": call_count}

        memoize_by_hash({"a": 1}, compute)
        memoize_by_hash({"a": 2}, compute)

        assert call_count == 2

    def test_clear_cache(self):
        """clear_memo_cache should reset everything."""
        memoize_by_hash({"x": 1}, lambda: "cached")
        clear_memo_cache()
        stats = memo_stats()
        assert stats["entries"] == 0
        assert stats["hits"] == 0


class TestCanonicalPerformance:
    """Performance regression guards for canonical operations."""

    def test_canonical_json_small_dict(self):
        """Small dict canonicalization should be fast."""
        data = {"key": "value", "number": 42, "flag": True}
        start = time.perf_counter()
        for _ in range(1000):
            canonical_json(data)
        elapsed = time.perf_counter() - start
        assert elapsed < 2.0, f"1000 small dict canonicalizations took {elapsed:.3f}s"

    def test_canonical_json_large_dict(self):
        """Large dict canonicalization should complete in reasonable time."""
        data = {f"key_{i}": {"nested": i, "flag": i % 2 == 0} for i in range(100)}
        start = time.perf_counter()
        for _ in range(100):
            canonical_json(data)
        elapsed = time.perf_counter() - start
        assert elapsed < 5.0, f"100 large dict canonicalizations took {elapsed:.3f}s"

    def test_hash_stability_performance(self):
        """hash_dict should not regress on performance."""
        data = {"findings": [{"id": f"f_{i}", "sev": "HIGH"} for i in range(50)]}
        start = time.perf_counter()
        for _ in range(500):
            hash_dict(data)
        elapsed = time.perf_counter() - start
        assert elapsed < 5.0, f"500 hash_dict calls took {elapsed:.3f}s"


class TestVerdictPerformance:
    """Performance regression guards for verdict operations."""

    def test_verdict_aggregation_many_findings(self):
        """Verdict aggregation with many findings should complete quickly."""
        with determinism_mode():
            thresholds = VerdictThresholds.for_mode(Mode.PR)
            agg = VerdictAggregator(thresholds=thresholds, expected_engines=["engine"])
            agg.register_engine_health(EngineHealth(
                engine_id="engine", expected=True, ran=True, succeeded=True,
                timestamp="2025-01-01T00:00:00Z",
            ))

            # Add 100 findings
            for i in range(100):
                severity = ["HIGH", "MEDIUM", "LOW", "INFO"][i % 4]
                category = ["security", "types", "build", "general"][i % 4]
                agg.add_finding(
                    finding_id=f"f_{i:03d}",
                    tool="engine",
                    severity=severity,
                    category=category,
                    message=f"Finding {i}",
                    rule_id=f"RULE_{i:03d}",
                    source_engine="engine",
                    run_id="perf-test",
                )

            start = time.perf_counter()
            result = agg.aggregate(mode=Mode.PR, run_id="perf-test")
            elapsed = time.perf_counter() - start

            assert elapsed < 1.0, f"Verdict aggregation with 100 findings took {elapsed:.3f}s"
            assert result.total_findings == 100

    def test_envelope_creation_performance(self):
        """Envelope creation from verdict should be fast."""
        with determinism_mode():
            thresholds = VerdictThresholds.for_mode(Mode.PR)
            agg = VerdictAggregator(thresholds=thresholds, expected_engines=["engine"])
            agg.register_engine_health(EngineHealth(
                engine_id="engine", expected=True, ran=True, succeeded=True,
                timestamp="2025-01-01T00:00:00Z",
            ))
            for i in range(50):
                agg.add_finding(
                    finding_id=f"f_{i}", tool="engine", severity="MEDIUM",
                    category="general", message=f"Finding {i}",
                    source_engine="engine", run_id="perf-test",
                )

            result = agg.aggregate(mode=Mode.PR, run_id="perf-test")

            start = time.perf_counter()
            for _ in range(100):
                result.to_envelope()
            elapsed = time.perf_counter() - start

            assert elapsed < 5.0, f"100 envelope creations took {elapsed:.3f}s"
