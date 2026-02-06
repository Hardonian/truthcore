"""Truth Graph - graph model linking runs, engines, findings, evidence, and entities."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any


class NodeType(Enum):
    """Types of nodes in the truth graph."""

    RUN = "run"
    ENGINE = "engine"
    FINDING = "finding"
    EVIDENCE = "evidence"
    ENTITY = "entity"


class EdgeType(Enum):
    """Types of edges (relationships) in the truth graph."""

    EXECUTED = "executed"
    PRODUCED = "produced"
    SUPPORTED_BY = "supported_by"
    AFFECTS = "affects"
    DEPENDS_ON = "depends_on"
    BELONGS_TO = "belongs_to"


class Severity(Enum):
    """Severity levels for findings."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    BLOCKER = "blocker"


class EntityType(Enum):
    """Types of entities that can be affected."""

    FILE_PATH = "file_path"
    ROUTE = "route"
    COMPONENT = "component"
    INVARIANT_RULE = "invariant_rule"
    ADAPTER = "adapter"
    DEPENDENCY = "dependency"
    API_ENDPOINT = "api_endpoint"
    MODULE = "module"
    CONFIG = "config"


@dataclass
class Node:
    """A node in the truth graph."""

    id: str
    type: NodeType
    label: str
    properties: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert node to dictionary."""
        return {
            "id": self.id,
            "type": self.type.value,
            "label": self.label,
            "properties": dict(sorted(self.properties.items())),
            "timestamp": self.timestamp,
        }


@dataclass
class Edge:
    """An edge (relationship) in the truth graph."""

    id: str
    source: str
    target: str
    type: EdgeType
    properties: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert edge to dictionary."""
        return {
            "id": self.id,
            "source": self.source,
            "target": self.target,
            "type": self.type.value,
            "properties": dict(sorted(self.properties.items())),
            "timestamp": self.timestamp,
        }


