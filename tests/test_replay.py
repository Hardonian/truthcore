"""Tests for replay and simulation system."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from truthcore.replay import (
    BundleExporter,
    DiffComputer,
    DeterministicDiff,
    ReplayBundle,
    ReplayEngine,
    ReplayReporter,
    ReplayResult,
    SimulationChanges,
    SimulationEngine,
    SimulationReporter,
)
from truthcore.replay.diff import compute_content_hash
from truthcore.verdict.models import VerdictResult, VerdictStatus, Mode


class TestBundleExporter:
    """Tests for BundleExporter."""
    
    def test_export_creates_bundle_structure(self):
        """Test that export creates proper bundle structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            run_dir = tmpdir / "run"
            inputs_dir = tmpdir / "inputs"
            bundle_dir = tmpdir / "bundle"
            
            # Create mock run structure
            run_dir.mkdir()
            inputs_dir.mkdir()
            
            # Create run manifest
            manifest = {
                "run_id": "20260131120000-abc123",
                "command": "judge",
                "timestamp": "2026-01-31T12:00:00Z",
                "truthcore_version": "0.2.0",
                "config": {"hash": "abc123", "profile": "ui"},
                "inputs": {
                    "directory": str(inputs_dir),
                    "files": [
                        {
                            "path": "test.json",
                            "size": 100,
                            "content_hash": "def456",
                            "modified_time": "2026-01-31T11:00:00Z",
                        }
                    ],
                },
                "execution": {"duration_ms": 1000, "exit_code": 0},
                "cache": {"hit": False, "key": None, "path": None},
                "environment": {},
                "metadata": {},
            }
            
            with open(run_dir / "run_manifest.json", "w") as f:
                json.dump(manifest, f)
            
            # Create mock outputs
            with open(run_dir / "readiness.json", "w") as f:
                json.dump({"passed": True, "findings": []}, f)
            
            with open(run_dir / "verdict.json", "w") as f:
                json.dump({"verdict": "SHIP", "version": "2.0"}, f)
            
            # Create mock input
            with open(inputs_dir / "test.json", "w") as f:
                json.dump({"data": "test"}, f)
            
            # Export bundle
            exporter = BundleExporter()
            bundle = exporter.export(
                run_dir=run_dir,
                original_inputs_dir=inputs_dir,
                out_bundle_dir=bundle_dir,
                profile="ui",
                mode="pr",
            )
            
            # Verify bundle structure
            assert bundle_dir.exists()
            assert (bundle_dir / "run_manifest.json").exists()
            assert (bundle_dir / "inputs").exists()
            assert (bundle_dir / "outputs").exists()
            assert (bundle_dir / "bundle_meta.json").exists()
            
            # Verify files copied
            assert (bundle_dir / "inputs" / "test.json").exists()
            assert (bundle_dir / "outputs" / "readiness.json").exists()
            assert (bundle_dir / "outputs" / "verdict.json").exists()
    
    def test_load_bundle(self):
        """Test loading a replay bundle."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            bundle_dir = tmpdir / "bundle"
            bundle_dir.mkdir()
            
            # Create bundle structure
            manifest = {
                "run_id": "20260131120000-abc123",
                "command": "judge",
                "timestamp": "2026-01-31T12:00:00Z",
                "truthcore_version": "0.2.0",
                "truthcore_git_sha": None,
                "engine_versions": {},
                "config": {"hash": "abc123", "path": None, "profile": "ui"},
                "inputs": {"directory": "/tmp/inputs", "files": []},
                "environment": {
                    "python_version": "3.11.0",
                    "python_implementation": "CPython",
                    "os": {"name": "Linux", "release": "5.0"},
                    "cpu_arch": "x86_64",
                    "timezone": "UTC",
                },
                "cache": {"hit": False, "key": None, "path": None},
                "execution": {"duration_ms": 1000, "exit_code": 0},
                "metadata": {},
            }
            
            with open(bundle_dir / "run_manifest.json", "w") as f:
                json.dump(manifest, f)
            
            # Load bundle
            bundle = ReplayBundle.load(bundle_dir)
            
            assert bundle.manifest.run_id == "20260131120000-abc123"
            assert bundle.manifest.command == "judge"
            assert bundle.manifest.profile == "ui"


class TestDiffComputer:
    """Tests for DiffComputer."""
    
    def test_identical_documents(self):
        """Test that identical documents produce no diff."""
        old = {"key": "value", "number": 42}
        new = {"key": "value", "number": 42}
        
        computer = DiffComputer()
        diff = computer.compute(old, new)
        
        assert diff.identical is True
        assert diff.total_differences == 0
        assert diff.content_differences == 0
    
    def test_content_differences(self):
        """Test detection of content differences."""
        old = {"key": "value", "number": 42}
        new = {"key": "changed", "number": 42}
        
        computer = DiffComputer()
        diff = computer.compute(old, new)
        
        assert diff.identical is False
        assert diff.content_differences == 1
        assert diff.entries[0].path == "$.key"
    
    def test_allowed_differences(self):
        """Test that allowlisted fields are allowed to differ."""
        old = {"key": "value", "timestamp": "2026-01-31T10:00:00Z"}
        new = {"key": "value", "timestamp": "2026-01-31T11:00:00Z"}
        
        computer = DiffComputer(allowlist={"timestamp"})
        diff = computer.compute(old, new)
        
        assert diff.identical is True  # No content differences
        assert diff.allowed_differences == 1
    
    def test_nested_differences(self):
        """Test detection of nested differences."""
        old = {"nested": {"key": "value"}}
        new = {"nested": {"key": "changed"}}
        
        computer = DiffComputer()
        diff = computer.compute(old, new)
        
        assert diff.identical is False
        assert any(e.path == "$.nested.key" for e in diff.entries)
    
    def test_list_sorting(self):
        """Test that lists are sorted for deterministic comparison."""
        old = {"items": [{"id": "b"}, {"id": "a"}]}
        new = {"items": [{"id": "a"}, {"id": "b"}]}
        
        computer = DiffComputer()
        diff = computer.compute(old, new)
        
        # Should be identical after sorting by id
        assert diff.identical is True


class TestReplayEngine:
    """Tests for ReplayEngine."""
    
    def test_replay_produces_report(self):
        """Test that replay produces expected outputs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            bundle_dir = tmpdir / "bundle"
            output_dir = tmpdir / "replay"
            
            # Create bundle with minimal structure
            bundle_dir.mkdir()
            (bundle_dir / "inputs").mkdir()
            (bundle_dir / "outputs").mkdir()
            
            manifest = {
                "run_id": "20260131120000-abc123",
                "command": "judge",
                "timestamp": "2026-01-31T12:00:00Z",
                "truthcore_version": "0.2.0",
                "truthcore_git_sha": None,
                "engine_versions": {},
                "config": {"hash": "abc123", "path": None, "profile": "pr"},
                "inputs": {"directory": str(bundle_dir / "inputs"), "files": []},
                "environment": {
                    "python_version": "3.11.0",
                    "python_implementation": "CPython",
                    "os": {"name": "Linux", "release": "5.0"},
                    "cpu_arch": "x86_64",
                    "timezone": "UTC",
                },
                "cache": {"hit": False, "key": None, "path": None},
                "execution": {"duration_ms": 1000, "exit_code": 0},
                "metadata": {},
            }
            
            with open(bundle_dir / "run_manifest.json", "w") as f:
                json.dump(manifest, f)
            
            # Create minimal findings
            with open(bundle_dir / "outputs" / "readiness.json", "w") as f:
                json.dump({
                    "version": "0.2.0",
                    "profile": "pr",
                    "timestamp": "2026-01-31T12:00:00Z",
                    "passed": True,
                    "findings": [],
                }, f)
            
            # Load and replay
            bundle = ReplayBundle.load(bundle_dir)
            engine = ReplayEngine()
            result = engine.replay(bundle, output_dir)
            
            # Should complete without errors
            assert result.success is True
            assert (output_dir / "verdict.json").exists()
            assert (output_dir / "verdict.md").exists()


