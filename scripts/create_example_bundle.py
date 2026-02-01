#!/usr/bin/env python3
"""Create example replay bundle fixture.

This script creates an example replay bundle for testing and demonstration.
Run with: python scripts/create_example_bundle.py
"""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from truthcore.manifest import RunManifest, normalize_timestamp
from truthcore.replay import BundleExporter


def create_example_bundle():
    """Create an example replay bundle."""
    examples_dir = Path(__file__).parent.parent / "examples" / "replay_bundle"
    run_dir = examples_dir / "run_output"
    inputs_dir = examples_dir / "inputs"
    bundle_dir = examples_dir / "bundle"

    # Clean and recreate directories
    for d in [examples_dir, run_dir, inputs_dir, bundle_dir]:
        if d.exists():
            import shutil
            shutil.rmtree(d)
        d.mkdir(parents=True, exist_ok=True)

    # Create run directory structure
    (run_dir / "subfolder").mkdir(parents=True, exist_ok=True)

    # Create mock findings
    findings = {
        "version": "0.2.0",
        "profile": "ui",
        "timestamp": normalize_timestamp(),
        "passed": False,
        "findings": [
            {
                "id": "UI_001",
                "severity": "HIGH",
                "category": "ui",
                "message": "Button not clickable at coordinates (100, 200)",
                "location": "src/components/Button.tsx:45",
                "rule_id": "UI_CLICKABLE",
                "tool": "ui_geometry",
            },
            {
                "id": "BUILD_001",
                "severity": "MEDIUM",
                "category": "build",
                "message": "TypeScript compilation warning",
                "location": "src/utils/helpers.ts:23",
                "rule_id": "TS_WARN",
                "tool": "build",
            },
            {
                "id": "SEC_001",
                "severity": "LOW",
                "category": "security",
                "message": "Missing security header",
                "location": "nginx.conf:12",
                "rule_id": "SEC_HEADERS",
                "tool": "security",
            },
        ],
    }

    # Create mock verdict
    verdict = {
        "verdict": "NO_SHIP",
        "version": "2.0",
        "timestamp": normalize_timestamp(),
        "mode": "pr",
        "profile": "ui",
        "summary": {
            "total_findings": 3,
            "blockers": 0,
            "highs": 1,
            "mediums": 1,
            "lows": 1,
            "total_points": 60,
        },
        "inputs": [str(inputs_dir)],
        "engines": [
            {
                "engine_id": "ui_geometry",
                "findings_count": 1,
                "blockers": 0,
                "highs": 1,
                "mediums": 0,
                "lows": 0,
                "points_contributed": 50,
                "passed": False,
            },
            {
                "engine_id": "build",
                "findings_count": 1,
                "blockers": 0,
                "highs": 0,
                "mediums": 1,
                "lows": 0,
                "points_contributed": 10,
                "passed": True,
            },
            {
                "engine_id": "security",
                "findings_count": 1,
                "blockers": 0,
                "highs": 0,
                "mediums": 0,
                "lows": 1,
                "points_contributed": 1,
                "passed": True,
            },
        ],
        "categories": [
            {
                "category": "ui",
                "weight": 1.0,
                "findings_count": 1,
                "points_contributed": 50,
                "max_allowed": None,
            },
            {
                "category": "build",
                "weight": 1.5,
                "findings_count": 1,
                "points_contributed": 10,
                "max_allowed": 50,
            },
            {
                "category": "security",
                "weight": 2.0,
                "findings_count": 1,
                "points_contributed": 1,
                "max_allowed": 100,
            },
        ],
        "top_findings": [
            {
                "finding_id": "UI_001",
                "tool": "ui_geometry",
                "severity": "HIGH",
                "category": "ui",
                "message": "Button not clickable at coordinates (100, 200)",
                "location": "src/components/Button.tsx:45",
                "rule_id": "UI_CLICKABLE",
                "weight": 50.0,
                "points": 50,
                "source_file": None,
                "source_engine": "ui_geometry",
            },
        ],
        "reasoning": {
            "ship_reasons": [],
            "no_ship_reasons": [
                "1 high severity issue(s) found (max allowed: 0)",
                "Total points (60) exceed threshold (100)",
            ],
        },
        "thresholds": {
            "mode": "pr",
            "max_blockers": 0,
            "max_highs": 0,
            "max_highs_with_override": 3,
            "max_total_points": 100,
            "category_limits": {"security": 100, "build": 50},
            "severity_weights": {
                "BLOCKER": float("inf"),
                "HIGH": 50.0,
                "MEDIUM": 10.0,
                "LOW": 1.0,
                "INFO": 0.0,
            },
            "category_weights": {
                "ui": 1.0,
                "build": 1.5,
                "security": 2.0,
            },
        },
    }

    # Write output files
    with open(run_dir / "readiness.json", "w") as f:
        json.dump(findings, f, indent=2, sort_keys=True)

    with open(run_dir / "verdict.json", "w") as f:
        json.dump(verdict, f, indent=2, sort_keys=True)

    with open(run_dir / "verdict.md", "w") as f:
        f.write("""# Verdict Report

**Verdict:** NO_SHIP
**Mode:** pr
**Profile:** ui

## Summary

- **Total Findings:** 3
- **Blockers:** 0
- **High Severity:** 1
- **Medium Severity:** 1
- **Low Severity:** 1
- **Total Points:** 60

## Top Findings

1. **HIGH** Button not clickable at coordinates (100, 200)
   - Location: `src/components/Button.tsx:45`
   - Rule: `UI_CLICKABLE`
   - Points: 50 (weight: 50.0)

## No-Ship Reasons

- 1 high severity issue(s) found (max allowed: 0)
- Total points (60) exceed threshold (100)
""")

    # Create input files
    with open(inputs_dir / "ui_facts.json", "w") as f:
        json.dump({
            "elements": [
                {
                    "id": "button1",
                    "type": "button",
                    "bounds": {"x": 100, "y": 200, "width": 80, "height": 40},
                    "clickable": False,
                }
            ]
        }, f, indent=2)

    with open(inputs_dir / "build_report.json", "w") as f:
        json.dump({
            "errors": 0,
            "warnings": 1,
            "duration_ms": 5000,
        }, f, indent=2)

    # Create run manifest
    manifest = RunManifest.create(
        command="judge",
        config={"profile": "ui", "mode": "pr"},
        input_dir=inputs_dir,
        profile="ui",
    )
    manifest.duration_ms = 1500
    manifest.write(run_dir)

    # Export bundle
    exporter = BundleExporter()
    bundle = exporter.export(
        run_dir=run_dir,
        original_inputs_dir=inputs_dir,
        out_bundle_dir=bundle_dir,
        profile="ui",
        mode="pr",
    )

    print(f"Example bundle created at: {bundle_dir}")
    print("\nBundle contents:")
    print(f"  - Run ID: {bundle.manifest.run_id}")
    print(f"  - Inputs: {len(bundle.get_input_files())} files")
    print(f"  - Outputs: {len(bundle.get_output_files())} files")

    # Create example changes file
    changes_file = examples_dir / "changes_example.yaml"
    with open(changes_file, "w") as f:
        f.write("""# Example changes for simulation
# This file demonstrates how to configure counterfactual changes

# Override thresholds
thresholds:
  max_highs: 5              # Allow up to 5 high severity issues
  max_total_points: 200     # Increase total points threshold
  max_highs_with_override: 10

# Override severity weights
severity_weights:
  HIGH: 25.0               # Reduce HIGH weight from 50.0
  MEDIUM: 5.0              # Reduce MEDIUM weight from 10.0

# Override category weights
category_weights:
  ui: 0.5                  # Reduce UI weight
  security: 3.0            # Increase security weight
  build: 1.0               # Reduce build weight

# Disable specific engines
disabled_engines:
  - "ui_geometry"

# Disable specific rules
disabled_rules:
  - "UI_CLICKABLE"

# Suppress specific findings
suppressions:
  - rule_id: "UI_001"
    reason: "Known issue, will be fixed in next sprint"
    expiry: "2026-02-15T00:00:00Z"
""")

    print(f"\nExample changes file: {changes_file}")

    # Create README
    readme = examples_dir / "README.md"
    with open(readme, "w") as f:
        f.write("""# Replay Bundle Example

This directory contains an example replay bundle for demonstration and testing.

## Structure

```
examples/replay_bundle/
├── run_output/           # Original run outputs
│   ├── run_manifest.json
│   ├── readiness.json
│   ├── verdict.json
│   └── verdict.md
├── inputs/               # Original inputs
│   ├── ui_facts.json
│   └── build_report.json
├── bundle/               # Exported replay bundle
│   ├── run_manifest.json
│   ├── inputs/
│   ├── outputs/
│   └── bundle_meta.json
└── changes_example.yaml  # Example simulation changes
```

## Usage

### Replay the bundle

```bash
truthctl replay --bundle ./bundle --out ./replay-results
```

### Run simulation

```bash
truthctl simulate --bundle ./bundle --out ./sim-results --changes ./changes_example.yaml
```

### Export a new bundle

```bash
truthctl bundle export --run-dir ./run_output --inputs ./inputs --out ./new-bundle
```

## Expected Results

The example bundle represents a UI analysis that found:
- 1 HIGH severity issue (button not clickable)
- 1 MEDIUM severity issue (TypeScript warning)
- 1 LOW severity issue (missing security header)

Total: 60 points (exceeds threshold of 100 in strict mode, but within PR limits)

With the example changes:
- UI weight reduced to 0.5
- UI geometry engine disabled
- UI_001 finding suppressed

The simulated verdict should show improved results.
""")

    print(f"README: {readme}")
    print("\nExample bundle fixture created successfully!")
    print("\nNext steps:")
    print(f"  1. Replay: truthctl replay --bundle {bundle_dir} --out /tmp/replay")
    print(
        f"  2. Simulate: truthctl simulate --bundle {bundle_dir} --out /tmp/sim "
        f"--changes {changes_file}"
    )


if __name__ == "__main__":
    create_example_bundle()
