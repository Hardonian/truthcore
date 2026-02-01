# Migration Guide

This document describes how to migrate truth-core artifacts between contract versions.

## Overview

The migration system provides deterministic, validated transformations to move artifacts from one contract version to another. All migrations are:
- **Deterministic**: Same input always produces same output
- **Validated**: Output is validated against target schema
- **Reversible** (when possible): Some migrations can be reversed
- **Documented**: Each migration has a clear description of changes

## Migration Concepts

### Migration Chain

Migrations form a chain between versions:
```
v1.0.0 → v1.1.0 → v1.2.0 → v2.0.0 → v2.1.0
```

To migrate from v1.0.0 to v2.1.0:
1. Apply v1.0.0 → v1.1.0
2. Apply v1.1.0 → v1.2.0
3. Apply v1.2.0 → v2.0.0
4. Apply v2.0.0 → v2.1.0

### Migration Types

| Type | Direction | Use Case |
|------|-----------|----------|
| `upgrade` | Old → New | Consumer updating to latest |
| `downgrade` | New → Old | Compat mode, emergency rollback |
| `cross` | Any → Any | Direct migration when path exists |

### Migration Functions

Each migration is a pure function:
```python
def migrate_v1_to_v2(artifact: dict) -> dict:
    """
    Migrate artifact from v1.0.0 to v2.0.0.
    
    Changes:
    - Renames 'result' to 'verdict'
    - Adds 'confidence' field (required)
    - Removes deprecated 'legacy_notes' field
    """
    new_artifact = copy.deepcopy(artifact)
    new_artifact["verdict"] = new_artifact.pop("result")
    new_artifact["confidence"] = calculate_confidence(artifact)
    new_artifact.pop("legacy_notes", None)
    return new_artifact
```

## Using the Migration CLI

### Basic Migration

Migrate a single artifact:
```bash
truthctl contracts migrate \
  --file verdict.json \
  --to 2.0.0 \
  --out verdict_v2.json
```

### Batch Migration

Migrate all artifacts in a directory:
```bash
truthctl contracts compat \
  --inputs ./old_outputs/ \
  --target-version 2.0.0 \
  --out ./migrated_outputs/
```

### Validation During Migration

All migrations automatically validate:
1. Input artifact against source version schema
2. Output artifact against target version schema

Use `--strict` for additional validation:
```bash
truthctl contracts migrate \
  --file verdict.json \
  --to 2.0.0 \
  --out verdict_v2.json \
  --strict
```

## Available Migrations

### Verdict Artifact

| From | To | Changes | Breaking |
|------|----|---------|----------|
| v0.0.0 | v1.0.0 | Add contract metadata | No |
| v1.0.0 | v1.1.0 | Add optional 'evidence_refs' field | No |
| v1.1.0 | v2.0.0 | Rename 'score' to 'value', add 'confidence' | Yes |

### Readiness Artifact

| From | To | Changes | Breaking |
|------|----|---------|----------|
| v0.0.0 | v1.0.0 | Add contract metadata | No |
| v1.0.0 | v1.1.0 | Add optional 'engine_versions' | No |

### Invariants Artifact

| From | To | Changes | Breaking |
|------|----|---------|----------|
| v0.0.0 | v1.0.0 | Add contract metadata | No |

### Policy Findings Artifact

| From | To | Changes | Breaking |
|------|----|---------|----------|
| v0.0.0 | v1.0.0 | Add contract metadata | No |

### Provenance Manifest

| From | To | Changes | Breaking |
|------|----|---------|----------|
| v0.0.0 | v1.0.0 | Add contract metadata | No |

### Agent Trace Report

| From | To | Changes | Breaking |
|------|----|---------|----------|
| v0.0.0 | v1.0.0 | Add contract metadata | No |

### Reconciliation Table

| From | To | Changes | Breaking |
|------|----|---------|----------|
| v0.0.0 | v1.0.0 | Add contract metadata | No |

### Knowledge Index

| From | To | Changes | Breaking |
|------|----|---------|----------|
| v0.0.0 | v1.0.0 | Add contract metadata | No |

### Intel Scorecard

