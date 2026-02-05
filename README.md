# Truth Core

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Version](https://img.shields.io/badge/version-0.2.0-blue.svg)](https://github.com/your-org/truth-core)

> Deterministic, evidence-based verification framework for software systems.

Truth Core provides a verification platform featuring content-addressed caching, parallel execution, and comprehensive anomaly detection. All operations run without non-deterministic external dependencies.

## Features

- **Deterministic Outputs** - Same inputs always produce same outputs
- **Content-Addressed Cache** - Reuse previous results for identical inputs
- **Parallel Execution** - Multi-engine commands run in parallel
- **Security Hardening** - Protection against resource exhaustion and injection
- **Run Manifests** - Full provenance tracking with content hashes
- **Static Dashboard** - Offline-capable HTML dashboard for results
- **Anomaly Detection** - Deterministic scoring for historical analysis
- **UI Geometry Checks** - Verify actual clickability of UI elements
- **Parquet History** - High-performance optional storage
- **HTTP Server** - REST API and web GUI for remote access
- **Replay/Simulation** - Re-run and simulate changes for analysis

## Quick Start (60 seconds)

```bash
# Install
pip install truth-core

# Run verification
truthctl judge --inputs ./src --profile ui --out ./results

# View with dashboard
truthctl dashboard demo --out ./demo

# Open demo_out/dashboard/index.html in your browser
```

## Installation

```bash
# Basic installation
pip install truth-core

# With development dependencies
pip install truth-core[dev]

# With Parquet support for history storage
pip install truth-core[parquet]

# All features
pip install truth-core[dev,parquet]
```

## Integrate in 3 Minutes

## Integrate in 3 Minutes

### 1. GitHub Actions (10 lines of YAML)

```yaml
- name: Truth Core Verification
  uses: your-org/truth-core/integrations/github-actions@main
  with:
    profile: readylayer        # Options: readylayer, settler, aias, keys
    inputs-path: ./src
    output-path: verdict.json

- name: Check Results
  run: |
    if [ "${{ steps.truthcore.outputs.verdict }}" = "FAIL" ]; then
      exit 1
    fi
```

**Profiles:**
- `readylayer` - PR/CI quality gates (threshold configurable)
- `settler` - Release readiness (threshold configurable)
- `aias` - AI agent trace validation (threshold configurable)
- `keys` - Security credential verification (threshold configurable)

### 2. TypeScript SDK

```bash
npm install @truth-core/contract-sdk
```

```typescript
import { loadVerdict, topFindings, filterBySeverity } from "@truth-core/contract-sdk";

// Load and validate
const verdict = loadVerdict(await fetch("/api/verdict").then(r => r.json()));

// Analyze
const blockers = filterBySeverity(verdict, "BLOCKER");
const topIssues = topFindings(verdict, 5);

console.log(`${verdict.verdict}: ${verdict.value}/100 with ${blockers.length} blockers`);
```

### 3. Local CLI

```bash
# Run verification
truthctl judge --inputs ./src --profile ui --out ./results

# Check output
cat ./results/verdict.json | jq '.verdict'

# View in dashboard
truthctl dashboard serve --runs ./results --port 8787
```

## Dashboard

Truth Core includes a professional static dashboard for viewing results:

![Dashboard Preview](docs/assets/dashboard-preview.png)

### Dashboard Features

- **Fully Offline** - No external CDN dependencies
- **GitHub Pages Ready** - Build once, host anywhere
- **Interactive Charts** - SVG charts generated locally
- **Dark/Light Theme** - Automatic and manual switching
- **Accessibility** - Keyboard navigation, screen reader friendly

### Using the Dashboard

Truth Core artifacts remain with your organization. The dashboard is designed to integrate into existing operating models and internal controls.

```bash
# Build with embedded runs
truthctl dashboard build --runs ./my-runs --out ./dashboard-dist

# Serve locally
truthctl dashboard serve --runs ./my-runs --port 8787

# Create portable snapshot
truthctl dashboard snapshot --runs ./my-runs --out ./snapshot

# Run demo
truthctl dashboard demo --out ./demo-out
```

## Commands

### Core Commands

- `truthctl judge` - Run readiness engine with invariants
- `truthctl recon` - Reconcile financial transactions
- `truthctl trace` - Analyze agent execution traces
- `truthctl index` - Index knowledge base
- `truthctl intel` - Run intelligence analysis

### Dashboard Commands

- `truthctl dashboard build` - Build static dashboard
- `truthctl dashboard serve` - Serve dashboard locally
- `truthctl dashboard snapshot` - Create portable snapshot
- `truthctl dashboard demo` - Run demo with sample data

### Cache Management

- `truthctl cache-stats` - Show cache statistics
- `truthctl cache-compact` - Remove old entries
- `truthctl cache-clear` - Clear all cache entries

### Server Mode

- `truthctl serve` - Start HTTP server with REST API and web GUI
- `truthctl serve --port 8080` - Start on custom port
- `truthctl serve --reload` - Development mode with auto-reload

### Invariant Tools

- `truthctl explain` - Explain invariant rule evaluation

## Key Concepts

### Evidence
Immutable, signed artifacts produced by verification runs. Each piece of evidence includes content hashes for integrity verification. Evidence remains under your organization's custody.

### Invariants
Declarative rules that define "must always be true" conditions for your system. Invariants are checked automatically during verification. All rule evaluations are auditable.

### Policy
Policy-as-code for security, privacy, and compliance checks. Define rules in YAML and run them against any codebase. Policies integrate with your existing approval structures.

### Provenance
Full chain of custody for all evidence. Know exactly when, how, and by whom each artifact was created. All provenance data is preserved in local artifacts.

### Verdict
The final decision: PASS, FAIL, or CONDITIONAL. Includes a score (0-100) and detailed findings.

### Replay/Simulation
Re-run past verifications with the same inputs, or simulate "what-if" scenarios by adjusting thresholds and rules. All simulation results are clearly labeled as projections and require human review.

### Contracts
Versioned schemas for all artifacts ensure backward compatibility. Migrate between versions automatically.

## Output Artifacts

Each command produces:

- `run_manifest.json` - Full provenance with content hashes
- `verdict.json` - Machine-readable verdict
- `verdict.md` - Human-readable report
- `*.csv` - Tabular data (where applicable)

All artifacts remain under your organization's control. No artifacts are transmitted to external services.

### Cache Directory Structure

```
.truthcache/
├── index.json           # Cache index
├── <hash>/              # Cached outputs
│   ├── readiness.json
│   └── run_manifest.json
```

## Security

Truth Core implements defense in depth with the following controls:

- **Path Traversal Protection** - All paths validated before access
- **Resource Limits** - Configurable limits on file size, JSON depth
- **Output Sanitization** - Markdown outputs sanitized to prevent injection
- **Safe Archive Extraction** - Zip extraction with traversal checks
- **Evidence Signing** - Ed25519 signatures for tamper detection

All verification workflows include human-in-the-loop review points. Least privilege access is enforced through configurable permission boundaries.

See [SECURITY.md](SECURITY.md) for vulnerability reporting.

## Determinism

All operations are designed to be deterministic:

- Stable sorting of all collections
- Normalized UTC timestamps
- Canonical JSON serialization
- Content-addressed hashing (blake2b, sha256, sha3)
- No random sampling or probabilistic methods

Outputs are reproducible for verification and audit purposes.

## Documentation

- [Contributing Guide](CONTRIBUTING.md) - Development guidelines
- [Code of Conduct](CODE_OF_CONDUCT.md) - Community standards
- [Security Policy](SECURITY.md) - Security information
- [Governance](GOVERNANCE.md) - Project governance
- [Upgrade Notes](UPGRADE_NOTES.md) - Version upgrade guide
- [Changelog](CHANGELOG.md) - Version history

## Development

```bash
# Setup
pip install -e '.[dev,parquet]'

# Run tests
pytest -q

# Run linting
ruff check .
ruff format .

# Type checking
pyright src/truthcore

# Build package
python -m build

# Dashboard development
cd dashboard
npm install
npm run dev
```

## License

MIT License - see [LICENSE](LICENSE) for details.

---

**Version:** 0.2.0  
**Python:** 3.11+
