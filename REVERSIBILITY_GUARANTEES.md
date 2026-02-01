# Reversibility Guarantees

**Status**: Implemented and Tested
**Version**: v3.1
**Purpose**: Document all reversibility mechanisms in governance system
**Principle**: Every enforced decision must be cheaper to reverse than to enforce

---

## Overview

TruthCore's governance system implements comprehensive reversibility guarantees to ensure that:

1. **All decisions can be reversed** without data loss
2. **Reversal costs less** than the original decision (time/effort)
3. **Audit trails are preserved** through reversals
4. **Point-in-time reconciliation** is possible for all past decisions

This document describes every reversibility mechanism, its cost, and how to use it.

---

## Part 1: Override Reversibility

### 1.1 Override Revocation

**Problem**: Override approved but no longer needed (policy changed, approver error, etc.)
**Reversal**: `override.revoke()`

**Usage**:
```python
override = Override.create_for_high_severity(
    approved_by="tech-lead@example.com",
    reason="Prod hotfix",
    max_highs_override=10,
    duration_hours=24
)

# Later: Revoke it
override.revoke(
    revoked_by="security-lead@example.com",
    reason="Policy changed, no longer allowing this"
)

assert override.revoked
assert not override.is_valid()  # Cannot be used
```

**Audit Trail**:
- `revoked: bool` - Revocation flag
- `revoked_by: str` - Who revoked it
- `revoked_at: str` - When it was revoked (ISO timestamp)
- `revocation_reason: str` - Why it was revoked

**Cost**:
- **Enforcement**: 2-10 minutes (approval workflow)
- **Reversal**: < 1 second (method call)
- **Ratio**: ~1000x cheaper to reverse

**Limitations**:
- Can only revoke before override is used (after `mark_used()`, cannot revoke)
- Revoked overrides remain in audit trail (not deleted)

---

### 1.2 Override Extension

**Problem**: Override expires before issue resolved
**Reversal**: `Override.extend_existing()`

**Usage**:
```python
original = Override.create_for_high_severity(
    approved_by="tech-lead@example.com",
    reason="Need more time to fix",
    max_highs_override=10,
    duration_hours=24
)

# Later: Extend by 12 hours
extended = Override.extend_existing(
    existing=original,
    additional_hours=12,
    extended_by="tech-lead@example.com",
    reason="Still fixing issues"
)

assert extended.parent_override_id == original.override_id
assert extended.scope == original.scope
```

**Audit Trail**:
- `parent_override_id: str` - Links to original override
- Extension creates new override (not mutation)
- Original override remains in audit trail

**Cost**:
- **Enforcement**: Override expires, must create new one (2-10 minutes)
- **Reversal**: Create extension (< 1 second, no re-approval needed)
- **Ratio**: ~1000x cheaper to extend

**Limitations**:
- Same approver can extend without re-approval
- Different approver should follow approval workflow
- Cannot retroactively extend after expiry (create before expiry)

---

### 1.3 Override Removal (Before Use)

**Problem**: Override registered with aggregator but shouldn't be used
**Reversal**: `aggregator.remove_override()`

**Usage**:
```python
aggregator = VerdictAggregator()

override = Override.create_for_high_severity(...)
aggregator.register_override(override)

# Later: Remove it before verdict
removed = aggregator.remove_override(override.override_id)
assert removed
assert len(aggregator.overrides) == 0
```

**Cost**:
- **Enforcement**: Register override (< 1 second)
- **Reversal**: Remove from list (< 1 second)
- **Ratio**: Equal cost

**Limitations**:
- Can only remove before `aggregate()` is called
- After override is used, it's in verdict audit trail (cannot remove)

---

### 1.4 Override Scope Validation

**Problem**: Free-text scope causes silent failures
**Reversal**: `OverrideScope` schema with validation

**Usage**:
```python
# Parse and validate scope
scope = override.parse_scope()

# Access structured data
assert scope.scope_type == "max_highs"
assert scope.limit == 10
assert scope.original_limit == 5  # If range format

# Convert back to string
scope_str = scope.to_string()  # "max_highs: 5 -> 10"
```

