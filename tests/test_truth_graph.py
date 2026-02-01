"""Unit tests for Truth Graph."""

from __future__ import annotations

import pytest
import json
from pathlib import Path
from truthcore.truth_graph import (
    TruthGraph,
    TruthGraphBuilder,
    Node,
    Edge,
    NodeType,
    EdgeType,
    Severity,
    EntityType,
)


class TestNode:
    """Test Node dataclass."""

    def test_node_creation(self):
        """Test creating a node."""
        node = Node(
            id="run_123",
            type=NodeType.RUN,
            label="Run: 123",
            properties={"run_id": "123", "command": "judge"},
        )
        
        assert node.id == "run_123"
        assert node.type == NodeType.RUN
        assert node.properties["run_id"] == "123"

    def test_node_to_dict(self):
        """Test node serialization."""
        node = Node(
            id="run_123",
            type=NodeType.RUN,
            label="Run: 123",
            properties={"run_id": "123"},
        )
        
        data = node.to_dict()
        assert data["id"] == "run_123"
        assert data["type"] == "run"
        assert data["properties"]["run_id"] == "123"


class TestEdge:
    """Test Edge dataclass."""

    def test_edge_creation(self):
        """Test creating an edge."""
        edge = Edge(
            id="edge_1",
            source="run_123",
            target="engine_456",
            type=EdgeType.EXECUTED,
        )
        
        assert edge.source == "run_123"
        assert edge.target == "engine_456"
        assert edge.type == EdgeType.EXECUTED


