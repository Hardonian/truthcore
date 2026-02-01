# Change Impact Engine

The Change Impact Engine analyzes git diffs or changed file lists to determine which engines and invariants should be run. This enables selective testing based on actual code changes.

## Overview

```
┌─────────────────┐     ┌──────────────────┐     ┌──────────────┐
│   Git Diff      │────▶│  Impact Engine   │────▶│  Run Plan    │
│  Changed Files  │     │   (analysis)     │     │  (output)    │
└─────────────────┘     └──────────────────┘     └──────────────┘
```

## Features

- **Deterministic**: Same inputs always produce same outputs
- **Cacheable**: Run plans have content-addressed cache keys
- **Explainable**: Includes reasons for inclusion/exclusion decisions
- **Flexible**: Supports both git diff text and file lists

## Usage

### Generate Run Plan from Git Diff

```bash
truthctl plan --diff changes.diff --out run_plan.json
```

### Generate Run Plan from Changed Files

```bash
truthctl plan --changed-files changed_files.txt --out run_plan.json
```

### Run Judge with Impact Analysis

```bash
# Automatically generate and use run plan
truthctl judge \
  --diff changes.diff \
  --inputs ./test-data \
  --out ./results \
  --plan-out ./run_plan.json
```

## Run Plan Structure

```json
{
  "version": "1.0.0",
  "timestamp": "2026-01-31T15:30:00Z",
  "source": "changes.diff",
  "source_type": "git_diff",
  "cache_key": "a1b2c3d4...",
  "impact_summary": {
    "total_changes": 3,
    "max_impact": "high",
    "affected_entities_count": 8
  },
  "engines": [
    {
      "engine_id": "readiness",
      "include": true,
      "reason": "Matched 2 files, 4 entities",
      "priority": 1,
      "impact_level": "high"
    }
  ],
  "invariants": [
    {
      "rule_id": "api_contract_compliance",
      "include": true,
      "reason": "API changes detected",
      "impact_level": "high"
    }
  ],
  "exclusions": [
    {
      "type": "engine",
      "id": "ui_geometry",
      "reason": "No matching patterns"
    }
  ]
}
```

## Impact Levels

Files are classified by impact level based on patterns:

| Level | Patterns | Examples |
|-------|----------|----------|
| **Critical** | security, auth, crypto, secrets | `security/auth.py`, `.env` |
| **High** | api, model, schema, engine, core | `api/routes.py`, `models/user.py` |
| **Medium** | adapter, test, util | `adapters/http.py`, `test_api.py` |
| **Low** | docs, config, markdown | `README.md`, `config.yaml` |

## Entity Extraction

The engine extracts entities from diffs:

- **file_path**: All changed files
- **route**: API route decorators
- **component**: Classes and functions
- **dependency**: Import statements
- **api_endpoint**: Endpoint definitions

## Integration

Run plans integrate with `truthctl judge`:

```python
# judge command automatically:
# 1. Generates run plan from --diff/--changed-files
# 2. Writes plan to --plan-out or results dir
# 3. Executes only selected engines/invariants
# 4. Links run_manifest to run_plan
```

## API Usage

```python
from truthcore.impact import ChangeImpactEngine

engine = ChangeImpactEngine()

# From diff text
plan = engine.analyze(
    diff_text=diff_content,
    profile="api",
    source="feature-branch"
)

# From file list
plan = engine.analyze(
    changed_files=["src/main.py", "tests/test.py"],
    profile="default"
)

# Access decisions
for engine_decision in plan.engines:
    if engine_decision.include:
        print(f"Run: {engine_decision.engine_id}")
        print(f"  Reason: {engine_decision.reason}")

# Write plan
plan.write(Path("run_plan.json"))
```

## Determinism

Run plans are deterministic:
- Stable sorting of all collections
- Canonical JSON output
- Content-addressed cache keys (blake2b)
- No timestamps in cache key computation

## Examples

See `examples/run_plan/` for example files:
- `sample.diff` - Sample git diff
- `changed_files.txt` - Changed files list
- `run_plan_example.json` - Generated run plan