**Supported Formats**:
- Simple: `"max_highs: 10"`
- Range: `"max_highs: 5 -> 10"`
- Legacy: `"max_highs_with_override: 10"` (auto-converted)

**Cost**:
- **Without validation**: Silent failure, override expires unused
- **With validation**: Parse error at creation time
- **Benefit**: Catch errors before enforcement

---

## Part 2: Temporal Escalation Reversibility

### 2.1 De-escalation

**Problem**: Temporal escalation was false positive (fingerprint collision, test runs, etc.)
**Reversal**: `temporal_finding.de_escalate()`

**Usage**:
```python
finding = TemporalFinding(
    finding_fingerprint="abc123",
    occurrences=3,
    escalated=True  # Already escalated
)

# De-escalate it
finding.de_escalate(
    by="human@example.com",
    reason="Fingerprint collision across microservices"
)

assert not finding.escalated
assert finding.de_escalated
assert not finding.should_escalate()  # Won't re-escalate
```

**Audit Trail**:
- `de_escalated: bool` - De-escalation flag
- `de_escalated_by: str` - Who de-escalated it
- `de_escalated_at: str` - When it was de-escalated
- `de_escalation_reason: str` - Why it was de-escalated

**Cost**:
- **Nuclear option**: Delete entire temporal record (lose all history)
- **Reversal**: De-escalate (< 1 second, preserves history)
- **Ratio**: Infinite (no data loss vs total data loss)

**Limitations**:
- De-escalated findings won't re-escalate even if occurrence count increases
- Past verdicts that used escalated severity are not updated
- Affects future verdicts only

---

### 2.2 Occurrence History Preservation

**Key Feature**: De-escalation does NOT delete occurrence history

**Preserved Data**:
- `occurrences: int` - Total occurrence count
- `runs_with_finding: list[str]` - Run IDs where found
- `severity_history: list[tuple[str, str]]` - Timestamp + severity for each occurrence
- `first_seen: str` - When first observed
- `last_seen: str` - When last observed

**Usage**:
```python
finding.de_escalate(by="human@example.com", reason="False positive")

# History still available for forensics
assert finding.occurrences == 3
assert len(finding.runs_with_finding) == 3
assert len(finding.severity_history) == 3
```

**Benefit**: Can analyze pattern later to fix fingerprint collisions

---

## Part 3: Category Assignment Reversibility

### 3.1 Category Assignment History

**Problem**: Category corrections lose track of original assignment
**Reversal**: `CategoryAssignmentHistory` versioning

**Usage**:
```python
history = CategoryAssignmentHistory(finding_id="F1")

# Scanner assigns SECURITY (0.8 confidence)
history.add_version(CategoryAssignment(
    finding_id="F1",
    category=Category.SECURITY,
    assigned_by="scanner",
    assigned_at="2026-02-01T10:00:00Z",
    reason="SQL keywords detected",
    confidence=0.8
))

# Human corrects to BUILD (1.0 confidence)
history.add_version(CategoryAssignment(
    finding_id="F1",
    category=Category.BUILD,
    assigned_by="human@example.com",
    assigned_at="2026-02-01T12:00:00Z",
    reason="Actually build config",
    confidence=1.0,
    reviewed=True
))

# Get current (highest confidence)
current = history.get_current()
assert current.category == Category.BUILD

# Get what was used at specific time (verdict reconciliation)
at_11am = history.get_at_time("2026-02-01T11:00:00Z")
assert at_11am.category == Category.SECURITY
```

**Audit Trail**:
- All versions preserved in `history.versions`
- Each version has `version: int` (auto-incremented)
- Point-in-time lookup via `get_at_time(timestamp)`

**Cost**:
- **Without versioning**: Correction loses original (cannot reconcile past verdicts)
- **With versioning**: All versions preserved (< 1 KB per version)
- **Ratio**: Infinite (reversible vs irreversible)

**Conflict Resolution**:
```python
# Detect conflicts (different categories assigned)
if history.has_conflict():
    print("Multiple categories assigned, using highest confidence")
    current = history.get_current()  # Highest confidence wins
```

