# Truth Graph

The Truth Graph is a graph model linking runs, engines, findings, evidence, and entities. It provides a queryable representation of verification results.

## Overview

```
Run ──executed──▶ Engine ──produced──▶ Finding ──supported_by──▶ Evidence
 │                                      │
 │                                      └──affects──▶ Entity (file_path)
 │                                      └──affects──▶ Entity (route)
 └──belongs_to──▶ Run Plan
```

## Node Types

### Run
Represents a verification run:
```json
{
  "id": "run_20260131153000a1b2c3d4",
  "type": "run",
  "properties": {
    "run_id": "20260131153000-a1b2c3d4",
    "command": "judge",
    "config": {"profile": "api"},
    "manifest_path": "...",
    "run_plan_path": "..."
  }
}
```

### Engine
Represents an executed engine:
```json
{
  "id": "engine_run123_readiness",
  "type": "engine",
  "properties": {
    "engine_id": "readiness",
    "engine_type": "readiness",
    "run_id": "20260131153000-a1b2c3d4"
  }
}
```

### Finding
Represents a verification finding:
```json
{
  "id": "finding_run123_readiness_finding_0",
  "type": "finding",
  "properties": {
    "finding_id": "finding_0",
    "engine_id": "readiness",
    "severity": "high",
    "message": "API route missing validation",
    "rule_id": "api_contract_compliance"
  }
}
```

### Evidence
Represents supporting evidence:
```json
{
  "id": "evidence_run123_finding_0_ev_0",
  "type": "evidence",
  "properties": {
    "evidence_id": "ev_0",
    "evidence_type": "finding_evidence",
    "content": {"file": "src/api/users.py", "line": 5}
  }
}
```

### Entity
Represents affected entities:
```json
{
  "id": "entity_file_path_srcapiuserspy",
  "type": "entity",
  "properties": {
    "entity_type": "file_path",
    "entity_id": "src/api/users.py",
    "name": "src/api/users.py"
  }
}
```

## Entity Types

- **file_path**: File paths
- **route**: API routes/endpoints
- **component**: Classes, functions, components
- **invariant_rule**: Invariant rule IDs
- **adapter**: Adapter names
- **dependency**: Import dependencies
- **api_endpoint**: API endpoint URLs
- **module**: Module names
- **config**: Configuration keys

## Edge Types

| Edge Type | From | To | Meaning |
|-----------|------|-----|---------|
| **executed** | Run | Engine | Run executed engine |
| **produced** | Engine | Finding | Engine produced finding |
| **supported_by** | Finding | Evidence | Finding supported by evidence |
| **affects** | Finding | Entity | Finding affects entity |
| **depends_on** | Entity | Entity | Entity depends on another |
| **belongs_to** | Engine | Run | Engine belongs to run |

## CLI Usage

### Build Truth Graph

```bash
truthctl graph \
  --run-dir ./results \
  --plan ./run_plan.json \
  --out ./graph \
  --format json
```

### Export Formats

```bash
# JSON only
truthctl graph --run-dir ./results --out ./graph --format json

# Parquet (requires pyarrow)
truthctl graph --run-dir ./results --out ./graph --format parquet

# Both
truthctl graph --run-dir ./results --out ./graph --format both
```

### Query Truth Graph

```bash
# Find high severity findings
truthctl graph-query \
  --graph ./graph/truth_graph.json \
  --where "severity=high"

# Find findings affecting specific file
truthctl graph-query \
  --graph ./graph/truth_graph.json \
  --where "name=contains:users.py"

# Find all findings with severity >= medium
truthctl graph-query \
  --graph ./graph/truth_graph.json \
  --where "severity>=medium" \
  --out results.json
```

## Query Syntax

### Exact Match
```
key=value
```
Examples:
- `severity=high`
- `type=finding`
- `command=judge`

### Contains Match
```
key=contains:substring
```
Examples:
- `name=contains:users.py`
- `message=contains:validation`

### Severity Comparison
```
severity>=level
```
Examples:
- `severity>=medium` (matches medium, high, critical, blocker)
- `severity>=high` (matches high, critical, blocker)

Severity order: info < low < medium < high < critical < blocker

## API Usage

```python
from truthcore.truth_graph import TruthGraph, TruthGraphBuilder
from truthcore.truth_graph import Severity, EntityType

# Build from run directory
builder = TruthGraphBuilder()
graph = builder.build_from_run_directory(
    run_dir=Path("./results"),
    run_plan_path=Path("./run_plan.json")
)

# Export to JSON
graph.to_json(Path("./truth_graph.json"))

# Export to Parquet (requires pyarrow)
graph.to_parquet(Path("./truth_graph.parquet"))

# Query by type
findings = graph.query(node_type=NodeType.FINDING)

# Query by severity
high_findings = graph.query(
    node_type=NodeType.FINDING,
    severity=Severity.HIGH
)

# Simple query
results = graph.query_simple("severity>=medium")

# Get connected nodes
finding = graph.nodes["finding_123"]
connected = graph.get_connected(finding.id)

# Load existing graph
graph = TruthGraph.from_json(Path("./truth_graph.json"))
```

## Output Formats

### JSON
```json
{
  "version": "1.0.0",
  "created_at": "2026-01-31T15:30:00Z",
  "nodes": [...],
  "edges": [...],
  "stats": {
    "node_count": 8,
    "edge_count": 7
  }
}
```

### Parquet
Two files:
- `nodes.parquet` - All nodes with properties
- `edges.parquet` - All edges with relationships

## Integration with Run Plan

When run plan is provided during graph building, the graph includes:
- References to run_plan_path in run nodes
- Engine selections from plan
- Invariant selections from plan
- Impact levels from plan

## Examples

See `examples/truth_graph/` for example files:
- `truth_graph_example.json` - Sample graph output