class TestTruthGraph:
    """Test TruthGraph operations."""

    def test_add_run(self):
        """Test adding a run node."""
        graph = TruthGraph()
        node = graph.add_run("run-123", "judge", {"profile": "test"})
        
        assert node.id in graph.nodes
        assert node.type == NodeType.RUN
        assert node.properties["run_id"] == "run-123"

    def test_add_engine(self):
        """Test adding an engine node."""
        graph = TruthGraph()
        
        # First add a run
        graph.add_run("run-123", "judge", {})
        
        # Add engine
        engine = graph.add_engine("readiness", "run-123", "readiness")
        
        assert engine.id in graph.nodes
        assert engine.type == NodeType.ENGINE
        
        # Should have edge to run
        run_id = graph._make_id("run", "run-123")
        edges_to_engine = [e for e in graph.edges.values() if e.target == engine.id]
        assert len(edges_to_engine) == 1
        assert edges_to_engine[0].source == run_id

    def test_add_finding(self):
        """Test adding a finding node."""
        graph = TruthGraph()
        
        graph.add_run("run-123", "judge", {})
        graph.add_engine("readiness", "run-123", "readiness")
        
        finding = graph.add_finding(
            finding_id="finding-1",
            engine_id="readiness",
            run_id="run-123",
            severity=Severity.HIGH,
            message="Test finding",
        )
        
        assert finding.id in graph.nodes
        assert finding.type == NodeType.FINDING
        assert finding.properties["severity"] == "high"

    def test_add_evidence(self):
        """Test adding evidence node."""
        graph = TruthGraph()
        
        graph.add_run("run-123", "judge", {})
        graph.add_engine("readiness", "run-123", "readiness")
        graph.add_finding("finding-1", "readiness", "run-123", Severity.HIGH, "Test")
        
        evidence = graph.add_evidence(
            evidence_id="ev-1",
            finding_id="finding-1",
            engine_id="readiness",
            run_id="run-123",
            evidence_type="test",
            content={"key": "value"},
        )
        
        assert evidence.id in graph.nodes
        assert evidence.type == NodeType.EVIDENCE

    def test_add_entity(self):
        """Test adding entity node."""
        graph = TruthGraph()
        
        entity = graph.add_entity(EntityType.FILE_PATH, "src/main.py", "src/main.py")
        
        assert entity.id in graph.nodes
        assert entity.type == NodeType.ENTITY
        assert entity.properties["entity_type"] == "file_path"

    def test_link_finding_to_entity(self):
        """Test linking finding to entity."""
        graph = TruthGraph()
        
        graph.add_run("run-123", "judge", {})
        graph.add_engine("readiness", "run-123", "readiness")
        graph.add_finding("finding-1", "readiness", "run-123", Severity.HIGH, "Test")
        graph.add_entity(EntityType.FILE_PATH, "src/main.py", "src/main.py")
        
        graph.link_finding_to_entity("finding-1", "readiness", "run-123", EntityType.FILE_PATH, "src/main.py")
        
        # Should have affect edge
        finding_id = graph._make_id("finding", "run-123", "readiness", "finding-1")
        entity_id = graph._make_id("entity", "file_path", "src/main.py")
        
        affect_edges = [e for e in graph.edges.values() if e.type == EdgeType.AFFECTS and e.source == finding_id and e.target == entity_id]
        assert len(affect_edges) == 1

    def test_query_by_type(self):
        """Test querying nodes by type."""
        graph = TruthGraph()
        
        graph.add_run("run-123", "judge", {})
        graph.add_engine("readiness", "run-123", "readiness")
        graph.add_finding("finding-1", "readiness", "run-123", Severity.HIGH, "Test")
        
        runs = graph.query(node_type=NodeType.RUN)
        assert len(runs) == 1
        
        engines = graph.query(node_type=NodeType.ENGINE)
        assert len(engines) == 1

    def test_query_by_severity(self):
        """Test querying by severity."""
        graph = TruthGraph()
        
        graph.add_run("run-123", "judge", {})
        graph.add_engine("readiness", "run-123", "readiness")
        graph.add_finding("finding-1", "readiness", "run-123", Severity.HIGH, "High severity")
        graph.add_finding("finding-2", "readiness", "run-123", Severity.LOW, "Low severity")
        
        high_findings = graph.query(node_type=NodeType.FINDING, severity=Severity.HIGH)
        assert len(high_findings) == 1
        assert high_findings[0].properties["message"] == "High severity"

    def test_query_simple_exact_match(self):
        """Test simple query with exact match."""
        graph = TruthGraph()
        
        graph.add_run("run-123", "judge", {})
        graph.add_run("run-456", "recon", {})
        
        results = graph.query_simple("command=judge")
        assert len(results) == 1
        assert results[0].properties["run_id"] == "run-123"

    def test_query_simple_contains(self):
        """Test simple query with contains."""
        graph = TruthGraph()
        
        graph.add_run("run-123", "judge", {"path": "/test/judge/run"})
        
        results = graph.query_simple("path=contains:judge")
        assert len(results) == 1

    def test_query_simple_severity_comparison(self):
        """Test simple query with severity comparison."""
        graph = TruthGraph()
        
        graph.add_run("run-123", "judge", {})
        graph.add_engine("readiness", "run-123", "readiness")
        graph.add_finding("finding-1", "readiness", "run-123", Severity.HIGH, "High")
        graph.add_finding("finding-2", "readiness", "run-123", Severity.LOW, "Low")
        
        results = graph.query_simple("severity>=medium")
        assert len(results) == 1
        assert results[0].properties["severity"] == "high"

    def test_get_connected(self):
        """Test getting connected nodes."""
        graph = TruthGraph()
        
        run = graph.add_run("run-123", "judge", {})
        graph.add_engine("readiness", "run-123", "readiness")
        
        connected = graph.get_connected(run.id)
        assert len(connected) == 1
        assert connected[0].type == NodeType.ENGINE

    def test_to_dict(self):
        """Test graph serialization."""
        graph = TruthGraph()
        graph.add_run("run-123", "judge", {})
        
        data = graph.to_dict()
        assert data["version"] == "1.0.0"
        assert "nodes" in data
        assert "edges" in data
        assert "stats" in data
        assert data["stats"]["node_count"] == 1

    def test_to_json(self, tmp_path: Path):
        """Test exporting to JSON."""
        graph = TruthGraph()
        graph.add_run("run-123", "judge", {})
        
        output_path = tmp_path / "truth_graph.json"
        graph.to_json(output_path)
        
        assert output_path.exists()
        
        with open(output_path) as f:
            data = json.load(f)
        
        assert data["version"] == "1.0.0"
        assert len(data["nodes"]) == 1

    def test_from_dict(self):
        """Test loading from dictionary."""
        data = {
            "version": "1.0.0",
            "created_at": "2026-01-31T12:00:00Z",
            "metadata": {},
            "nodes": [
                {
                    "id": "run_123",
                    "type": "run",
                    "label": "Run: 123",
                    "properties": {"run_id": "123"},
                    "timestamp": "2026-01-31T12:00:00Z",
                }
            ],
            "edges": [],
        }
        
        graph = TruthGraph.from_dict(data)
        assert "run_123" in graph.nodes
        assert graph.nodes["run_123"].type == NodeType.RUN

    def test_from_json(self, tmp_path: Path):
        """Test loading from JSON file."""
        data = {
            "version": "1.0.0",
            "created_at": "2026-01-31T12:00:00Z",
            "metadata": {},
            "nodes": [
                {
                    "id": "run_123",
                    "type": "run",
                    "label": "Run: 123",
                    "properties": {"run_id": "123"},
                    "timestamp": "2026-01-31T12:00:00Z",
                }
            ],
            "edges": [],
        }
        
        input_path = tmp_path / "truth_graph.json"
        with open(input_path, "w") as f:
            json.dump(data, f)
        
        graph = TruthGraph.from_json(input_path)
        assert "run_123" in graph.nodes


