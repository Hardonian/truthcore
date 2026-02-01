# Replay and Simulation

Truth Core provides deterministic replay and counterfactual simulation capabilities for verifying reproducibility and exploring "what-if" scenarios.

## Overview

- **Replay**: Re-run a previous verdict using stored inputs and configuration, verifying that outputs are identical (modulo allowed non-content fields like timestamps).
- **Simulation**: Run counterfactual scenarios by modifying thresholds, weights, or rules without changing raw inputs.

## Replay Bundle Format

A replay bundle captures all artifacts needed for deterministic replay:

```
bundle/
├── run_manifest.json          # Original run manifest
├── inputs/                    # Raw inputs used
│   ├── test-data.json
│   └── ui_facts.json
├── config/                    # Configuration files
│   ├── thresholds.json
│   └── profile_ui.yaml
├── outputs/                   # Previous outputs
│   ├── readiness.json
│   ├── verdict.json
│   └── verdict.md
├── evidence.manifest.json     # Provenance manifest (optional)
└── evidence.sig               # Signature (optional)
```

## Commands

### `truthctl bundle export`

Export a run into a replay bundle.

```bash
# Export a run directory
truthctl bundle export --run-dir ./results --out ./my-bundle

# Export with separate inputs directory
truthctl bundle export \
  --run-dir ./results \
  --inputs ./test-data \
  --out ./my-bundle \
  --profile ui \
  --mode pr
```

Options:
- `--run-dir, -r`: Directory containing run outputs (required)
- `--inputs, -i`: Original inputs directory (if separate)
- `--out, -o`: Output directory for the bundle (required)
- `--profile, -p`: Profile used for the run
- `--mode, -m`: Mode used for the run (pr/main/release)

### `truthctl replay`

Replay a bundle and verify deterministic behavior.

```bash
# Basic replay
truthctl replay --bundle ./my-bundle --out ./replay-results

# Strict mode (fail on any differences)
truthctl replay --bundle ./my-bundle --out ./replay-results --strict

# Override mode/profile
truthctl replay --bundle ./my-bundle --out ./replay-results --mode main

# Skip verification
truthctl replay --bundle ./my-bundle --out ./replay-results --no-verify
```

Options:
- `--bundle, -b`: Path to replay bundle directory (required)
- `--out, -o`: Output directory for replay results (required)
- `--mode, -m`: Override mode (uses bundle mode if not specified)
- `--profile, -p`: Override profile (uses bundle profile if not specified)
- `--strict`: Fail if any differences found (even in allowed fields)
- `--verify/--no-verify`: Verify bundle integrity before replay (default: verify)
- `--force`: Proceed even if bundle verification fails

The replay produces:
- `replay_report.json`: Machine-readable comparison results
- `replay_report.md`: Human-readable report

### `truthctl simulate`

Run counterfactual simulation with modified configuration.

```bash
# Basic simulation
truthctl simulate --bundle ./my-bundle --out ./sim-results --changes ./changes.yaml

# Override mode
truthctl simulate --bundle ./my-bundle --out ./sim-results --changes ./changes.yaml --mode main
```

Options:
- `--bundle, -b`: Path to replay bundle directory (required)
- `--out, -o`: Output directory for simulation results (required)
- `--changes, -c`: YAML file with changes to apply (required)
- `--mode, -m`: Override mode
- `--profile, -p`: Override profile
- `--verify/--no-verify`: Verify bundle integrity (default: verify)
- `--force`: Proceed even if bundle verification fails

The simulation produces:
- `simulation_report.json`: Machine-readable results
- `simulation_report.md`: Human-readable report
- `simulation_diff.json`: Detailed diff between original and simulated
- `verdict.json`: The new verdict with changes applied
- `verdict.md`: Human-readable new verdict

## Changes YAML Format

The changes file for simulation supports:

```yaml
# Override thresholds
thresholds:
  max_highs: 10
  max_total_points: 200
  max_highs_with_override: 15

# Override severity weights
severity_weights:
  HIGH: 75.0
  MEDIUM: 15.0

# Override category weights
category_weights:
  security: 3.0
  build: 2.0
  ui: 0.5

# Set category point limits
category_limits:
  security: 150
  build: 50

# Disable specific engines
disabled_engines:
  - "ui_geometry"
  - "accessibility"

# Disable specific rules
disabled_rules:
  - "UI_001"
  - "UI_002"

# Suppress specific findings
suppressions:
  - rule_id: "UI_001"
    reason: "Known issue, fix in progress"
    expiry: "2026-02-01T00:00:00Z"
  - rule_id: "BUILD_003"
    reason: "False positive"
```

## Deterministic Diff

The replay system uses content-aware diffing that:

1. **Ignores allowed fields**: Timestamps, run IDs, cache keys, etc.
2. **Normalizes values**: ISO timestamps are compared semantically
3. **Sorts collections**: Arrays are sorted by ID/path for stable comparison
4. **Computes content hashes**: Deterministic hashes excluding allowed fields

### Allowlist

By default, these fields are allowed to differ:

- `run_id`: Unique run identifier
- `timestamp`: Execution timestamp
- `duration_ms`: Execution duration
- `cache_key`: Cache key
- `cache_path`: Cache storage path
- `cache_hit`: Cache hit flag

Use `--strict` mode to require even these fields to match.

## Examples

### Example 1: Verify Determinism