---

### 3.2 Category Assignment Versioning

**Key Feature**: Every assignment has a version number

**Usage**:
```python
assignment1 = CategoryAssignment(...)
assignment2 = CategoryAssignment(...)

history.add_version(assignment1)  # version=1
history.add_version(assignment2)  # version=2

assert history.versions[0].version == 1
assert history.versions[1].version == 2
```

**Benefit**: Can track correction chains (scanner → human → senior human)

---

## Part 4: Weight Version Tracking

### 4.1 Weight Version Increments

**Problem**: Verdicts incomparable across time when weights change
**Reversal**: Version increments + snapshot in verdict

**Usage**:
```python
config = CategoryWeightConfig.create_default()
assert config.config_version == "1.0.0"

# Update weights
config.update_weights(
    {Category.SECURITY: 3.0},
    reviewed_by="security-team@example.com",
    notes="Post-incident increase"
)

assert config.config_version == "1.1.0"  # Minor version incremented

# Update again
config.update_weights(
    {Category.SECURITY: 2.5},
    reviewed_by="security-team@example.com",
    notes="Reverting partial increase"
)

assert config.config_version == "1.2.0"
```

**Version Format**: `"major.minor.patch"`
- **Major**: Reserved for breaking changes
- **Minor**: Incremented on weight updates
- **Patch**: Reserved for config fixes

**Fallback**: If version parsing fails, uses timestamp (e.g., `"1.0.1738419200"`)

---

### 4.2 Weight Snapshot in Verdicts

**Problem**: Cannot determine which weights were used for past verdicts
**Reversal**: Verdicts store `category_weights_used` snapshot

**Usage**:
```python
aggregator = VerdictAggregator(thresholds=thresholds)
result = aggregator.aggregate(mode=Mode.PR)

# Verdict captures snapshot
assert result.category_weights_used == {
    "security": 2.0,
    "privacy": 2.0,
    "finance": 1.5,
    # ...
}

assert result.weight_version == "1.0.0"
```

**Reconciliation**:
```python
# Compare verdicts across time
verdict_v1 = aggregator1.aggregate()  # Using weights v1.0.0
verdict_v2 = aggregator2.aggregate()  # Using weights v1.1.0

# Can determine which weights were used
if verdict_v1.category_weights_used["security"] != verdict_v2.category_weights_used["security"]:
    print("Weight changed between verdicts")
    print(f"V1 used: {verdict_v1.category_weights_used['security']}")
    print(f"V2 used: {verdict_v2.category_weights_used['security']}")
```

**Cost**:
- **Storage**: ~200 bytes per verdict (9 categories × ~20 bytes)
- **Benefit**: Can accurately reconstruct any past verdict's point calculation

---

## Part 5: Engine Health Retry

### 5.1 Auto-Retry for Transient Failures

**Problem**: Transient failures (timeouts, network errors) require full CI/CD re-run
**Reversal**: Auto-retry with exponential backoff

**Usage**:
```python
health = EngineHealth(
    engine_id="security-scanner",
    expected=True,
    ran=False,
    succeeded=False,
    error_message="Timeout after 300s"
)

# Check if should retry
if health.should_retry():
    # Retry the engine
    health.record_retry()
    # ... run engine again ...

    if health.should_retry():
        health.record_retry()
        # ... retry again ...
```

**Transient Error Detection**:
Automatically detected keywords in `error_message`:
- `"timeout"`, `"timed out"`
- `"network"`, `"connection refused"`, `"connection reset"`
- `"temporarily unavailable"`
- `"resource exhausted"`
- `"rate limit"`

**Retry Limits**:
- Default: `max_retries=3`
- After 3 attempts, gives up
- Each retry tracked in `retry_count`

**Cost**:
- **Without retry**: Full CI/CD re-run (10+ minutes)
- **With retry**: Auto-retry (30 seconds × 3 = ~90 seconds)
- **Ratio**: ~10x cheaper for transient failures

