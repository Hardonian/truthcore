# Contract System Documentation

This document defines the contract system for truth-core artifacts, ensuring versioned, validated, and migratable outputs.

## Overview

Every canonical artifact produced by truth-core is explicitly versioned with contract metadata. This enables:
- **Consumer stability**: Repos can pin to specific contract versions
- **Deterministic migrations**: Old artifacts can be migrated forward reliably
- **Validation**: All outputs are validated against their declared schema
- **Compatibility**: Backward compatibility for at least 2 major versions

## Contract Metadata Structure

Every artifact includes a top-level `_contract` section:

```json
{
  "_contract": {
    "artifact_type": "verdict",
    "contract_version": "2.0.0",
    "truthcore_version": "0.7.0",
    "engine_versions": {
      "readiness": "1.2.0",
      "invariants": "2.1.0"
    },
    "created_at": "2026-01-31T00:00:00Z",
    "schema": "schemas/verdict/v2.0.0/verdict.schema.json"
  }
}
```

### Contract Fields

| Field | Type | Description |
|-------|------|-------------|
| `artifact_type` | string | The type of artifact (e.g., "verdict", "readiness", "invariants") |
| `contract_version` | string | Semantic version of this artifact's contract |
| `truthcore_version` | string | Version of truth-core that produced this artifact |
| `engine_versions` | object | Versions of engines used to produce this artifact |
| `created_at` | string | ISO 8601 UTC timestamp (normalized, no local time) |
| `schema` | string | Path or identifier for the schema this artifact conforms to |

**Determinism Requirements:**
- `created_at` must be normalized UTC (no timezone offsets)
- Contract metadata must not contain local paths or environment details
- Those belong in the run_manifest, not the artifact contract

## Artifact Types

The following artifact types are supported:

| Artifact Type | Description | Current Version |
|--------------|-------------|----------------|
| `verdict` | Aggregated judgment from multiple engines | 2.0.0 |
| `readiness` | Readiness check results | 1.0.0 |
| `invariants` | Invariant rule evaluations | 1.0.0 |
| `policy_findings` | Policy-as-code scan results | 1.0.0 |
| `provenance_manifest` | Signed provenance manifest | 1.0.0 |
| `agent_trace_report` | Agent trace analysis report | 1.0.0 |
| `reconciliation_table` | Reconciliation truth table | 1.0.0 |
| `knowledge_index` | Knowledge graph index | 1.0.0 |
| `intel_scorecard` | Intelligence analysis scorecard | 1.0.0 |

## Version Semantics (Semver)

Contract versions follow semantic versioning:

### PATCH (e.g., 1.0.0 → 1.0.1)
- **Backward compatible**: Yes
- **Changes**: Bug fixes, documentation updates
- **Field changes**: No required fields added or removed
- **Migration**: Automatic, no data transformation needed

### MINOR (e.g., 1.0.0 → 1.1.0)
- **Backward compatible**: Yes
- **Changes**: Optional fields added, new artifact types
- **Field changes**: Only optional fields added
- **Migration**: Automatic, old readers can ignore new fields

### MAJOR (e.g., 1.0.0 → 2.0.0)
- **Backward compatible**: No
- **Changes**: Breaking changes to required fields
- **Field changes**: Required fields removed/renamed, semantics changed
- **Migration**: Requires explicit migration function

## Compatibility Mode

truth-core supports "compat mode" for producing outputs in older contract versions:

```bash
# Produce verdict in version 1.0.0 format
truthctl judge --inputs ./data --compat 1.0.0

# Build verdict with specific contract version
truthctl verdict build --inputs ./data --compat 1.0.0
```

**Compat Mode Rules:**
- truth-core always computes using latest internal models
- Then renders outputs to requested compat version if specified
- If compat requested is impossible (breaking removal), fails with clear error
- Supports at least the last 2 MAJOR versions (configurable)

## Schema Registry

Schemas are organized by artifact type and version:

```
src/truthcore/schemas/
├── verdict/
│   ├── v1.0.0/
│   │   └── verdict.schema.json
│   └── v2.0.0/
│       └── verdict.schema.json
├── readiness/
│   └── v1.0.0/
│       └── readiness.schema.json
└── ...
```

### Schema Loading

Old paths are mapped to new versioned paths:
- Legacy path: `schemas/verdict.schema.json` → maps to latest version
- Versioned path: `schemas/verdict/v2.0.0/verdict.schema.json`

This is implemented in code (not OS symlinks) for cross-platform compatibility.

## Contract Validation

All artifacts can be validated against their declared schema:

```bash
# Validate a single artifact
truthctl contracts validate --file verdict.json --strict

# Validate all artifacts in a directory
truthctl contracts validate --inputs ./outputs/
```

Validation checks:
- Schema exists for declared version
- All required fields present
- Field types match schema
- No extra fields (in strict mode)

## CLI Commands

### List Contracts
```bash
truthctl contracts list
```
Shows all registered contract types and their available versions.

### Validate Contract
```bash
truthctl contracts validate --file <artifact.json> [--strict]
```
Validates an artifact against its declared schema version.

### Migrate Contract
```bash
truthctl contracts migrate --file <artifact.json> --to <version> --out <path>
```
Migrates an artifact from its current version to a target version.

### Compatibility Mode
```bash
truthctl contracts compat --inputs <dir> --target-version <ver> --out <dir>
```
Converts all artifacts in a directory to target versions where possible.

### Contract Diff
```bash
truthctl contracts diff --old <file> --new <file>
```
Analyzes differences between two contract versions.

## Consumer Integration

Consumer repos should:

1. **Pin to a contract version** in their CI configuration
2. **Validate truth-core outputs** before consumption
3. **Plan migrations** when truth-core announces contract changes

Example consumer workflow:
```yaml
# .github/workflows/truth-core.yml
- name: Run truth-core
  run: truthctl judge --inputs ./src --out ./truth-outputs
  
- name: Validate outputs
  run: truthctl contracts validate --inputs ./truth-outputs --strict
  
- name: Pin to contract version
  run: |
    CONTRACT_VERSION=$(jq -r '._contract.contract_version' ./truth-outputs/verdict.json)
    if [ "$CONTRACT_VERSION" != "2.0.0" ]; then
      echo "Unexpected contract version: $CONTRACT_VERSION"
      exit 1
    fi
```

## Best Practices

1. **Always validate outputs** before consuming them
2. **Pin to specific contract versions** in CI/CD pipelines
3. **Test migrations** before upgrading truth-core
4. **Monitor contract versions** in production outputs
5. **Use compat mode** during transition periods

## Error Handling

Common contract errors and solutions:

| Error | Cause | Solution |
|-------|-------|----------|
| `UnknownContractVersion` | Artifact references unknown version | Check version string format, upgrade truth-core |
| `SchemaValidationError` | Artifact doesn't match schema | Validate input data, check field types |
| `MigrationNotFound` | No migration path exists | Use intermediate migration steps |
| `BreakingChangeError` | Compat mode impossible | Upgrade consumer code, use latest version |

## See Also

- [Migrations Guide](./migrations.md) - Detailed migration procedures
- [Versioning Policy](./versioning_policy.md) - Version governance rules
- [Consumer Integration](./consumer_integration.md) - How to integrate as a consumer
