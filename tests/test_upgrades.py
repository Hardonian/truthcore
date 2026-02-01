"""Tests for new upgrade features."""

import json

import pytest

from truthcore.cache import ContentAddressedCache
from truthcore.manifest import (
    RunManifest,
    hash_content,
    hash_dict,
    normalize_timestamp,
)
from truthcore.security import (
    SecurityLimits,
    check_path_safety,
    safe_load_json,
    sanitize_markdown,
)


class TestManifest:
    """Tests for manifest system."""

    def test_normalize_timestamp(self):
        """Test timestamp normalization."""
        ts = normalize_timestamp()
        assert ts.endswith("Z")
        assert "+" not in ts  # No timezone offset, always UTC

    def test_hash_content(self):
        """Test content hashing."""
        h1 = hash_content(b"test")
        h2 = hash_content(b"test")
        assert h1 == h2  # Deterministic
        assert len(h1) == 32  # blake2b with 16 bytes = 32 hex chars

    def test_hash_dict(self):
        """Test dict hashing is deterministic."""
        d1 = {"b": 2, "a": 1}
        d2 = {"a": 1, "b": 2}
        assert hash_dict(d1) == hash_dict(d2)  # Order independent

    def test_manifest_creation(self):
        """Test manifest creation."""
        manifest = RunManifest.create(
            command="test",
            config={"profile": "test"},
        )

        assert manifest.command == "test"
        assert manifest.truthcore_version is not None
        assert manifest.timestamp.endswith("Z")
        assert manifest.run_id is not None


class TestCache:
    """Tests for content-addressed cache."""

    def test_cache_put_get(self, tmp_path):
        """Test cache put and get."""
        cache_dir = tmp_path / "cache"
        cache = ContentAddressedCache(cache_dir)

        # Create test output
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        (output_dir / "test.json").write_text('{"result": true}')

        # Store in cache
        key = "test_key_123"
        cache.put(key, output_dir, {"test": True})

        # Retrieve from cache
        cached_path = cache.get(key)
        assert cached_path is not None
        assert (cached_path / "test.json").exists()

    def test_cache_miss(self, tmp_path):
        """Test cache miss."""
        cache = ContentAddressedCache(tmp_path / "cache")
        assert cache.get("nonexistent_key") is None

    def test_cache_stats(self, tmp_path):
        """Test cache statistics."""
        cache = ContentAddressedCache(tmp_path / "cache")
        stats = cache.stats()

        assert "entries" in stats
        assert "total_size_bytes" in stats


class TestSecurity:
    """Tests for security hardening."""

    def test_path_traversal_detection(self, tmp_path):
        """Test path traversal is detected."""
        base = tmp_path / "base"
        base.mkdir()

        # Safe path
        safe = check_path_safety(base / "subdir", base)
        assert safe == (base / "subdir").resolve()

        # Unsafe path should raise
        with pytest.raises(Exception):
            check_path_safety(tmp_path / "outside", base)

    def test_safe_load_json_depth(self):
        """Test JSON depth limit."""
        # Create deeply nested JSON
        data = {}
        current = data
        for _ in range(150):  # Exceed default 100
            current["nested"] = {}
            current = current["nested"]

        json_str = json.dumps(data)
        limits = SecurityLimits(max_json_depth=100)

        with pytest.raises(Exception):
            safe_load_json(json_str, limits)

    def test_sanitize_markdown(self):
        """Test markdown sanitization."""
        dirty = "<script>alert('xss')</script> Hello"
        clean = sanitize_markdown(dirty)
        assert "<script>" not in clean
        assert "[REMOVED" in clean


class TestAnomalyScoring:
    """Tests for deterministic anomaly scoring."""

    def test_regression_density(self):
        """Test regression density calculation."""
        from truthcore.anomaly_scoring import ReadinessAnomalyScorer

        history = [
            {"passed": True},
            {"passed": False},
            {"passed": True},
            {"passed": False},
        ]

        scorer = ReadinessAnomalyScorer(history)
        density = scorer.compute_regression_density(window_size=4)

        assert density["score"] == 0.5  # 2 failures / 4 total
        assert density["failures"] == 2

    def test_flake_probability(self):
        """Test flake probability calculation."""
        from truthcore.anomaly_scoring import ReadinessAnomalyScorer

        # Alternating pass/fail indicates flakiness
        history = [
            {"passed": True},
            {"passed": False},
            {"passed": True},
            {"passed": False},
        ]

        scorer = ReadinessAnomalyScorer(history)
        flake = scorer.compute_flake_probability()

        assert flake["transitions"] == 3
        assert flake["flake_indicator"] > 0


class TestInvariantDSL:
    """Tests for invariant DSL."""

    def test_simple_rule_evaluation(self):
        """Test simple rule evaluation."""
        from truthcore.invariant_dsl import InvariantDSL

        data = {"errors": 0, "warnings": 5}
        dsl = InvariantDSL(data)

        rule = {
            "id": "no_errors",
            "left": "errors",
            "operator": "==",
            "right": 0,
        }

        passed, _ = dsl.evaluate_rule(rule)
        assert passed is True

    def test_all_composition(self):
        """Test all (AND) composition."""
        from truthcore.invariant_dsl import InvariantDSL

        data = {"errors": 0, "warnings": 2}
        dsl = InvariantDSL(data)

        rule = {
            "id": "all_checks",
            "all": [
                {"left": "errors", "operator": "==", "right": 0},
                {"left": "warnings", "operator": "<", "right": 5},
            ]
        }

        passed, _ = dsl.evaluate_rule(rule)
        assert passed is True

    def test_aggregation(self):
        """Test aggregation functions."""
        from truthcore.invariant_dsl import InvariantDSL

        data = {
            "findings": [
                {"severity": "HIGH"},
                {"severity": "HIGH"},
                {"severity": "LOW"},
            ]
        }
        dsl = InvariantDSL(data)

        rule = {
            "id": "count_high",
            "aggregation": "count",
            "path": "findings",
            "filter": {"severity": "HIGH"},
            "operator": "==",
            "right": 2,
        }

        passed, eval_data = dsl.evaluate_rule(rule)
        assert passed is True


class TestUIGeometry:
    """Tests for UI geometry checks."""

    def test_bounding_box_intersection(self):
        """Test bounding box intersection."""
        from truthcore.ui_geometry import BoundingBox

        box1 = BoundingBox(x=0, y=0, width=100, height=100)
        box2 = BoundingBox(x=50, y=50, width=100, height=100)

        assert box1.intersects(box2) is True
        assert box1.intersection_area(box2) == 2500  # 50x50 overlap

    def test_no_intersection(self):
        """Test non-intersecting boxes."""
        from truthcore.ui_geometry import BoundingBox

        box1 = BoundingBox(x=0, y=0, width=10, height=10)
        box2 = BoundingBox(x=100, y=100, width=10, height=10)

        assert box1.intersects(box2) is False
        assert box1.intersection_area(box2) == 0