**Limitations**:
- Only retries transient failures (not logic errors)
- Non-transient failures still require full re-run
- Does not reduce cost for permanent failures

---

### 5.2 Retry History

**Audit Trail**:
```python
health = EngineHealth(...)
health.record_retry()
health.record_retry()

assert health.retry_count == 2
assert health.is_transient_failure  # Detected as transient
```

**Benefit**: Can analyze retry patterns to identify infrastructure issues

---

## Part 6: Verdict Reversibility

### 6.1 Past Verdict Impact

**Problem**: Category or weight corrections don't affect past verdicts
**Status**: Partially reversible (forward-only)

**Current Behavior**:
- Correcting category assignment affects **future verdicts only**
- Updating weights affects **future verdicts only**
- Past verdicts remain in audit trail with original values

**Reconciliation**:
```python
# Can determine what verdict SHOULD have been
verdict = load_past_verdict()

# Look up category at verdict time
category_history = load_category_history(finding_id)
category_at_time = category_history.get_at_time(verdict.timestamp)

# Look up weights at verdict time
weights_at_time = verdict.category_weights_used

# Recalculate points
correct_weight = weights_at_time[category_at_time.category.value]
correct_points = severity_points * correct_weight

if correct_points != verdict.finding_points:
    print(f"Verdict used incorrect category")
    print(f"Should have been: {correct_points} points")
    print(f"Actually was: {verdict.finding_points} points")
```

**Cost**:
- **Without versioning**: Cannot reconcile (impossible)
- **With versioning**: Can reconcile (manual process, ~5 minutes per verdict)
- **Ratio**: Possible vs impossible

**Limitation**: Automatic reconciliation not implemented (requires manual analysis)

---

## Part 7: Cost Summary

| Decision | Enforcement Cost | Reversal Method | Reversal Cost | Ratio |
|----------|------------------|-----------------|---------------|-------|
| **Override approval** | 2-10 min | `override.revoke()` | < 1 sec | 1000x |
| **Override extension** | 2-10 min | `Override.extend_existing()` | < 1 sec | 1000x |
| **Override registration** | < 1 sec | `aggregator.remove_override()` | < 1 sec | 1x |
| **Temporal escalation** | Automatic | `temporal.de_escalate()` | < 1 sec | ∞ (no data loss) |
| **Category assignment** | < 1 sec | Add new version | < 1 sec | 1x (with history) |
| **Weight update** | < 1 sec | Revert weights | < 1 sec | 1x (with versioning) |
| **Engine health (transient)** | 10+ min | Auto-retry | 30 sec | 20x |
| **Engine health (permanent)** | 10+ min | Full re-run | 10+ min | 1x |
| **Past verdict impact** | N/A | Manual reconciliation | 5 min | Possible vs impossible |

---

## Part 8: Guarantee Verification

### 8.1 Automated Tests

All reversibility guarantees are verified by automated tests:

**File**: `tests/test_reversibility_guarantees.py` (29 tests)

**Test Coverage**:
- Override revocation (3 tests)
- Override extension (1 test)
- Override scope validation (3 tests)
- Temporal de-escalation (4 tests)
- Category assignment history (4 tests)
- Weight versioning (3 tests)
- Engine health retry (5 tests)
- Aggregator reversibility (3 tests)
- Cost verification (3 tests)

**Run Tests**:
```bash
pytest tests/test_reversibility_guarantees.py -v
```

---

### 8.2 Reversibility Checklist

Before activating enforcement, verify:

- [ ] Override can be revoked before use
- [ ] Override can be extended without re-approval
- [ ] Temporal escalation can be de-escalated without data loss
- [ ] Category corrections preserve history
- [ ] Weight updates increment version
- [ ] Verdicts capture weight snapshot
- [ ] Engine health retries transient failures
- [ ] All reversals preserve audit trails
- [ ] Reversal cost < enforcement cost (or equal with data preservation)

---

## Part 9: Best Practices

### 9.1 When to Revoke Overrides

**Good reasons**:
- Policy changed (org no longer allows this)
- Approver error (wrong limit, wrong scope)
- Context changed (urgency resolved, issue fixed)