```bash
# Run initial analysis
truthctl judge --inputs ./test-data --profile ui --out ./results

# Export to bundle
truthctl bundle export --run-dir ./results --out ./replay-bundle

# Replay and verify identical results
truthctl replay --bundle ./replay-bundle --out ./replay-results --strict
# Should exit 0 if deterministic
```

### Example 2: Test Threshold Changes

```bash
# Create changes file
cat > /tmp/lenient.yaml << 'EOF'
thresholds:
  max_highs: 20
  max_total_points: 300
EOF

# Run simulation
truthctl simulate \
  --bundle ./replay-bundle \
  --out ./sim-lenient \
  --changes /tmp/lenient.yaml

# Check if verdict changed
cat ./sim-lenient/simulation_report.json | jq '.verdict_changed'
```

### Example 3: Disable Problematic Engine

```bash
# Create changes file
cat > /tmp/disable-ui.yaml << 'EOF'
disabled_engines:
  - "ui_geometry"
suppressions:
  - rule_id: "UI_001"
    reason: "Blocking release, will fix in follow-up"
EOF

# Run simulation
truthctl simulate \
  --bundle ./replay-bundle \
  --out ./sim-no-ui \
  --changes /tmp/disable-ui.yaml \
  --mode release

# Compare verdicts
diff ./replay-bundle/outputs/verdict.md ./sim-no-ui/verdict.md
```

### Example 4: CI Integration

```yaml
# .github/workflows/verify.yml
- name: Verify Determinism
  run: |
    # Run analysis
    truthctl judge --inputs ./test-data --out ./results
    
    # Export bundle
    truthctl bundle export --run-dir ./results --out ./bundle
    
    # Replay and verify
    truthctl replay --bundle ./bundle --out ./replay --strict
    
    # If we get here, outputs are deterministic
    echo "✅ Determinism verified"
```

## Security

### Bundle Verification

Replay and simulation commands verify bundle integrity before execution:

1. **Evidence manifest**: Recomputes file hashes and compares
2. **Signature**: Verifies cryptographic signature (if present)
3. **Path safety**: Validates all paths are within bundle directory

Use `--force` to proceed despite verification failures (use with caution).

### Provenance

Bundles created with `--sign` include cryptographic signatures:

```bash
# Sign during export (if keys configured)
truthctl bundle export --run-dir ./results --out ./bundle

# Verification will check signature
truthctl replay --bundle ./bundle --out ./replay
```

## Troubleshooting

### "Bundle verification failed"

Check if files were modified:
```bash
# Verify bundle separately
truthctl verify-bundle --bundle ./my-bundle
```

### "Differences found in replay"

Inspect the diff:
```bash
# View detailed report
cat ./replay-results/replay_report.md

# Check specific files
cat ./replay-results/replay_report.json | jq '.file_diffs[] | select(.identical == false)'
```

Common causes:
- Non-deterministic inputs (timestamps in test data)
- Random sampling or probabilistic methods
- External dependencies (network, filesystem ordering)
- Hash algorithm mismatches

### "Missing input files"

Ensure inputs are copied during export:
```bash
# Export with explicit inputs directory
truthctl bundle export --run-dir ./results --inputs ./original-inputs --out ./bundle
```

## API Usage

### Programmatic Replay

```python
from truthcore.replay import ReplayBundle, ReplayEngine, ReplayReporter

# Load bundle
bundle = ReplayBundle.load("./my-bundle")

# Verify integrity
result = bundle.verify_integrity()
if not result.valid:
    raise ValueError("Bundle verification failed")

# Run replay
engine = ReplayEngine(strict=True)
replay_result = engine.replay(
    bundle=bundle,
    output_dir=Path("./replay-results"),
)

# Generate reports
reporter = ReplayReporter()
paths = reporter.write_reports(replay_result, Path("./replay-results"))

print(f"Identical: {replay_result.identical}")
```

### Programmatic Simulation

```python
from truthcore.replay import (
    ReplayBundle,
    SimulationEngine,
    SimulationChanges,
    SimulationReporter,
)

# Load bundle
bundle = ReplayBundle.load("./my-bundle")

# Define changes
changes = SimulationChanges(
    thresholds={"max_highs": 10},
    disabled_engines=["ui_geometry"],
)

# Or load from YAML
changes = SimulationChanges.from_yaml(Path("./changes.yaml"))

# Run simulation
engine = SimulationEngine()
result = engine.simulate(
    bundle=bundle,
    output_dir=Path("./sim-results"),
    changes=changes,
)

# Generate reports
reporter = SimulationReporter()
paths = reporter.write_reports(result, Path("./sim-results"))

# Check if verdict changed
if result.original_verdict and result.simulated_verdict:
    if result.original_verdict.verdict != result.simulated_verdict.verdict:
        print(f"Verdict changed: {result.original_verdict.verdict.value} -> {result.simulated_verdict.verdict.value}")
```

## Best Practices

1. **Always verify bundles**: Use `--verify` (default) to catch tampering
2. **Export after important runs**: Create bundles for release candidates
3. **Use strict mode for CI**: `--strict` ensures complete determinism
4. **Document threshold changes**: Include rationale in changes YAML
5. **Version control bundles**: Store bundles as artifacts for audit trails
6. **Test simulations before applying**: Run simulation to preview impact
7. **Keep bundles immutable**: Never modify bundle contents directly

## See Also

- [Verdict Model](verdict_model.md) - Weighted verdict aggregation
- [Provenance](contracts.md) - Evidence signing and verification
- [Normalization](normalization.md) - Deterministic data handling