class TestSimulationChanges:
    """Tests for SimulationChanges."""
    
    def test_from_yaml(self):
        """Test loading changes from YAML."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yaml_path = Path(tmpdir) / "changes.yaml"
            
            yaml_content = """
thresholds:
  max_highs: 10
  max_total_points: 200
severity_weights:
  HIGH: 75.0
category_weights:
  security: 3.0
disabled_engines:
  - ui_geometry
disabled_rules:
  - UI_001
suppressions:
  - rule_id: UI_001
    reason: Known issue
    expiry: 2026-02-01T00:00:00Z
"""
            
            with open(yaml_path, "w") as f:
                f.write(yaml_content)
            
            changes = SimulationChanges.from_yaml(yaml_path)
            
            assert changes.thresholds["max_highs"] == 10
            assert changes.severity_weights["HIGH"] == 75.0
            assert changes.category_weights["security"] == 3.0
            assert "ui_geometry" in changes.disabled_engines
            assert "UI_001" in changes.disabled_rules
            assert len(changes.suppressions) == 1


class TestSimulationEngine:
    """Tests for SimulationEngine."""
    
    def test_simulation_produces_outputs(self):
        """Test that simulation produces expected outputs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            bundle_dir = tmpdir / "bundle"
            output_dir = tmpdir / "sim"
            
            # Create bundle with minimal structure
            bundle_dir.mkdir()
            (bundle_dir / "inputs").mkdir()
            (bundle_dir / "outputs").mkdir()
            
            manifest = {
                "run_id": "20260131120000-abc123",
                "command": "judge",
                "timestamp": "2026-01-31T12:00:00Z",
                "truthcore_version": "0.2.0",
                "truthcore_git_sha": None,
                "engine_versions": {},
                "config": {"hash": "abc123", "path": None, "profile": "pr"},
                "inputs": {"directory": str(bundle_dir / "inputs"), "files": []},
                "environment": {
                    "python_version": "3.11.0",
                    "python_implementation": "CPython",
                    "os": {"name": "Linux", "release": "5.0"},
                    "cpu_arch": "x86_64",
                    "timezone": "UTC",
                },
                "cache": {"hit": False, "key": None, "path": None},
                "execution": {"duration_ms": 1000, "exit_code": 0},
                "metadata": {},
            }
            
            with open(bundle_dir / "run_manifest.json", "w") as f:
                json.dump(manifest, f)
            
            # Create verdict in outputs
            verdict = {
                "verdict": "NO_SHIP",
                "version": "2.0",
                "timestamp": "2026-01-31T12:00:00Z",
                "mode": "pr",
                "profile": "default",
                "summary": {
                    "total_findings": 5,
                    "blockers": 0,
                    "highs": 3,
                    "mediums": 2,
                    "lows": 0,
                    "total_points": 150,
                },
                "inputs": [],
                "engines": [],
                "categories": [],
                "top_findings": [],
                "reasoning": {
                    "ship_reasons": [],
                    "no_ship_reasons": ["Too many highs"],
                },
                "thresholds": None,
            }
            
            with open(bundle_dir / "outputs" / "verdict.json", "w") as f:
                json.dump(verdict, f)
            
            # Create findings
            with open(bundle_dir / "outputs" / "readiness.json", "w") as f:
                json.dump({
                    "version": "0.2.0",
                    "profile": "pr",
                    "timestamp": "2026-01-31T12:00:00Z",
                    "passed": False,
                    "findings": [
                        {
                            "id": "f1",
                            "severity": "HIGH",
                            "category": "ui",
                            "message": "Test finding",
                        }
                    ],
                }, f)
            
            # Load and simulate
            bundle = ReplayBundle.load(bundle_dir)
            
            changes = SimulationChanges(
                thresholds={"max_highs": 10},
                disabled_engines=[],
            )
            
            engine = SimulationEngine()
            result = engine.simulate(bundle, output_dir, changes)
            
            # Should complete without errors
            assert result.success is True
            assert (output_dir / "verdict.json").exists()
            assert (output_dir / "verdict.md").exists()