**Bad reasons**:
- Already used (revocation won't affect past verdict)
- Already expired (revocation unnecessary)

**Best practice**: Revoke proactively when no longer needed to prevent accidental use

---

### 9.2 When to De-escalate Temporal Findings

**Good reasons**:
- Fingerprint collision (same line in different services)
- Test findings (dev/staging, not prod)
- Issue resolved (occurrences are historical)

**Bad reasons**:
- Chronic issue (escalation is correct)
- Too many findings (escalation doing its job)

**Best practice**: Investigate escalation trigger before de-escalating

---

### 9.3 When to Extend Overrides

**Good reasons**:
- Issue taking longer than expected (but actively being fixed)
- Blocker discovered (e.g., dependency not available)
- Same approver (no re-approval needed)

**Bad reasons**:
- Issue abandoned (should expire)
- Different context (create new override instead)

**Best practice**: Extend early (before expiry) to avoid gap

---

### 9.4 When to Correct Category Assignments

**Good reasons**:
- Scanner misclassified (e.g., SECURITY → BUILD)
- Confidence low (< 0.8)
- High-impact finding (affects verdict)

**Bad reasons**:
- Low-impact finding (doesn't change verdict)
- Correct category (unnecessary churn)

**Best practice**: Review high-impact findings only (BLOCKER, HIGH severity)

---

## Part 10: Limitations and Future Work

### 10.1 Current Limitations

**1. Past Verdict Impact**
- Corrections don't update past verdicts automatically
- Manual reconciliation required (time-consuming)
- Future work: Automated reconciliation with notification

**2. Engine Health Permanent Failures**
- No cheaper reversal than full re-run
- Future work: Partial re-run (failed engine only)

**3. Override Scope**
- Only supports `max_highs` currently
- Future work: Support `max_points`, `max_category_points`

**4. Temporal Escalation Context**
- Fingerprint doesn't include environment (dev vs prod)
- Future work: Context-aware fingerprints

---

### 10.2 Non-Reversible by Design

**1. Blockers**
- Cannot override BLOCKER severity (by design)
- Reversal: Fix the issue (code change)

**2. Time**
- Cannot un-expire overrides (time is irreversible)
- Reversal: Create extension before expiry

**3. Override Consumption**
- Cannot un-mark override as used
- Reversal: Create new override

**Rationale**: These are intentionally irreversible to prevent abuse

---

## Part 11: Governance Impact

### 11.1 Trust Implications

**Before Reversibility**:
- Mistakes are expensive to fix (hours of re-work)
- Fear of approving overrides (permanent damage)
- Over-caution slows development

**After Reversibility**:
- Mistakes are cheap to fix (seconds)
- Confidence in approving overrides (can revoke if wrong)
- Faster decision-making

---

### 11.2 Enforcement Readiness

**Pre-Reversibility**:
- System not ready for enforcement (irreversible mistakes)
- Requires perfect decisions (impossible)

**Post-Reversibility**:
- System ready for enforcement (mistakes can be fixed)
- Requires good decisions (achievable)

**Verdict**: Reversibility is a prerequisite for enforcement activation

---

## Conclusion

TruthCore's governance system now guarantees that:

✅ **All decisions can be reversed** without data loss
✅ **Reversal costs ≤ enforcement cost** (or preserves data where equal)
✅ **Audit trails are preserved** through all reversals
✅ **Point-in-time reconciliation** is possible for past verdicts

**Status**: All reversibility guarantees implemented and tested (29/29 tests passing)

**Next Steps**:
1. Monitor reversal usage in production
2. Measure actual reversal costs vs enforcement costs
3. Iterate on high-cost reversals (engine health re-runs)
4. Implement automated verdict reconciliation

---

*Generated: 2026-02-01*
*Implementation: severity.py, verdict/models.py, verdict/aggregator.py*
*Tests: tests/test_reversibility_guarantees.py*
*Analysis: AUTHORITY_GAP_REVERSIBILITY_MATRIX.md*
