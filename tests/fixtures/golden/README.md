# Golden Fixture Regression Suite

This directory contains the Golden Fixture Regression Suite for truth-core - a collection of expected verdict outputs for known scenarios to ensure consistency and stability.

## Overview

Golden fixtures serve as the reference standard for truth-core verification outputs. They define the expected verdict structure, values, and findings for various real-world scenarios across different domains.

## Scenarios

### Code Quality

| Scenario | Verdict | Description |
|----------|---------|-------------|
| `clean_code` | PASS | High-quality codebase with good practices |
| `style_only` | PASS | Code with only formatting/style issues |
| `missing_tests` | FAIL | Codebase lacking proper test coverage |

### Security & Performance

| Scenario | Verdict | Description |
|----------|---------|-------------|
| `security_issues` | FAIL | Code with critical security vulnerabilities |
| `performance_regression` | WARN | Code with performance issues but no security blockers |

### AI Agent Traces

| Scenario | Verdict | Description |
|----------|---------|-------------|
| `agent_trace_success` | PASS | Valid AI agent trace with proper FSM compliance |
| `agent_trace_failure` | FAIL | AI agent trace with FSM violations and safety issues |

## Fixture Structure

Each scenario directory contains:

```
scenario_name/
├── expected_verdict.json    # The golden reference verdict
└── [inputs/]                # Optional: Input files that generated this verdict
```

## Expected Verdict Format

All expected verdicts follow the truth-core Verdict v2.0.0 contract:

```json
{
  "_contract": {
    "artifact_type": "verdict",
    "contract_version": "2.0.0",
    "truthcore_version": "0.2.0",
    "created_at": "2026-01-31T12:00:00Z",
    "schema": "schemas/verdict/v2.0.0/verdict.schema.json"
  },
  "verdict": "PASS|FAIL|WARN|UNKNOWN",
  "value": 0-100,
  "confidence": 0.0-1.0,
  "items": [
    {
      "id": "finding-id",
      "severity": "BLOCKER|HIGH|MEDIUM|LOW|INFO",
      "message": "Human-readable description",
      "category": "category-name",
      "engine": "engine-name",
      "confidence": 0.0-1.0
    }
  ],
  "metadata": {
    "scenario": "scenario-name",
    "description": "Scenario description"
  }
}
```

## Usage in Tests

The test harness (`tests/test_golden_fixtures.py`) validates:

1. **Structure Compliance**: All fixtures have valid contract fields
2. **Value Ranges**: Scores between 0-100, severities are valid
3. **Explainability**: Verdict states match findings appropriately
4. **Completeness**: All severity levels and verdict states covered
5. **Stability**: Expected outputs don't drift unexpectedly

Run the tests:

```bash
pytest tests/test_golden_fixtures.py -v
```

## Adding New Scenarios

1. Create a new directory under `tests/fixtures/golden/`
2. Add `expected_verdict.json` with the expected output
3. Optionally add input files to document what generated the verdict
4. Update `test_golden_fixtures.py` with the new scenario parameters
5. Run tests to ensure compliance

## Maintenance

- Golden fixtures should only change when truth-core behavior intentionally changes
- When updating, increment `truthcore_version` in `_contract`
- Document any changes in UPGRADE_NOTES.md
- Ensure backward compatibility when possible
