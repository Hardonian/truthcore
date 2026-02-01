# Verdict Model (M6)

Multi-engine weighted ship/no-ship decision system.

## Overview

The Verdict Aggregator v2 combines findings from multiple engines (readiness, invariants, policy, provenance, intel) into a single ship/no-ship verdict. It uses weighted scoring based on severity, category, and execution mode.

## Quick Start

```python
from truthcore.verdict import aggregate_verdict
from pathlib import Path

result = aggregate_verdict(
    [Path("readiness.json"), Path("policy_findings.json")],
    mode="main",
    profile="ui"
)

print(result.verdict.value)  # 'SHIP' or 'NO_SHIP'
result.write_json(Path("./verdict.json"))
result.write_markdown(Path("./verdict.md"))
```

## CLI Usage

```bash
# Build verdict from engine outputs
truthctl verdict build \
  --inputs ./test-outputs \
  --profile ui \
  --mode main \
  --out ./results

# With custom thresholds
truthctl verdict build \
  --inputs ./test-outputs \
  --mode release \
  --thresholds ./custom-thresholds.json \
  --out ./results
```

## Execution Modes

Different modes have different thresholds:

| Mode | Blockers | Highs | Max Points | Description |
|------|----------|-------|------------|-------------|
| `pr` | 0 | 5 | 150 | Lenient, allows issues |
| `main` | 0 | 2 | 75 | Balanced |
| `release` | 0 | 0 | 20 | Strict, minimal issues |

Blockers always cause immediate NO_SHIP regardless of mode.

## Scoring System

### Severity Weights

| Severity | Base Points | Weight |
|----------|-------------|--------|
| BLOCKER | 1000 | ∞ (always fail) |
| HIGH | 50 | 1.0-2.0 |
| MEDIUM | 10 | 1.0-2.0 |
| LOW | 1 | 1.0-2.0 |
| INFO | 0 | 0 |

### Category Multipliers

| Category | Multiplier |
|----------|------------|
| security | 2.0x |
| privacy | 2.0x |
| finance | 1.5x |
| build | 1.5x |
| types | 1.2x |
| ui | 1.0x |
| agent | 1.0x |
| knowledge | 1.0x |

### Points Calculation

```
points = base_severity_points * category_multiplier
```

Example: A HIGH severity security finding = 50 * 2.0 = 100 points

## Input Formats

The aggregator accepts findings from:

### readiness.json
```json
{
  "findings": [
    {
      "id": "error-1",
      "severity": "HIGH",
      "category": "ui",
      "message": "Button not clickable",
      "location": "src/page.tsx:42"
    }
  ]
}
```

### invariants.json
```json
{
  "violations": [
    {
      "rule_id": "no_console_log",
      "severity": "MEDIUM",
      "message": "console.log found in production code",
      "file": "src/app.ts"
    }
  ]
}
```

### policy_findings.json
```json
{
  "policy_findings": [
    {
      "id": "SECRET_DETECTED",
      "severity": "BLOCKER",
      "category": "security",
      "message": "API key detected in code"
    }
  ]
}
```

### Provenance Results
Automatically parsed for tampered files (marked as BLOCKER).

## Output Format

### verdict.json

```json
{
  "verdict": "NO_SHIP",
  "version": "2.0",
  "timestamp": "2026-01-31T12:00:00Z",
  "mode": "main",
  "profile": "ui",
  "summary": {
    "total_findings": 15,
    "blockers": 1,
    "highs": 3,
    "mediums": 8,
    "lows": 3,
    "total_points": 267
  },
  "inputs": ["readiness.json", "policy_findings.json"],
  "engines": [
    {
      "engine_id": "readiness",
      "findings_count": 10,
      "blockers": 0,
      "highs": 2,
      "points_contributed": 120,
      "passed": false
    }
  ],
  "categories": [
    {
      "category": "security",
      "weight": 2.0,
      "findings_count": 3,
      "points_contributed": 150,
      "max_allowed": 50
    }
  ],
  "top_findings": [...],
  "reasoning": {
    "ship_reasons": ["No blocker issues found"],
    "no_ship_reasons": [
      "1 blocker(s) found (max allowed: 0)",
      "Total points (267) exceed threshold (75)"
    ]
  }
}
```