class TestTruthGraphBuilder:
    """Test TruthGraphBuilder."""

    def test_add_run_from_manifest(self, tmp_path: Path):
        """Test adding run from manifest."""
        manifest = {
            "run_id": "test-123",
            "command": "judge",
            "timestamp": "2026-01-31T12:00:00Z",
            "config": {"profile": "test"},
        }
        
        manifest_path = tmp_path / "run_manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f)
        
        builder = TruthGraphBuilder()
        node = builder.add_run_from_manifest(manifest_path)
        
        assert node.type == NodeType.RUN
        assert node.properties["run_id"] == "test-123"
        assert node.properties["command"] == "judge"

    def test_add_findings_from_readiness(self, tmp_path: Path):
        """Test adding findings from readiness output."""
        # Create manifest
        manifest = {
            "run_id": "test-123",
            "command": "judge",
            "timestamp": "2026-01-31T12:00:00Z",
            "config": {},
        }
        manifest_path = tmp_path / "run_manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f)
        
        # Create readiness output
        readiness = {
            "version": "0.2.0",
            "findings": [
                {
                    "severity": "high",
                    "message": "Test finding",
                    "rule_id": "test-rule",
                    "evidence": {"key": "value"},
                }
            ],
        }
        readiness_path = tmp_path / "readiness.json"
        with open(readiness_path, "w") as f:
            json.dump(readiness, f)
        
        builder = TruthGraphBuilder()
        builder.add_run_from_manifest(manifest_path)
        nodes = builder.add_findings_from_readiness("test-123", readiness_path)
        
        assert len(nodes) == 1
        assert nodes[0].type == NodeType.FINDING

    def test_build_from_run_directory(self, tmp_path: Path):
        """Test building graph from run directory."""
        # Create manifest
        manifest = {
            "run_id": "test-123",
            "command": "judge",
            "timestamp": "2026-01-31T12:00:00Z",
            "config": {},
        }
        with open(tmp_path / "run_manifest.json", "w") as f:
            json.dump(manifest, f)
        
        # Create readiness output
        readiness = {
            "version": "0.2.0",
            "findings": [],
        }
        with open(tmp_path / "readiness.json", "w") as f:
            json.dump(readiness, f)
        
        builder = TruthGraphBuilder()
        graph = builder.build_from_run_directory(tmp_path)
        
        # Should have run and engine nodes
        run_nodes = [n for n in graph.nodes.values() if n.type == NodeType.RUN]
        engine_nodes = [n for n in graph.nodes.values() if n.type == NodeType.ENGINE]
        
        assert len(run_nodes) == 1
        assert len(engine_nodes) == 1