| From | To | Changes | Breaking |
|------|----|---------|----------|
| v0.0.0 | v1.0.0 | Add contract metadata | No |

## Writing Custom Migrations

To add a new migration:

1. **Define the migration function** in `src/truthcore/migrations/<artifact_type>.py`:

```python
def migrate_v1_to_v2(artifact: dict) -> dict:
    """Migrate from v1.0.0 to v2.0.0."""
    result = copy.deepcopy(artifact)
    # Apply transformations
    result["new_field"] = result.pop("old_field")
    return result
```

2. **Register the migration** in the artifact type's migration registry:

```python
from truthcore.migrations.engine import register_migration

register_migration(
    artifact_type="verdict",
    from_version="1.0.0",
    to_version="2.0.0",
    fn=migrate_v1_to_v2,
    description="Rename old_field to new_field",
    breaking=True
)
```

3. **Add tests** in `tests/test_migrations.py`:

```python
def test_verdict_v1_to_v2_migration():
    v1_artifact = load_fixture("verdict_v1.json")
    v2_artifact = migrate(v1_artifact, "1.0.0", "2.0.0")
    assert v2_artifact["new_field"] == v1_artifact["old_field"]
    validate_artifact(v2_artifact, "verdict", "2.0.0")
```

## Migration Best Practices

### For Consumers

1. **Test migrations in staging** before production
2. **Pin contract versions** during migration periods
3. **Validate outputs** after migration
4. **Keep old artifacts** until migration is verified

### For truth-core Maintainers

1. **Avoid breaking changes** when possible
2. **Provide migration paths** for all breaking changes
3. **Document all field changes** in migration docstrings
4. **Maintain backward compatibility** for at least 2 major versions
5. **Test migrations** with real-world data

## Common Migration Patterns

### Field Rename
```python
def migrate_field_rename(artifact: dict, old: str, new: str) -> dict:
    result = copy.deepcopy(artifact)
    if old in result:
        result[new] = result.pop(old)
    return result
```

### Field Addition (Optional)
```python
def migrate_add_optional_field(artifact: dict, field: str, default: Any) -> dict:
    result = copy.deepcopy(artifact)
    if field not in result:
        result[field] = default
    return result
```

### Field Addition (Required)
```python
def migrate_add_required_field(artifact: dict, field: str, calculate_fn) -> dict:
    result = copy.deepcopy(artifact)
    result[field] = calculate_fn(result)
    return result
```

### Field Removal
```python
def migrate_remove_field(artifact: dict, field: str) -> dict:
    result = copy.deepcopy(artifact)
    result.pop(field, None)
    return result
```

### Structure Flattening
```python
def migrate_flatten_nested(artifact: dict, old_path: str, new_field: str) -> dict:
    result = copy.deepcopy(artifact)
    parts = old_path.split(".")
    value = result
    for part in parts:
        value = value.get(part, {})
    result[new_field] = value
    # Remove old nested structure
    return result
```

## Troubleshooting

### Migration Not Found

**Error**: `MigrationNotFoundError: No migration from v1.0.0 to v3.0.0`

**Solution**: Migrate in steps:
```bash
truthctl contracts migrate --file art.json --to 2.0.0 --out art_v2.json
truthctl contracts migrate --file art_v2.json --to 3.0.0 --out art_v3.json
```

### Validation Failed

**Error**: `ValidationError: Output failed schema validation`

**Solution**: Check migration logic:
1. Verify all required fields are present
2. Check field types match schema
3. Review transformation logic for errors

### Breaking Change Undetected

**Error**: Output validates but consumer code breaks

**Solution**: 
1. Check if migration should be marked as breaking
2. Verify consumer code handles new structure
3. Use compat mode during transition

## Migration Testing

Run migration tests:
```bash
pytest tests/test_migrations.py -v
```

Test specific migration:
```bash
pytest tests/test_migrations.py::test_verdict_v1_to_v2 -v
```

## See Also

- [Contracts Guide](./contracts.md) - Contract system overview
- [Versioning Policy](./versioning_policy.md) - Version governance
- [Consumer Integration](./consumer_integration.md) - Consumer integration guide