@dataclass
class TruthGraph:
    """Graph model for truth relationships.

    Links:
        Run -> Engine -> Finding -> Evidence -> Entities
    """

    version: str = "1.0.0"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    nodes: dict[str, Node] = field(default_factory=dict)
    edges: dict[str, Edge] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def _make_id(self, prefix: str, *parts: str) -> str:
        """Generate a deterministic ID."""
        import hashlib

        content = "|".join([prefix] + list(parts))
        hash_part = hashlib.blake2b(content.encode(), digest_size=8).hexdigest()
        return f"{prefix}_{hash_part}"

    def add_run(
        self,
        run_id: str,
        command: str,
        config: dict[str, Any] | None = None,
        manifest_path: str | None = None,
        run_plan_path: str | None = None,
        **properties: Any,
    ) -> Node:
        """Add a run node to the graph."""
        node_id = self._make_id("run", run_id)

        props = {
            "run_id": run_id,
            "command": command,
            "config": config or {},
            "manifest_path": manifest_path,
            "run_plan_path": run_plan_path,
            **properties,
        }

        node = Node(
            id=node_id,
            type=NodeType.RUN,
            label=f"Run: {run_id}",
            properties=props,
        )

        self.nodes[node_id] = node
        return node

    def add_engine(
        self,
        engine_id: str,
        run_id: str,
        engine_type: str,
        version: str | None = None,
        **properties: Any,
    ) -> Node:
        """Add an engine execution node to the graph."""
        node_id = self._make_id("engine", run_id, engine_id)

        props = {
            "engine_id": engine_id,
            "engine_type": engine_type,
            "run_id": run_id,
            "version": version,
            **properties,
        }

        node = Node(
            id=node_id,
            type=NodeType.ENGINE,
            label=f"Engine: {engine_id}",
            properties=props,
        )

        self.nodes[node_id] = node

        # Link to run
        run_node_id = self._make_id("run", run_id)
        if run_node_id in self.nodes:
            self.add_edge(run_node_id, node_id, EdgeType.EXECUTED)

        return node

    def add_finding(
        self,
        finding_id: str,
        engine_id: str,
        run_id: str,
        severity: Severity,
        message: str,
        rule_id: str | None = None,
        **properties: Any,
    ) -> Node:
        """Add a finding node to the graph."""
        node_id = self._make_id("finding", run_id, engine_id, finding_id)

        props = {
            "finding_id": finding_id,
            "engine_id": engine_id,
            "run_id": run_id,
            "severity": severity.value,
            "message": message,
            "rule_id": rule_id,
            **properties,
        }

        node = Node(
            id=node_id,
            type=NodeType.FINDING,
            label=f"Finding: {finding_id}",
            properties=props,
        )

        self.nodes[node_id] = node

        # Link to engine
        engine_node_id = self._make_id("engine", run_id, engine_id)
        if engine_node_id in self.nodes:
            self.add_edge(engine_node_id, node_id, EdgeType.PRODUCED)

        return node

    def add_evidence(
        self,
        evidence_id: str,
        finding_id: str,
        engine_id: str,
        run_id: str,
        evidence_type: str,
        content: dict[str, Any] | str,
        **properties: Any,
    ) -> Node:
        """Add an evidence node to the graph."""
        node_id = self._make_id("evidence", run_id, finding_id, evidence_id)

        props = {
            "evidence_id": evidence_id,
            "finding_id": finding_id,
            "engine_id": engine_id,
            "run_id": run_id,
            "evidence_type": evidence_type,
            "content": content,
            **properties,
        }

        node = Node(
            id=node_id,
            type=NodeType.EVIDENCE,
            label=f"Evidence: {evidence_id}",
            properties=props,
        )

        self.nodes[node_id] = node

        # Link to finding
        finding_node_id = self._make_id("finding", run_id, engine_id, finding_id)
        if finding_node_id in self.nodes:
            self.add_edge(finding_node_id, node_id, EdgeType.SUPPORTED_BY)

        return node

    def add_entity(
        self,
        entity_type: EntityType,
        entity_id: str,
        name: str,
        **properties: Any,
    ) -> Node:
        """Add an entity node to the graph."""
        node_id = self._make_id("entity", entity_type.value, entity_id)

        props = {
            "entity_type": entity_type.value,
            "entity_id": entity_id,
            "name": name,
            **properties,
        }

        node = Node(
            id=node_id,
            type=NodeType.ENTITY,
            label=f"{entity_type.value}: {name}",
            properties=props,
        )

        self.nodes[node_id] = node
        return node

    def add_edge(
        self,
        source: str,
        target: str,
        edge_type: EdgeType,
        **properties: Any,
    ) -> Edge:
        """Add an edge between two nodes."""
        edge_id = self._make_id("edge", source, target, edge_type.value)

        edge = Edge(
            id=edge_id,
            source=source,
            target=target,
            type=edge_type,
            properties=properties,
        )

        self.edges[edge_id] = edge
        return edge

    def link_finding_to_entity(
        self,
        finding_id: str,
        engine_id: str,
        run_id: str,
        entity_type: EntityType,
        entity_id: str,
    ) -> None:
        """Link a finding to an affected entity."""
        finding_node_id = self._make_id("finding", run_id, engine_id, finding_id)
        entity_node_id = self._make_id("entity", entity_type.value, entity_id)

        # Ensure entity exists
        if entity_node_id not in self.nodes:
            self.add_entity(entity_type, entity_id, entity_id)

        # Add affect relationship
        self.add_edge(finding_node_id, entity_node_id, EdgeType.AFFECTS)

    def query(
        self,
        node_type: NodeType | None = None,
        properties: dict[str, Any] | None = None,
        severity: Severity | None = None,
    ) -> list[Node]:
        """Query nodes with filters.

        Args:
            node_type: Filter by node type
            properties: Filter by properties (key=value)
            severity: Filter findings by severity

        Returns:
            List of matching nodes
        """
        results: list[Node] = []

        for node in self.nodes.values():
            # Filter by type
            if node_type and node.type != node_type:
                continue

            # Filter by severity
            if severity and node.type == NodeType.FINDING:
                if node.properties.get("severity") != severity.value:
                    continue

            # Filter by properties
            if properties:
                match = True
                for key, value in properties.items():
                    if node.properties.get(key) != value:
                        match = False
                        break
                if not match:
                    continue

            results.append(node)

        return results

    def query_simple(self, predicate: str) -> list[Node]:
        """Simple query with predicate string.

        Supports:
            - key=value (exact match)
            - key=contains:substring (contains match)
            - severity>=level (severity >= level)

        Args:
            predicate: Query predicate string

        Returns:
            List of matching nodes
        """
        results: list[Node] = []

        # Parse predicate
        if ">=" in predicate and "severity" in predicate:
            # Severity comparison
            level = predicate.split(">=")[1].strip()
            severity_levels = ["info", "low", "medium", "high", "critical", "blocker"]
            if level in severity_levels:
                min_index = severity_levels.index(level)
                for node in self.nodes.values():
                    if node.type == NodeType.FINDING:
                        node_sev = node.properties.get("severity", "info")
                        if node_sev in severity_levels:
                            if severity_levels.index(node_sev) >= min_index:
                                results.append(node)

        elif "contains:" in predicate:
            # Contains match
            key, value = predicate.split("=contains:", 1)
            key = key.strip()
            value = value.strip()
            for node in self.nodes.values():
                if key in node.properties:
                    prop_value = str(node.properties[key])
                    if value in prop_value:
                        results.append(node)

        elif "=" in predicate:
            # Exact match
            key, value = predicate.split("=", 1)
            key = key.strip()
            value = value.strip()
            for node in self.nodes.values():
                if str(node.properties.get(key)) == value:
                    results.append(node)

        return results

    def get_connected(self, node_id: str, edge_type: EdgeType | None = None) -> list[Node]:
        """Get nodes connected to a given node."""
        connected: list[Node] = []

        for edge in self.edges.values():
            if edge_type and edge.type != edge_type:
                continue

            if edge.source == node_id and edge.target in self.nodes:
                connected.append(self.nodes[edge.target])
            elif edge.target == node_id and edge.source in self.nodes:
                connected.append(self.nodes[edge.source])

        return connected

    def to_dict(self) -> dict[str, Any]:
        """Convert graph to dictionary."""
        return {
            "version": self.version,
            "created_at": self.created_at,
            "metadata": dict(sorted(self.metadata.items())),
            "nodes": [n.to_dict() for n in sorted(self.nodes.values(), key=lambda x: x.id)],
            "edges": [e.to_dict() for e in sorted(self.edges.values(), key=lambda x: x.id)],
            "stats": {
                "node_count": len(self.nodes),
                "edge_count": len(self.edges),
            },
        }

    def to_json(self, output_path: Path) -> None:
        """Export graph to JSON file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, sort_keys=True)

    def to_parquet(self, output_path: Path) -> None:
        """Export graph to Parquet files (nodes and edges)."""
        try:
            import pandas as pd

            # Convert nodes to DataFrame
            nodes_data = []
            for node in self.nodes.values():
                row = {
                    "id": node.id,
                    "type": node.type.value,
                    "label": node.label,
                    "timestamp": node.timestamp,
                    **node.properties,
                }
                nodes_data.append(row)

            # Convert edges to DataFrame
            edges_data = []
            for edge in self.edges.values():
                row = {
                    "id": edge.id,
                    "source": edge.source,
                    "target": edge.target,
                    "type": edge.type.value,
                    "timestamp": edge.timestamp,
                    **edge.properties,
                }
                edges_data.append(row)

            # Write to Parquet
            import pyarrow as pa
            import pyarrow.parquet as pq

            if nodes_data:
                df_nodes = pd.DataFrame(nodes_data)
                table_nodes = pa.Table.from_pandas(df_nodes)
                pq.write_table(table_nodes, str(output_path / "nodes.parquet"))

            if edges_data:
                df_edges = pd.DataFrame(edges_data)
                table_edges = pa.Table.from_pandas(df_edges)
                pq.write_table(table_edges, str(output_path / "edges.parquet"))

        except ImportError as err:
            raise RuntimeError("Parquet support requires pyarrow and pandas") from err

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TruthGraph:
        """Create graph from dictionary."""
        graph = cls(
            version=data.get("version", "1.0.0"),
            created_at=data.get("created_at", datetime.now(UTC).isoformat()),
            metadata=data.get("metadata", {}),
        )

        # Reconstruct nodes
        for node_data in data.get("nodes", []):
            node = Node(
                id=node_data["id"],
                type=NodeType(node_data["type"]),
                label=node_data["label"],
                properties=node_data.get("properties", {}),
                timestamp=node_data.get("timestamp", datetime.now(UTC).isoformat()),
            )
            graph.nodes[node.id] = node

        # Reconstruct edges
        for edge_data in data.get("edges", []):
            edge = Edge(
                id=edge_data["id"],
                source=edge_data["source"],
                target=edge_data["target"],
                type=EdgeType(edge_data["type"]),
                properties=edge_data.get("properties", {}),
                timestamp=edge_data.get("timestamp", datetime.now(UTC).isoformat()),
            )
            graph.edges[edge.id] = edge

        return graph

    @classmethod
    def from_json(cls, input_path: Path) -> TruthGraph:
        """Load graph from JSON file."""
        with open(input_path, encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)


class TruthGraphBuilder:
    """Builder for constructing truth graphs from run outputs."""

    def __init__(self):
        self.graph = TruthGraph()

    def add_run_from_manifest(
        self,
        manifest_path: Path,
        run_plan_path: Path | None = None,
    ) -> Node:
        """Add a run node from a run manifest."""
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)

        run_id = manifest.get("run_id", "unknown")
        command = manifest.get("command", "unknown")
        config = manifest.get("config", {})

        return self.graph.add_run(
            run_id=run_id,
            command=command,
            config=config,
            manifest_path=str(manifest_path),
            run_plan_path=str(run_plan_path) if run_plan_path else None,
            timestamp=manifest.get("timestamp"),
        )

    def add_findings_from_readiness(
        self,
        run_id: str,
        readiness_path: Path,
    ) -> list[Node]:
        """Add findings from readiness output."""
        nodes: list[Node] = []

        try:
            with open(readiness_path, encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return nodes

        # Add readiness engine node
        self.graph.add_engine(
            engine_id="readiness",
            run_id=run_id,
            engine_type="readiness",
        )

        # Process findings
        findings = data.get("findings", [])
        for idx, finding in enumerate(findings):
            finding_id = f"finding_{idx}"
            severity = Severity(finding.get("severity", "info"))
            message = finding.get("message", "")
            rule_id = finding.get("rule_id")

            finding_node = self.graph.add_finding(
                finding_id=finding_id,
                engine_id="readiness",
                run_id=run_id,
                severity=severity,
                message=message,
                rule_id=rule_id,
            )
            nodes.append(finding_node)

            # Add evidence
            if "evidence" in finding:
                self.graph.add_evidence(
                    evidence_id=f"ev_{idx}",
                    finding_id=finding_id,
                    engine_id="readiness",
                    run_id=run_id,
                    evidence_type="finding_evidence",
                    content=finding["evidence"],
                )

            # Link to entities
            for entity in finding.get("affected_entities", []):
                entity_type, entity_id = self._parse_entity(entity)
                self.graph.link_finding_to_entity(
                    finding_id=finding_id,
                    engine_id="readiness",
                    run_id=run_id,
                    entity_type=entity_type,
                    entity_id=entity_id,
                )

        return nodes

    def _parse_entity(self, entity_str: str) -> tuple[EntityType, str]:
        """Parse entity string into type and ID."""
        if ":" in entity_str:
            type_str, entity_id = entity_str.split(":", 1)
            try:
                return EntityType(type_str), entity_id
            except ValueError:
                return EntityType.FILE_PATH, entity_id
        return EntityType.FILE_PATH, entity_str

    def add_findings_from_recon(
        self,
        run_id: str,
        recon_path: Path,
    ) -> list[Node]:
        """Add findings from reconciliation output."""
        nodes: list[Node] = []

        try:
            with open(recon_path, encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return nodes

        # Add reconciliation engine node
        self.graph.add_engine(
            engine_id="reconciliation",
            run_id=run_id,
            engine_type="reconciliation",
        )

        # Process mismatches as findings
        mismatches = data.get("mismatches", [])
        for idx, mismatch in enumerate(mismatches):
            finding_id = f"mismatch_{idx}"

            finding_node = self.graph.add_finding(
                finding_id=finding_id,
                engine_id="reconciliation",
                run_id=run_id,
                severity=Severity.HIGH,
                message=mismatch.get("message", "Data mismatch detected"),
            )
            nodes.append(finding_node)

            # Add evidence
            self.graph.add_evidence(
                evidence_id=f"ev_recon_{idx}",
                finding_id=finding_id,
                engine_id="reconciliation",
                run_id=run_id,
                evidence_type="mismatch_data",
                content=mismatch,
            )

        return nodes

    def add_findings_from_trace(
        self,
        run_id: str,
        trace_path: Path,
    ) -> list[Node]:
        """Add findings from agent trace output."""
        nodes: list[Node] = []

        try:
            with open(trace_path, encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return nodes

        # Add trace engine node
        self.graph.add_engine(
            engine_id="agent_trace",
            run_id=run_id,
            engine_type="agent_trace",
        )

        # Process trace findings
        violations = data.get("violations", [])
        for idx, violation in enumerate(violations):
            finding_id = f"violation_{idx}"

            finding_node = self.graph.add_finding(
                finding_id=finding_id,
                engine_id="agent_trace",
                run_id=run_id,
                severity=Severity(violation.get("severity", "medium")),
                message=violation.get("message", "Trace violation"),
            )
            nodes.append(finding_node)

        return nodes

    def build_from_run_directory(
        self,
        run_dir: Path,
        run_plan_path: Path | None = None,
    ) -> TruthGraph:
        """Build complete graph from a run output directory."""
        manifest_path = run_dir / "run_manifest.json"

        if not manifest_path.exists():
            raise ValueError(f"No manifest found in {run_dir}")

        # Add run
        run_node = self.add_run_from_manifest(manifest_path, run_plan_path)
        run_id = run_node.properties.get("run_id", "unknown")

        # Add findings from various outputs
        self.add_findings_from_readiness(run_id, run_dir / "readiness.json")
        self.add_findings_from_recon(run_id, run_dir / "recon_run.json")
        self.add_findings_from_trace(run_id, run_dir / "trace_report.json")

        # Add UI geometry findings if present
        ui_geo_path = run_dir / "ui_geometry.json"
        if ui_geo_path.exists():
            self._add_ui_geometry_findings(run_id, ui_geo_path)

        return self.graph

    def _add_ui_geometry_findings(
        self,
        run_id: str,
        ui_geo_path: Path,
    ) -> list[Node]:
        """Add findings from UI geometry output."""
        nodes: list[Node] = []

        try:
            with open(ui_geo_path, encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return nodes

        # Add UI geometry engine node
        self.graph.add_engine(
            engine_id="ui_geometry",
            run_id=run_id,
            engine_type="ui_geometry",
        )

        # Process reachability issues
        issues = data.get("reachability_issues", [])
        for idx, issue in enumerate(issues):
            finding_id = f"ui_issue_{idx}"

            finding_node = self.graph.add_finding(
                finding_id=finding_id,
                engine_id="ui_geometry",
                run_id=run_id,
                severity=Severity.MEDIUM,
                message=issue.get("message", "UI reachability issue"),
            )
            nodes.append(finding_node)

        return nodes
