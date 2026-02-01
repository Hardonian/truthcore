# Truth Core

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **Deterministic, evidence-based verification framework for software systems.**

Truth Core provides a cutting-edge platform for deterministic verification, featuring content-addressed caching, parallel execution, security hardening, and comprehensive anomaly detection—all without non-deterministic external dependencies.

## Features

- **Deterministic Outputs** - Same inputs always produce same outputs
- **Content-Addressed Cache** - Reuse previous results for identical inputs
- **Parallel Execution** - Multi-engine commands run in parallel
- **Security Hardening** - Protection against resource exhaustion and injection
- **Run Manifests** - Full provenance tracking with content hashes
- **Anomaly Detection** - Deterministic scoring for historical analysis
- **UI Geometry Checks** - Verify actual clickability of UI elements
- **Parquet History** - High-performance optional storage

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

## Quick Start

```bash
# Run readiness check
truthctl judge --inputs ./test-outputs --profile ui --out ./results

# Run with caching for faster subsequent runs
truthctl judge --inputs ./test-outputs --profile ui --out ./results --cache-dir .truthcache

# Explain an invariant rule
truthctl explain --rule no_errors --data ./results/readiness.json --rules ./rules.json

# Analyze historical data
truthctl intel --inputs ./history --mode readiness --out ./intel-results

# Compact old history
truthctl intel --compact --retention 90 --inputs ./history --out ./intel-results
```

## Commands

### Core Commands

- `truthctl judge` - Run readiness engine with invariants
- `truthctl recon` - Reconcile financial transactions
- `truthctl trace` - Analyze agent execution traces
- `truthctl index` - Index knowledge base
- `truthctl intel` - Run intelligence analysis

### Cache Management

- `truthctl cache-stats` - Show cache statistics
- `truthctl cache-compact` - Remove old entries
- `truthctl cache-clear` - Clear all cache entries

### Invariant Tools

- `truthctl explain` - Explain invariant rule evaluation

## CLI Options

### Global Options

```bash
--cache-dir PATH       # Cache directory (default: .truthcache)
--no-cache             # Disable caching
--cache-readonly       # Use cache but don't write new entries
```

### Command Options

```bash
# Judge command
truthctl judge --inputs PATH --profile NAME --out PATH [--parallel/--sequential]

# Intel command  
truthctl intel --inputs PATH --mode {readiness,recon,agent,knowledge} --out PATH [--compact] [--retention DAYS]

# Index command
truthctl index --inputs PATH --out PATH [--parquet]
```

## Output Artifacts

Each command produces:

- `run_manifest.json` - Full provenance with content hashes
- `*.json` - Machine-readable results
- `*.md` - Human-readable reports
- `*.csv` - Tabular data (where applicable)

### Cache Directory Structure

```
.truthcache/
├── index.json           # Cache index
├── <hash>/              # Cached outputs
│   ├── readiness.json
│   └── run_manifest.json
```

## Security

Truth Core implements defense in depth:

- **Path Traversal Protection** - All paths validated before access
- **Resource Limits** - Configurable limits on file size, JSON depth
- **Output Sanitization** - Markdown outputs sanitized to prevent injection
- **Safe Archive Extraction** - Zip extraction with traversal checks

## Determinism

All operations are deterministic:

- Stable sorting of all collections
- Normalized UTC timestamps
- Canonical JSON serialization
- Content-addressed hashing (blake2b, sha256, sha3)
- No random sampling or probabilistic methods

## Configuration

### Security Limits

```python
from truthcore.security import SecurityLimits

limits = SecurityLimits(
    max_file_size=100*1024*1024,      # 100 MB
    max_json_depth=100,
    max_json_size=50*1024*1024,       # 50 MB
)
```

### Invariant Rules

```yaml
rules:
  - id: no_critical_errors
    name: No Critical Errors
    severity: BLOCKER
    all:
      - left: errors.critical
        operator: "=="
        right: 0
      - left: errors.high
        operator: "<"
        right: 5
```

## API Usage

```python
from truthcore.manifest import RunManifest
from truthcore.cache import ContentAddressedCache
from truthcore.anomaly_scoring import ReadinessAnomalyScorer

# Create manifest
manifest = RunManifest.create(
    command="judge",
    config={"profile": "ui"},
    input_dir=Path("./inputs"),
)

# Use cache
cache = ContentAddressedCache(Path(".truthcache"))
cache_key = manifest.compute_cache_key()

if cached := cache.get(cache_key):
    print(f"Cache hit: {cached}")
else:
    # Run engine and cache results
    cache.put(cache_key, output_dir, manifest.to_dict())
```

## Documentation

- [Upgrade Notes](UPGRADE_NOTES.md) - Version upgrade guide
- [Evidence Contract](docs/evidence_contract.md) - Output specifications
- [Severity Model](docs/severity_model.md) - Issue classification
- [Consumer Integration](docs/consumer_integration.md) - Integration guide

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
```

## CI/CD Integration

```yaml
- name: Run truth-core
  run: |
    truthctl judge \
      --inputs ./test-outputs \
      --profile ui \
      --out ./truth-results \
      --cache-dir .truthcache
    
    # Check thresholds
    if [ $(jq -r '.passed' ./truth-results/readiness.json) = "false" ]; then
      echo "Quality thresholds not met"
      exit 1
    fi
```

## License

MIT License - see [LICENSE](LICENSE) for details.

---

**Version:** 0.2.0  
**Python:** 3.11+  
**Status:** Beta