### verdict.md

Human-readable report with:
- Verdict summary
- Engine contribution table
- Category breakdown
- Top 10 findings
- Ship/no-ship reasoning
- Visual SVG chart (if findings exist)

## Custom Thresholds

Create custom thresholds via JSON:

```json
{
  "max_blockers": 0,
  "max_highs": 3,
  "max_total_points": 100,
  "category_limits": {
    "security": 50,
    "build": 25
  },
  "category_weights": {
    "security": 3.0,
    "performance": 1.5
  }
}
```

Load via CLI:
```bash
truthctl verdict build --thresholds ./custom-thresholds.json ...
```

## Programmatic API

### Basic Aggregation

```python
from truthcore.verdict import aggregate_verdict
from pathlib import Path

result = aggregate_verdict(
    input_paths=[Path("readiness.json")],
    mode="main",
    profile="ui"
)
```

### Manual Aggregation

```python
from truthcore.verdict import VerdictAggregator, VerdictThresholds, Mode

# Configure thresholds
thresholds = VerdictThresholds.for_mode(Mode.MAIN)
thresholds.max_highs = 5
thresholds.category_limits["security"] = 100

# Create aggregator
aggregator = VerdictAggregator(thresholds)

# Add findings
aggregator.add_finding(
    finding_id="error-1",
    tool="eslint",
    severity="HIGH",
    category="build",
    message="Type error detected",
)

# Add from JSON file
aggregator.add_findings_from_file(Path("readiness.json"))

# Aggregate
result = aggregator.aggregate(mode=Mode.MAIN, profile="ui")
```

### Reading Results

```python
# Check verdict
if result.verdict.value == "SHIP":
    print("✅ Ready to ship!")
else:
    print("❌ Issues found:")
    for reason in result.no_ship_reasons:
        print(f"  - {reason}")

# Access breakdown
for engine in result.engines:
    print(f"{engine.engine_id}: {engine.findings_count} findings")

# Top findings
for finding in result.top_findings[:5]:
    print(f"[{finding.severity.value}] {finding.message}")
```

## Integration with judge

The verdict is automatically generated by `truthctl judge`:

```bash
truthctl judge --inputs ./test-outputs --profile ui --out ./results
# Produces: results/verdict.json, results/verdict.md
```

## Threshold Reference

### Default Thresholds by Mode

**PR Mode:**
- Blockers: 0
- Highs: 5 (override up to 10)
- Total points: 150
- Category limits: security=100, build=50

**Main Mode:**
- Blockers: 0  
- Highs: 2 (override up to 5)
- Total points: 75
- Category limits: security=50, build=25, types=30

**Release Mode:**
- Blockers: 0
- Highs: 0 (override up to 1)
- Total points: 20
- Category limits: security=0, privacy=0, build=10, types=10

## Decision Logic

1. **Blockers** → Immediate NO_SHIP
2. **Highs > max_highs** → NO_SHIP (or CONDITIONAL if within override)
3. **Total points > max_points** → NO_SHIP
4. **Category exceeds limit** → NO_SHIP
5. **Otherwise** → SHIP

## API Reference

### Models

- `VerdictResult` - Complete verdict with all metadata
- `VerdictThresholds` - Threshold configuration
- `WeightedFinding` - Finding with computed weight/points
- `EngineContribution` - Per-engine summary
- `CategoryBreakdown` - Per-category summary

### Enums

- `VerdictStatus` - SHIP, NO_SHIP, CONDITIONAL
- `SeverityLevel` - BLOCKER, HIGH, MEDIUM, LOW, INFO
- `Category` - ui, build, types, security, privacy, finance, agent, knowledge
- `Mode` - pr, main, release

### Functions

- `aggregate_verdict(input_paths, mode, profile)` - Convenience function
- `register_verdict_commands(cli)` - Add to CLI
- `generate_verdict_for_judge(...)` - Judge integration