class TestContentHash:
    """Tests for content hash computation."""
    
    def test_same_content_same_hash(self):
        """Test that identical content produces same hash."""
        data = {"key": "value", "number": 42}
        
        hash1 = compute_content_hash(data)
        hash2 = compute_content_hash(data)
        
        assert hash1 == hash2
    
    def test_allowlist_ignores_fields(self):
        """Test that allowlisted fields are ignored in hash."""
        data1 = {"key": "value", "timestamp": "2026-01-31T10:00:00Z"}
        data2 = {"key": "value", "timestamp": "2026-01-31T11:00:00Z"}
        
        hash1 = compute_content_hash(data1, allowlist={"timestamp"})
        hash2 = compute_content_hash(data2, allowlist={"timestamp"})
        
        assert hash1 == hash2
    
    def test_different_content_different_hash(self):
        """Test that different content produces different hash."""
        data1 = {"key": "value1"}
        data2 = {"key": "value2"}
        
        hash1 = compute_content_hash(data1)
        hash2 = compute_content_hash(data2)
        
        assert hash1 != hash2


class TestReplayReporter:
    """Tests for ReplayReporter."""
    
    def test_writes_reports(self):
        """Test that reporter writes both JSON and markdown."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            
            # Create a mock result
            bundle_dir = Path(tmpdir) / "bundle"
            bundle_dir.mkdir()
            
            manifest = {
                "run_id": "test",
                "command": "judge",
                "timestamp": "2026-01-31T12:00:00Z",
                "truthcore_version": "0.2.0",
                "truthcore_git_sha": None,
                "engine_versions": {},
                "config": {"hash": "abc", "path": None, "profile": "pr"},
                "inputs": {"directory": None, "files": []},
                "environment": {
                    "python_version": "3.11.0",
                    "python_implementation": "CPython",
                    "os": {"name": "Linux", "release": "5.0"},
                    "cpu_arch": "x86_64",
                    "timezone": "UTC",
                },
                "cache": {"hit": False, "key": None, "path": None},
                "execution": {"duration_ms": 1000, "exit_code": 0},
                "metadata": {},
            }
            
            with open(bundle_dir / "run_manifest.json", "w") as f:
                json.dump(manifest, f)
            
            bundle = ReplayBundle.load(bundle_dir)
            
            result = ReplayResult(
                success=True,
                bundle=bundle,
                output_dir=output_dir,
                identical=True,
            )
            
            reporter = ReplayReporter()
            paths = reporter.write_reports(result, output_dir)
            
            assert "json" in paths
            assert "markdown" in paths
            assert paths["json"].exists()
            assert paths["markdown"].exists()


class TestSimulationReporter:
    """Tests for SimulationReporter."""
    
    def test_writes_reports(self):
        """Test that reporter writes reports."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            
            # Create a mock result
            bundle_dir = Path(tmpdir) / "bundle"
            bundle_dir.mkdir()
            
            manifest = {
                "run_id": "test",
                "command": "judge",
                "timestamp": "2026-01-31T12:00:00Z",
                "truthcore_version": "0.2.0",
                "truthcore_git_sha": None,
                "engine_versions": {},
                "config": {"hash": "abc", "path": None, "profile": "pr"},
                "inputs": {"directory": None, "files": []},
                "environment": {
                    "python_version": "3.11.0",
                    "python_implementation": "CPython",
                    "os": {"name": "Linux", "release": "5.0"},
                    "cpu_arch": "x86_64",
                    "timezone": "UTC",
                },
                "cache": {"hit": False, "key": None, "path": None},
                "execution": {"duration_ms": 1000, "exit_code": 0},
                "metadata": {},
            }
            
            with open(bundle_dir / "run_manifest.json", "w") as f:
                json.dump(manifest, f)
            
            bundle = ReplayBundle.load(bundle_dir)
            
            changes = SimulationChanges()
            
            result = SimulationResult(
                success=True,
                bundle=bundle,
                output_dir=output_dir,
                changes=changes,
            )
            
            reporter = SimulationReporter()
            paths = reporter.write_reports(result, output_dir)
            
            assert "json" in paths
            assert "markdown" in paths
            assert paths["json"].exists()
            assert paths["markdown"].exists()
