# Versioning Policy

This document defines the governance rules for truth-core contract versioning.

## Overview

truth-core follows a strict versioning policy to ensure stability for consumers while allowing the project to evolve. All contract changes must follow these rules.

## Semantic Versioning

Contract versions follow [Semantic Versioning 2.0.0](https://semver.org/):

```
MAJOR.MINOR.PATCH
```

### Version Components

| Component | Increment When | Consumer Impact |
|-----------|---------------|-----------------|
| **MAJOR** | Breaking changes | Must update code |
| **MINOR** | New features (backward compatible) | Can ignore, may benefit |
| **PATCH** | Bug fixes | Should update, no changes needed |

### Breaking vs Non-Breaking

**Breaking (MAJOR bump):**
- Removing a required field
- Renaming a field
- Changing field semantics
- Changing field type
- Removing an enum value
- Making an optional field required

**Non-Breaking (MINOR/PATCH):**
- Adding an optional field
- Adding a new artifact type
- Expanding an enum
- Adding schema constraints that existing data already satisfies
- Documentation changes

## Version Lifecycle

### Supported Versions

truth-core supports:
- Current MAJOR version (latest MINOR.PATCH)
- Previous MAJOR version (latest MINOR.PATCH)
- Critical security patches for older versions (at discretion)

### Deprecation Schedule

| Change Type | Notice Period | Support After |
|------------|---------------|---------------|
| MAJOR release | 30 days | 90 days for previous MAJOR |
| Feature deprecation | 60 days | Until next MAJOR |
| Field deprecation | 90 days | Until next MAJOR |

### End-of-Life

When a version reaches end-of-life:
- No new patches (except critical security)
- Migrations to newer versions remain available
- Validation continues to work
- No compat mode support

## Change Approval Process

### Change Types

**Trivial (PATCH)**
- Bug fixes
- Documentation fixes
- Performance improvements

**Approval**: Single maintainer review

**Minor (MINOR)**
- New optional fields
- New artifact types
- Non-breaking enhancements

**Approval**: Two maintainer reviews + CHANGELOG entry

**Breaking (MAJOR)**
- Any breaking change per definition above

**Approval**: 
- Three maintainer reviews
- RFC document
- Migration path implemented
- Tests updated
- Documentation updated
- CHANGELOG entry with notice period
- Consumer notification plan

### Change Process

1. **Create RFC** (for MINOR/MAJOR changes)
   - Describe the change
   - Justify the need
   - Document breaking vs non-breaking
   - Propose migration path (if breaking)

2. **Implement**
   - Code changes
   - Schema updates
   - Migration functions (if needed)
   - Tests

3. **Review**
   - Code review
   - Contract diff review
   - Migration testing

4. **Document**
   - CHANGELOG entry
   - Update contract docs
   - Update migration guide

5. **Release**
   - Version bump
   - Tag release
   - Announce (for MAJOR)

## CI Enforcement

The CI pipeline enforces versioning rules:

### Schema Change Detection

When schema files change:
```bash
scripts/check_contract_versions.py
```

Checks:
- Schema version matches change type
- Migration exists for breaking changes
- CHANGELOG has entry
- Tests updated

### Version Bump Validation

```bash
# Verify version bump matches change type
# - Breaking changes → MAJOR bump
# - New features → MINOR bump
# - Bug fixes → PATCH bump
```

### Migration Test Gate

```bash
pytest tests/test_migrations.py
```

All migrations must pass before merge.

## Contract Change Checklist

Before merging any contract change:

- [ ] Change classified (PATCH/MINOR/MAJOR)
- [ ] Approvals obtained (per change type)
- [ ] Schema version bumped correctly
- [ ] Migration implemented (if MAJOR)
- [ ] Tests added/updated
- [ ] CHANGELOG.md updated
- [ ] Documentation updated
- [ ] CI checks pass
- [ ] Contract diff reviewed

## Compat Mode Policy

### Support Commitment

truth-core guarantees compat mode support for:
- Last 2 MAJOR versions (configurable)
- All MINOR versions within supported MAJOR versions
- All PATCH versions

### Compat Mode Implementation

When `--compat` is requested:
1. Compute using latest internal models
2. Convert to requested version via migration
3. Validate output against target schema
4. Fail if conversion impossible

### Compat Mode Failures

When compat mode fails:
- Clear error message explaining why
- Hint to upgrade consumer code
- Option to use latest version

## Version Numbers

### Current Versions

| Artifact Type | Current | Supported Range |
|--------------|---------|-----------------|
| verdict | 2.0.0 | 1.x.x, 2.x.x |
| readiness | 1.0.0 | 1.x.x |
| invariants | 1.0.0 | 1.x.x |
| policy_findings | 1.0.0 | 1.x.x |
| provenance_manifest | 1.0.0 | 1.x.x |
| agent_trace_report | 1.0.0 | 1.x.x |
| reconciliation_table | 1.0.0 | 1.x.x |
| knowledge_index | 1.0.0 | 1.x.x |
| intel_scorecard | 1.0.0 | 1.x.x |

### truth-core Version to Contract Version Mapping

| truth-core | Default Contracts |
|------------|-------------------|
| 0.1.x | v0 (unversioned) |
| 0.2.x | v1.0.0 |
| 0.3.x | v2.0.0 (upcoming) |

## Deprecation Guidelines

### Deprecating Fields

1. Mark field as deprecated in schema:
```json
{
  "deprecated_field": {
    "type": "string",
    "deprecated": true,
    "description": "Use 'new_field' instead. Deprecated since v1.2.0, will be removed in v2.0.0"
  }
}
```

2. Add deprecation warning when field used
3. Provide migration to new field
4. Remove in next MAJOR version

### Deprecating Artifact Types

1. Announce in CHANGELOG
2. Provide migration to replacement
3. Support for 1 MAJOR version cycle
4. Remove documentation
5. Remove in next MAJOR version

## Emergency Changes

For critical security issues:
- Can bypass normal approval process
- Requires post-hoc review
- Must include security advisory
- May break compatibility if necessary

## Communication

### Release Notes

Every release includes:
- Summary of changes
- Breaking changes highlighted
- Migration instructions
- Deprecation notices
- Security fixes (if any)

### Consumer Notification

For MAJOR releases:
- 30-day advance notice
- Migration guide published
- Deprecation warnings in current version
- Announcement to known consumers

## FAQ

**Q: Can I skip versions when migrating?**
A: Yes, the migration engine chains migrations automatically.

**Q: What if my consumer breaks on a MINOR change?**
A: This is a bug - please report it. MINOR changes should be backward compatible.

**Q: How long do I have to migrate?**
A: truth-core supports the previous MAJOR version for at least 90 days after a new MAJOR release.

**Q: Can I pin to a specific PATCH version?**
A: Yes, but we recommend pinning to MAJOR.MINOR for security fixes.

**Q: What about prerelease versions?**
A: Prerelease versions (e.g., 2.0.0-alpha.1) are for testing only and have no stability guarantees.

## See Also

- [Contracts Guide](./contracts.md) - Contract system documentation
- [Migration Guide](./migrations.md) - How to migrate artifacts
- [Consumer Integration](./consumer_integration.md) - How to integrate as a consumer
