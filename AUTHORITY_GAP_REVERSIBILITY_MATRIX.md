# Authority Gap & Reversibility Test Matrix

**Status**: Comprehensive analysis of all governance primitives
**Purpose**: Identify where authority is ambiguous and where reversibility fails
**Scope**: All governance decision points, all lifecycle stages, all use cases

---

## Executive Summary

**Critical Findings**:
- **5 authority gaps** where decision power is assumed but not explicit
- **3 irreversible decisions** with no rollback path
- **4 reversibility cost violations** (reversal > enforcement cost)
- **7 use cases** where reversibility breaks down under load or edge cases
- **2 primitives** (TemporalFinding, EngineHealth) with zero reversal mechanisms

---

## PART 1: Authority Gap Catalog

### Gap 1: Category Assignment Conflict Resolution

**Location**: `CategoryAssignment` (severity.py:106-152)

**The Gap**:
- Scanner assigns category with `confidence=0.8`
- Human reviews and assigns different category with `confidence=1.0`
- No mechanism to determine which assignment wins

**Code Evidence**:
```python
# severity.py:107-122
@dataclass
class CategoryAssignment:
    finding_id: str
    category: Category
    assigned_by: str
    assigned_at: str
    reason: str
    confidence: float = 1.0
    reviewed: bool = False
    reviewer: str | None = None
    reviewed_at: str | None = None
```

**Authority Ambiguity**:
- Is `reviewed=True` a replacement or a confirmation?
- Does higher confidence override lower confidence?
- If timestamps differ, does latest win (last-write-wins)?
- Who has authority to reject a review?

**Observable Failure**:
```python
# Finding assigned SECURITY (2.0x) by scanner
assignment_1 = CategoryAssignment(
    finding_id="F123",
    category=Category.SECURITY,
    assigned_by="scanner-v2",
    confidence=0.8,
    reviewed=False
)

# Human reviews, assigns BUILD (1.0x)
assignment_2 = CategoryAssignment(
    finding_id="F123",
    category=Category.BUILD,
    assigned_by="human@example.com",
    confidence=1.0,
    reviewed=True,
    reviewer="human@example.com"
)

# QUESTION: Which assignment is authoritative?
# CODE: No resolution logic exists
```

**Impact**:
- Finding could accumulate 50 points (SECURITY × HIGH) or 25 points (BUILD × HIGH)
- 2x difference could flip verdict from SHIP to NO_SHIP
- No audit trail showing conflict occurred

---

### Gap 2: Override Scope Validation

**Location**: `Override.scope` (severity.py:167)

**The Gap**:
- Scope is free text: `"max_highs: 5 -> 10"`
- No schema, no parser, no validation
- Application logic parses at runtime (aggregator.py:543)

**Code Evidence**:
```python
# severity.py:167
scope: str  # What this override allows (e.g., "max_highs: 5 -> 10")

# aggregator.py:540-548
if override.is_valid() and "max_highs" in override.scope:
    try:
        override_limit = int(override.scope.split(":")[-1].strip())
        if result.highs <= override_limit:
            override_found = override
    except (ValueError, IndexError):
        pass  # Silent failure
```

**Authority Ambiguity**:
- Who validates scope string before approval?
- What happens if scope is malformed? (e.g., `"max_highs: ten"`)
- Can scope be interpreted multiple ways? (e.g., `"max_highs: 10, max_points: 500"`)
- Does approval include scope validation, or just intent?

**Observable Failure**:
```python
# Approver intends to allow 10 highs
override = Override.create_for_high_severity(
    approved_by="tech-lead@example.com",
    reason="Hotfix for prod incident",
    max_highs_override=10,
    duration_hours=24
)
# scope = "max_highs_with_override: 10"

# BUT: Aggregator expects "max_highs: 10"
# Line 540: if "max_highs" in override.scope
# Line 543: override_limit = int(override.scope.split(":")[-1].strip())

# "max_highs_with_override: 10" WILL MATCH (contains "max_highs")
# BUT: scope.split(":")[-1] = " 10" (works by accident)

# FRAGILE: Depends on substring matching, not schema validation
```

**Impact**:
- Override approved but unusable due to format mismatch
- Silent failure: override expires without being applied
- No feedback loop: approver never knows override didn't work

---

### Gap 3: Temporal Escalation Fingerprint Collisions

**Location**: `compute_finding_fingerprint()` (aggregator.py:182)

**The Gap**:
- Fingerprint = `rule_id:file_path:line_number`
- Collisions possible when:
  - Same rule, same file, different context (dev vs prod)
  - Same rule, file renamed/moved, same line number
  - Same rule, unrelated code at same location after refactor

**Code Evidence**:
```python
# aggregator.py:182
fingerprint = self.compute_finding_fingerprint(rule_id or finding_id, location)

# aggregator.py (implementation not shown, but documented as):
# f"{rule_id}:{file_path}:{line_number}"
```

**Authority Ambiguity**:
- Who decides if two findings are "the same"?
- Algorithm assumes sameness, but doesn't track context
- Human cannot override false positive escalation

**Observable Failure**:
```python
# Run 1: Dev environment
finding_1 = {
    "rule_id": "SQL-INJECTION-001",
    "location": "app/db.py:42",
    "message": "Test SQL injection in dev sandbox"
}
# fingerprint = "SQL-INJECTION-001:app/db.py:42"
# occurrences = 1

# Run 2: Staging environment
finding_2 = {
    "rule_id": "SQL-INJECTION-001",
    "location": "app/db.py:42",
    "message": "Test SQL injection in staging"
}
# SAME fingerprint
# occurrences = 2

# Run 3: Prod environment
finding_3 = {
    "rule_id": "SQL-INJECTION-001",
    "location": "app/db.py:42",
    "message": "ACTUAL SQL injection in prod (urgent)"
}
# SAME fingerprint
# occurrences = 3 → ESCALATE from HIGH to BLOCKER

# PROBLEM: Dev/staging tests escalated prod issue to BLOCKER
# AUTHORITY QUESTION: Who decides these are "different" contexts?
```

**Impact**:
- False positive escalation blocks shipping
- No override exists for temporal escalation (by design)
- Only recourse: Clear entire temporal store (lose all history)

---

### Gap 4: Engine Health Interpretation

**Location**: `EngineHealth.is_healthy()` (severity.py:335-341)

**The Gap**:
- System reports factual status: `ran=False`, `error_message="timeout"`
- But doesn't distinguish:
  - Infrastructure timeout (retry, don't block)
  - Logic error (fix immediately)
  - Expected failure (test, ignore)

**Code Evidence**:
```python
# severity.py:335-341
def is_healthy(self) -> bool:
    if not self.expected:
        return True  # Not expected, so absence is OK
    if not self.ran:
        return False  # Expected but didn't run
    return self.succeeded  # Ran, so check if it succeeded
```

**Authority Ambiguity**:
- Who interprets `error_message` to determine severity?
- System treats all `ran=False` as unhealthy (binary)
- No mechanism to mark "unhealthy but acceptable"

**Observable Failure**:
```python
# Engine times out due to network congestion (transient)
health_1 = EngineHealth(
    engine_id="security-scanner",
    expected=True,
    ran=False,
    succeeded=False,
    error_message="Timeout after 300s",
    execution_time_ms=None
)
# is_healthy() = False
# Verdict degrades to DEGRADED (no override possible)

# Engine fails due to SQL injection found (expected behavior)
health_2 = EngineHealth(
    engine_id="security-scanner",
    expected=True,
    ran=True,
    succeeded=False,
    error_message="SQL injection found, blocking build",
    execution_time_ms=2500
)
# is_healthy() = False (BUT: This is correct behavior!)
# QUESTION: Should this degrade verdict?
```

**Impact**:
- Transient failures (timeout) treated same as logic errors
- No way to distinguish "failed because it found issues" from "failed to run"
- Override cannot fix engine health degradation (by design)

---

### Gap 5: Category Weight Review Enforcement

**Location**: `CategoryWeightConfig.is_review_overdue()` (severity.py:386-393)

**The Gap**:
- Review flag exists: `is_review_overdue() -> bool`
- But no enforcement: System continues using overdue weights
- No mechanism to require review before use

**Code Evidence**:
```python
# severity.py:386-393
def is_review_overdue(self) -> bool:
    try:
        last_review_dt = datetime.fromisoformat(self.last_reviewed.replace("Z", "+00:00"))
        next_review = last_review_dt + timedelta(days=self.review_frequency_days)
        return datetime.now(UTC) >= next_review
    except ValueError:
        return True  # If we can't parse, assume review is needed

# severity.py:395-397
def get_weight(self, category: Category) -> float:
    return self.weights.get(category, 1.0)
    # NO CHECK: Doesn't call is_review_overdue()
```

**Authority Ambiguity**:
- Are overdue weights still legitimate?
- Who has authority to use weights past review date?
- Is review requirement advisory or mandatory?

**Observable Failure**:
```python
# Day 0: Security team sets SECURITY weight to 2.0x
config = CategoryWeightConfig.create_default()
config.update_weights(
    {Category.SECURITY: 2.0},
    reviewed_by="security-team@example.com",
    notes="Post-incident increase"
)

# Day 91: Review overdue
assert config.is_review_overdue() == True

# Day 91: Verdict still uses 2.0x multiplier
weight = config.get_weight(Category.SECURITY)
assert weight == 2.0  # Uses overdue weight!

# QUESTION: Is this weight still authoritative after 90 days?
```

**Impact**:
- Organizational values encoded in weights become stale
- No forcing function to review post-incident weight changes
- Weights set during crisis may persist indefinitely

---

## PART 2: Reversibility Test Matrix

### Test 1: Override Lifecycle Reversibility

**Stages**: Creation → Validation → Application → Expiry → Reversal

#### Stage 1: Creation
```python
override = Override.create_for_high_severity(
    approved_by="tech-lead@example.com",
    reason="Prod hotfix",
    max_highs_override=10,
    duration_hours=24
)
```
**Reversible?**: ✅ YES (don't register with aggregator)
**Cost**: 0 operations (simply don't use the object)

#### Stage 2: Validation (is_valid)
```python
aggregator.register_override(override)
assert override.is_valid() == True
```
**Reversible?**: ✅ YES (remove from aggregator.overrides list)
**Cost**: 1 operation (list removal)
**Implementation**:
```python
# Would need to add:
aggregator.remove_override(override_id)
```
**GAP**: No `remove_override()` method exists

#### Stage 3: Application (mark_used)
```python
# aggregator.py:552
override.mark_used(verdict_id)
result.overrides_applied.append(override)
```
**Reversible?**: ❌ NO
**Reason**:
- `mark_used()` sets `used=True`, `used_at=timestamp`, `verdict_id`
- `is_valid()` checks `if self.used: return False`
- No `unmark_used()` or `reset()` method

**Code Evidence**:
```python
# severity.py:191-195
def mark_used(self, verdict_id: str) -> None:
    self.used = True
    self.used_at = datetime.now(UTC).isoformat()
    self.verdict_id = verdict_id

# severity.py:173-181
def is_valid(self) -> bool:
    if self.used:
        return False  # PERMANENT
```

**Workaround**: Create new override with same scope (forward-only reversal)
**Cost**: Full approval cycle (minutes to hours)

#### Stage 4: Expiry
```python
# After 24 hours
assert override.is_expired() == True
assert override.is_valid() == False
```
**Reversible?**: ❌ NO
**Reason**: Time is irreversible
**Workaround**: Create new override (extension)
**Cost**: Full approval cycle

#### Stage 5: Reversal (revoke before use)
**Reversible?**: ⚠️ PARTIAL (only if not yet used)
**Gap**: No built-in revocation mechanism
**Required Implementation**:
```python
def revoke_override(self, override_id: str, revoked_by: str, reason: str) -> None:
    # Remove from active overrides
    # Record revocation in audit trail
    # Prevent future use
    pass
```

**Cost Analysis**:
| Stage | Reversible? | Cost | Method |
|-------|-------------|------|--------|
| Creation | ✅ YES | Free | Don't register |
| Validation | ⚠️ PARTIAL | 1 op | remove_override() (NOT IMPLEMENTED) |
| Application | ❌ NO | N/A | Cannot unmark_used() |
| Expiry | ❌ NO | N/A | Time is irreversible |
| Revocation | ⚠️ PARTIAL | 1 op + audit | revoke_override() (NOT IMPLEMENTED) |

---

### Test 2: Category Assignment Reversibility

**Stages**: Assignment → Review → Correction → Re-correction

#### Stage 1: Scanner Assignment
```python
assignment = CategoryAssignment(
    finding_id="F123",
    category=Category.SECURITY,  # 2.0x multiplier
    assigned_by="scanner-v2",
    assigned_at=datetime.now(UTC).isoformat(),
    reason="SQL keywords detected",
    confidence=0.8,
    reviewed=False
)
```
**Reversible?**: ✅ YES (create new assignment)
**Cost**: 1 write operation

#### Stage 2: Human Review
```python
# Human corrects to BUILD category (1.0x)
assignment_corrected = CategoryAssignment(
    finding_id="F123",
    category=Category.BUILD,
    assigned_by="scanner-v2",  # Original assigner
    assigned_at=assignment.assigned_at,  # Preserve timestamp
    reason="Actually a build config issue",
    confidence=1.0,
    reviewed=True,
    reviewer="human@example.com",
    reviewed_at=datetime.now(UTC).isoformat()
)
```
**Reversible?**: ✅ YES (affects future verdicts only)
**Cost**: 1 write operation
**Gap**: No versioning—old assignment is lost

#### Stage 3: Re-correction (human was wrong)
```python
# Second human reverts to SECURITY
assignment_v3 = CategoryAssignment(
    finding_id="F123",
    category=Category.SECURITY,
    assigned_by="scanner-v2",
    assigned_at=assignment.assigned_at,
    reason="First review was incorrect, SQL injection confirmed",
    confidence=1.0,
    reviewed=True,
    reviewer="security-lead@example.com",
    reviewed_at=datetime.now(UTC).isoformat()
)
```
**Reversible?**: ✅ YES
**Cost**: 1 write operation
**Gap**: No audit trail of correction history

**Cost Analysis**:
| Stage | Reversible? | Cost | Limitation |
|-------|-------------|------|------------|
| Assignment | ✅ YES | 1 op | None |
| Review | ✅ YES | 1 op | Forward-only (past verdicts unchanged) |
| Re-correction | ✅ YES | 1 op | No version history |

**Critical Gap**: **Past verdicts are NOT updated**
- If verdict V1 used SECURITY (2.0x), shipped with 100 points
- Then category corrected to BUILD (1.0x)
- Verdict V1 remains at 100 points (should have been 50)
- **No mechanism to flag "verdict based on incorrect category"**

---

### Test 3: Temporal Escalation Reversibility

**Stages**: First Occurrence → Escalation Threshold → Escalation → Reversal

#### Stage 1: First Occurrence
```python
fingerprint = "SQL-001:app/db.py:42"
temporal = TemporalFinding(
    finding_fingerprint=fingerprint,
    first_seen="2026-02-01T10:00:00Z",
    last_seen="2026-02-01T10:00:00Z",
    occurrences=1
)
```
**Reversible?**: ✅ YES (delete from temporal store)
**Cost**: 1 delete operation

#### Stage 2: Escalation Threshold (3 occurrences)
```python
# Occurrence 2
temporal.record_occurrence("run_002", "HIGH")
# occurrences = 2

# Occurrence 3
temporal.record_occurrence("run_003", "HIGH")
# occurrences = 3
# should_escalate() = True
```
**Reversible?**: ⚠️ PARTIAL (can reset occurrence count)
**Cost**: 1 write operation
**Gap**: No built-in decrementation method

#### Stage 3: Escalation Applied
```python
# aggregator.py:191-207
if temporal_record.should_escalate(threshold_occurrences=3):
    escalated_from = severity  # HIGH
    severity = Severity.BLOCKER  # Bumped
    temporal_record.escalate(
        f"Chronic issue: appeared 3 times, escalated from HIGH to BLOCKER"
    )

# severity.py:274-278
def escalate(self, reason: str) -> None:
    self.escalated = True  # PERMANENT FLAG
    self.escalated_at = datetime.now(UTC).isoformat()
    self.escalation_reason = reason
```
**Reversible?**: ❌ NO
**Reason**:
- `escalated=True` is permanent flag
- No `de_escalate()` or `reset_escalation()` method
- Future runs will skip escalation (`if self.escalated: return False`)

**Code Evidence**:
```python
# severity.py:268-272
def should_escalate(self, threshold_occurrences: int = 3) -> bool:
    if self.escalated:
        return False  # Once escalated, never again
    return self.occurrences >= threshold_occurrences
```

#### Stage 4: Reversal Attempt
**Option 1**: Delete temporal record
```python
del self.temporal_findings[fingerprint]
```
**Effect**: Loses all history (1st occurrence timestamp, occurrence count, severity history)
**Cost**: TOTAL (irreversible data loss)

**Option 2**: Reset occurrence count (NO METHOD EXISTS)
```python
# Would need:
temporal.reset_occurrences(new_count=1, reason="False positive")
```
**Effect**: Preserves history but allows re-escalation
**Cost**: 1 write operation
**Gap**: NOT IMPLEMENTED

**Option 3**: Mark escalation as false positive (NO METHOD EXISTS)
```python
# Would need:
temporal.mark_escalation_invalid(reason="Fingerprint collision")
temporal.escalated = False  # Reset flag
```
**Effect**: Prevents future escalation, preserves history
**Cost**: 1 write operation
**Gap**: NOT IMPLEMENTED

**Cost Analysis**:
| Stage | Reversible? | Cost | Impact |
|-------|-------------|------|--------|
| First occurrence | ✅ YES | 1 delete | Loses history |
| Threshold reached | ⚠️ PARTIAL | 1 write | No built-in method |
| Escalation applied | ❌ NO | TOTAL | Permanent flag |
| Reversal | ❌ NO | N/A | Nuclear option (clear all history) |

**Critical Finding**: **Temporal escalation is irreversible by design**
- Once `escalated=True`, finding stays escalated forever
- Only recourse: Delete entire temporal record
- Deleting record loses valuable occurrence data

---

### Test 4: Engine Health Reversibility

**Stages**: Health Report → Degradation → Reversal

#### Stage 1: Unhealthy Report
```python
health = EngineHealth(
    engine_id="security-scanner",
    expected=True,
    ran=False,
    succeeded=False,
    error_message="Timeout after 300s"
)
```
**Reversible?**: ✅ YES (re-run engine)
**Cost**: Full engine execution (minutes)

#### Stage 2: Verdict Degradation
```python
# aggregator.py:518-530
if result.engines_failed > 0:
    if thresholds.require_all_engines_healthy:
        no_ship_reasons.append(f"{result.engines_failed} engine(s) failed")
    else:
        degraded = True  # Verdict becomes DEGRADED
```
**Reversible?**: ✅ YES (new run with healthy signal)
**Cost**: Full CI/CD pipeline re-run (10+ minutes)

#### Stage 3: Reversal
```python
# New run with healthy engine
health_corrected = EngineHealth(
    engine_id="security-scanner",
    expected=True,
    ran=True,
    succeeded=True,
    error_message=None,
    execution_time_ms=2500
)
```
**Reversible?**: ✅ YES
**Cost**: **10+ minutes** (full CI/CD re-run)

**Cost Analysis**:
| Stage | Reversible? | Cost | Violates "Cheaper to Reverse"? |
|-------|-------------|------|-------------------------------|
| Health report | ✅ YES | 10+ min | ❌ YES (reversal = re-run, same cost) |
| Degradation | ✅ YES | 10+ min | ❌ YES |
| Reversal | ✅ YES | 10+ min | ❌ YES |

**Critical Violation**: **Reversal cost equals enforcement cost**
- Principle: "Reversal must be cheaper than enforcement"
- Reality: Reversal requires full CI/CD re-run
- **No cheaper reversal path exists**

---

### Test 5: Category Weight Update Reversibility

**Stages**: Update → Review → Revert → Forward Impact

#### Stage 1: Weight Update
```python
config = CategoryWeightConfig.create_default()
# Original: SECURITY = 2.0x

config.update_weights(
    {Category.SECURITY: 3.0},  # Increase to 3.0x
    reviewed_by="security-team@example.com",
    notes="Post-incident escalation"
)
```
**Reversible?**: ✅ YES (update back to 2.0)
**Cost**: 1 write operation

#### Stage 2: Verdicts Using New Weight
```python
# Verdict V1: Uses SECURITY = 3.0x
# Finding F1: HIGH severity, SECURITY category
# Points: 50 × 3.0 = 150 points
# Result: NO_SHIP (threshold = 100)
```
**Reversible?**: ⚠️ PARTIAL (future verdicts only)
**Gap**: Past verdicts use old weight, incomparable to future

#### Stage 3: Revert Weight
```python
config.update_weights(
    {Category.SECURITY: 2.0},  # Revert to 2.0x
    reviewed_by="security-team@example.com",
    notes="Reverting post-incident escalation"
)
```
**Reversible?**: ✅ YES
**Cost**: 1 write operation

#### Stage 4: Forward Impact
```python
# Verdict V2: Uses SECURITY = 2.0x
# Finding F1 (same issue): HIGH severity, SECURITY category
# Points: 50 × 2.0 = 100 points
# Result: SHIP (threshold = 100)

# PROBLEM: V1 (150 pts, NO_SHIP) vs V2 (100 pts, SHIP)
# Same finding, different verdicts due to weight change
```

**Cost Analysis**:
| Stage | Reversible? | Cost | Limitation |
|-------|-------------|------|------------|
| Weight update | ✅ YES | 1 op | None |
| Verdict impact | ⚠️ PARTIAL | N/A | Past verdicts unchanged |
| Revert | ✅ YES | 1 op | None |
| Comparability | ❌ NO | N/A | Verdicts across time incomparable |

**Critical Gap**: **No mechanism to flag "verdict based on different weights"**
- Verdicts before/after weight change use different scoring
- Cannot compare V1 vs V2 directly
- No audit trail showing "weight changed between these verdicts"

---

## PART 3: Use Cases Where Reversibility Fails

### Use Case 1: Override Consumed During Outage

**Scenario**:
1. Tech lead approves override: "max_highs: 10" for 24h
2. Override consumed at T+0h for urgent prod hotfix
3. At T+1h, another urgent issue needs same override
4. Override already marked `used=True`, cannot reuse

**Reversibility Failure**:
- Override is single-use by design (severity.py:173-176)
- No way to "un-consume" override
- Cannot create new override mid-outage (approval latency)

**Impact**:
- Second urgent fix blocked by NO_SHIP verdict
- Must wait for approval cycle (minutes to hours)
- Outage extended due to governance process

**Workaround**: Pre-approve multiple overrides
**Cost**: Requires predicting failure scenarios

---

### Use Case 2: Temporal Escalation False Positive in Monorepo

**Scenario**:
1. Monorepo with 50 microservices
2. Same rule triggers in same file path across services:
   - `service-A/app/db.py:42`
   - `service-B/app/db.py:42` (copied code)
   - `service-C/app/db.py:42` (template)
3. Fingerprint: `SQL-001:app/db.py:42` (same for all)
4. 3 occurrences → escalation to BLOCKER
5. All 50 services blocked from shipping

**Reversibility Failure**:
- No way to de-escalate specific service
- Clearing temporal store affects all 50 services
- No mechanism to distinguish "same line in different context"

**Impact**:
- False positive blocks entire monorepo
- Nuclear option: Clear temporal store (lose all history)
- Cannot target reversal to specific service

**Workaround**: Include service name in fingerprint
**Cost**: Requires code change, not configuration change

---

### Use Case 3: Category Assignment Correction After Shipping

**Scenario**:
1. Scanner assigns SECURITY (2.0x) to finding F1
2. Verdict V1: 100 points (50 × 2.0), ships as SHIP
3. Post-deploy: Security team reviews, corrects to BUILD (1.0x)
4. Verdict V1 should have been 50 points (50 × 1.0)

**Reversibility Failure**:
- Correction applies to future verdicts only
- Past verdict V1 remains in audit trail as "correct"
- No mechanism to flag "verdict based on incorrect category"

**Impact**:
- Audit trail shows V1 as SHIP (100 points)
- Cannot determine if past decisions were based on correct data
- Compliance risk: Cannot prove past verdicts were legitimate

**Workaround**: Manual reconciliation of past verdicts
**Cost**: Hours of manual audit work

---

### Use Case 4: Engine Health Transient Failure During Spike

**Scenario**:
1. Traffic spike causes engine timeout (300s)
2. Engine reports `ran=False`, `error_message="Timeout"`
3. Verdict degrades to DEGRADED
4. Spike ends, engine would succeed if retried
5. But verdict already issued as DEGRADED

**Reversibility Failure**:
- No auto-retry for engine health
- No mechanism to mark "transient failure, retry"
- Re-running entire CI/CD pipeline is expensive (10+ min)

**Impact**:
- Legitimate code blocked by transient infrastructure issue
- Reversal cost (10 min) equals initial cost (10 min)
- Violates "reversal cheaper than enforcement" principle

**Workaround**: Implement retry logic with exponential backoff
**Cost**: Code change, not configuration change

---

### Use Case 5: Override Expires During Approval Chain

**Scenario**:
1. Override created: expires at T+24h
2. Warning issued at T+18h (6h before expiry)
3. Tech lead on vacation, delegate not notified
4. Override expires at T+24h
5. At T+24h+1m, urgent fix needs override
6. Override marked `is_expired()=True`, cannot use

**Reversibility Failure**:
- Cannot "un-expire" override
- Cannot extend override retroactively
- Must create new override (approval latency)

**Impact**:
- Governance process blocks urgent fix
- Warning window (6h) insufficient if approver unavailable
- No mechanism for delegate approval

**Workaround**: Longer warning windows (24h, 48h)
**Cost**: Noise (too many warnings)

---

### Use Case 6: Category Weight Review Missed During Incident

**Scenario**:
1. Security incident: SECURITY weight increased to 3.0x
2. 90 days later: Review due
3. Incident context forgotten, review not performed
4. Verdicts continue using 3.0x weight (post-incident value)
5. Organization's risk tolerance has changed, but weights haven't

**Reversibility Failure**:
- No enforcement: Overdue weights still used
- No notification: is_review_overdue() checked but not acted upon
- No decay: Weights don't revert to baseline after review due

**Impact**:
- Post-incident weights persist indefinitely
- Organizational values drift from encoded weights
- No forcing function to review

**Workaround**: Manual calendar reminders
**Cost**: Out-of-band process (not in system)

---

### Use Case 7: Verdict History Reconciliation After Weight Change

**Scenario**:
1. Days 1-90: SECURITY = 2.0x
2. Day 91: SECURITY changed to 3.0x
3. Days 91-180: SECURITY = 3.0x
4. Compliance audit asks: "Show all SHIP verdicts for Q1"
5. Q1 spans days 1-90, includes both weight regimes

**Reversibility Failure**:
- Verdicts from days 1-90 used 2.0x
- Verdicts from days 60-90 used 3.0x
- No metadata in verdict showing "weight version"
- Cannot distinguish which weight was used

**Impact**:
- Cannot reconstruct decision context
- Cannot compare verdicts across time accurately
- Compliance risk: Cannot prove decisions used correct weights

**Workaround**: Add weight version to verdict metadata
**Cost**: Schema change, data migration

---

## PART 4: Reversal Cost Analysis

### Cost Matrix

| Decision Type | Stage | Reversal Method | Cost | Cheaper Than Enforcement? | Gap |
|---------------|-------|-----------------|------|---------------------------|-----|
| **Override** | Pre-use | Don't register | Free | ✅ YES | None |
| **Override** | Registered | Remove from list | 1 op | ✅ YES | No remove_override() |
| **Override** | Used | Create new | Full approval | ❌ NO (equal) | No un-mark |
| **Override** | Expired | Create new | Full approval | ❌ NO (equal) | No extension API |
| **Category Assignment** | Scanner assigned | Overwrite | 1 op | ✅ YES | None |
| **Category Assignment** | Human reviewed | Overwrite | 1 op | ✅ YES | No version history |
| **Category Assignment** | Past verdict | N/A | N/A | ❌ NO | Irreversible |
| **Temporal Escalation** | Pre-escalation | Delete record | 1 op | ✅ YES | Lose history |
| **Temporal Escalation** | Post-escalation | Delete record | 1 op + data loss | ⚠️ PARTIAL | Permanent flag |
| **Temporal Escalation** | Used in verdict | N/A | N/A | ❌ NO | Irreversible |
| **Engine Health** | Unhealthy report | Re-run engine | 10+ min | ❌ NO (equal) | Same cost |
| **Engine Health** | Verdict degraded | Re-run pipeline | 10+ min | ❌ NO (equal) | Same cost |
| **Category Weight** | Updated | Revert weight | 1 op | ✅ YES | None |
| **Category Weight** | Past verdicts | N/A | N/A | ❌ NO | Incomparable |

### Critical Cost Violations

**Violation 1: Override re-approval cost equals initial approval**
- Initial: 2-10 minutes (approval workflow)
- Reversal: 2-10 minutes (new approval)
- **Same cost**, violates "cheaper to reverse" principle

**Violation 2: Engine health re-run cost equals initial run**
- Initial: 10+ minutes (full CI/CD pipeline)
- Reversal: 10+ minutes (re-run pipeline)
- **Same cost**, violates principle

**Violation 3: Temporal escalation reversal requires data loss**
- Initial: Automatic (0 cost)
- Reversal: Delete record (lose occurrence history, first_seen timestamp)
- **Higher cost** (data loss), violates principle

**Violation 4: Past verdict impact is irreversible**
- Category assignment correction
- Weight updates
- Temporal escalation
- **Infinite cost** (cannot change past), violates principle

---

## PART 5: Reversibility Breakdown Signals

### Signal 1: Temporal Store Growth Rate

**Metric**: `len(temporal_findings)` over time

**Healthy**: Linear growth with codebase size
**Breakdown**: Exponential growth (fingerprint collisions)

**Detection**:
```python
if len(temporal_findings) > num_source_files * 10:
    # Likely fingerprint collision issue
    # Each file should have ~1-10 unique findings
    pass
```

**Impact**: False positive escalations increase
**Reversibility Impact**: More records to clear (nuclear option becomes more expensive)

---

### Signal 2: Override Expiry Rate

**Metric**: `expired_overrides / total_overrides` over time

**Healthy**: < 10% of overrides expire without use
**Breakdown**: > 50% expire without use

**Detection**:
```python
unused_expired = [o for o in overrides if o.is_expired() and not o.used]
if len(unused_expired) / len(overrides) > 0.5:
    # Approval process not aligned with usage
    pass
```

**Impact**: Approvals wasted, governance overhead without benefit
**Reversibility Impact**: Cannot extend expired overrides, must re-approve

---

### Signal 3: Category Assignment Review Rate

**Metric**: `reviewed_assignments / total_assignments` over time

**Healthy**: > 5% of high-impact findings reviewed
**Breakdown**: < 1% reviewed (human review not happening)

**Detection**:
```python
high_impact = [a for a in assignments if a.category in [Category.SECURITY, Category.PRIVACY]]
reviewed = [a for a in high_impact if a.reviewed]
if len(reviewed) / len(high_impact) < 0.05:
    # Human review not scaling with findings
    pass
```

**Impact**: Scanner errors compound, no correction feedback loop
**Reversibility Impact**: More incorrect categories in past verdicts (irreversible)

---

### Signal 4: Engine Health Failure Rate

**Metric**: `unhealthy_engines / total_expected_engines` over time

**Healthy**: < 1% failure rate
**Breakdown**: > 10% failure rate (infrastructure issues)

**Detection**:
```python
unhealthy = [h for h in engine_health if not h.is_healthy()]
if len(unhealthy) / len(engine_health) > 0.10:
    # Infrastructure degradation, not code quality issue
    pass
```

**Impact**: Verdicts degraded due to infrastructure, not code
**Reversibility Impact**: Re-run cost becomes prohibitive at scale

---

### Signal 5: Category Weight Staleness

**Metric**: `days_since_review` for category weights

**Healthy**: Review every 90 days
**Breakdown**: > 180 days without review

**Detection**:
```python
if config.is_review_overdue():
    days_overdue = (datetime.now(UTC) - datetime.fromisoformat(config.last_reviewed)).days - config.review_frequency_days
    if days_overdue > 90:
        # Weights are 2x overdue, likely stale
        pass
```

**Impact**: Organizational values drift from encoded weights
**Reversibility Impact**: Weight changes affect more verdicts (larger discontinuity)

---

### Signal 6: Verdict History Discontinuities

**Metric**: Same finding, different verdict over time

**Healthy**: Verdict consistent for same code
**Breakdown**: Verdict flips due to weight/threshold changes

**Detection**:
```python
# Track finding F1 across verdicts V1, V2, V3
if V1.result == "SHIP" and V2.result == "NO_SHIP" and finding_unchanged(F1):
    # Verdict flip due to governance change, not code change
    pass
```

**Impact**: Cannot trust verdict consistency
**Reversibility Impact**: Cannot determine which verdict was "correct"

---

### Signal 7: Audit Trail Conflicts

**Metric**: Multiple category assignments for same finding

**Healthy**: 1 assignment per finding (or reviewed=True supersedes)
**Breakdown**: Multiple assignments, no clear winner

**Detection**:
```python
assignments_per_finding = {}
for a in category_assignments:
    if a.finding_id not in assignments_per_finding:
        assignments_per_finding[a.finding_id] = []
    assignments_per_finding[a.finding_id].append(a)

conflicts = {k: v for k, v in assignments_per_finding.items() if len(v) > 1}
if len(conflicts) > 0:
    # Conflicting assignments exist
    pass
```

**Impact**: Ambiguous authority, no canonical category
**Reversibility Impact**: Cannot reverse to "correct" state (no ground truth)

---

## PART 6: Recommendations for Fixing Reversibility Gaps

### Recommendation 1: Add Override Revocation

**Implementation**:
```python
@dataclass
class Override:
    # ... existing fields ...
    revoked: bool = False
    revoked_by: str | None = None
    revoked_at: str | None = None
    revocation_reason: str | None = None

    def revoke(self, revoked_by: str, reason: str) -> None:
        self.revoked = True
        self.revoked_by = revoked_by
        self.revoked_at = datetime.now(UTC).isoformat()
        self.revocation_reason = reason

    def is_valid(self) -> bool:
        if self.used or self.revoked:
            return False
        # ... existing expiry check ...
```

**Cost**: < 1 second
**Enables**: Revoke override before use (cheaper than re-approval)

---

### Recommendation 2: Add Temporal De-escalation

**Implementation**:
```python
@dataclass
class TemporalFinding:
    # ... existing fields ...
    de_escalated: bool = False
    de_escalated_by: str | None = None
    de_escalated_at: str | None = None
    de_escalation_reason: str | None = None

    def de_escalate(self, by: str, reason: str) -> None:
        self.escalated = False
        self.de_escalated = True
        self.de_escalated_by = by
        self.de_escalated_at = datetime.now(UTC).isoformat()
        self.de_escalation_reason = reason
```

**Cost**: < 1 second
**Enables**: Mark escalation as false positive without losing history

---

### Recommendation 3: Add Category Assignment Versioning

**Implementation**:
```python
@dataclass
class CategoryAssignmentHistory:
    finding_id: str
    versions: list[CategoryAssignment] = field(default_factory=list)

    def add_version(self, assignment: CategoryAssignment) -> None:
        self.versions.append(assignment)

    def get_current(self) -> CategoryAssignment:
        # Return highest confidence, or latest if tied
        return max(self.versions, key=lambda a: (a.confidence, a.assigned_at))

    def get_at_time(self, timestamp: str) -> CategoryAssignment:
        # Return assignment active at timestamp
        valid_versions = [a for a in self.versions if a.assigned_at <= timestamp]
        return max(valid_versions, key=lambda a: (a.confidence, a.assigned_at))
```

**Cost**: < 1 second per lookup
**Enables**: Track which category was used for each verdict

---

### Recommendation 4: Add Weight Version to Verdict

**Implementation**:
```python
@dataclass
class VerdictResult:
    # ... existing fields ...
    category_weight_version: str  # Links to CategoryWeightConfig.config_version
    category_weights_used: dict[str, float]  # Snapshot of weights at verdict time
```

**Cost**: Negligible (small metadata)
**Enables**: Compare verdicts across time accurately

---

### Recommendation 5: Add Engine Health Retry Logic

**Implementation**:
```python
@dataclass
class EngineHealth:
    # ... existing fields ...
    retry_count: int = 0
    max_retries: int = 3

    def should_retry(self) -> bool:
        if not self.ran and "timeout" in (self.error_message or "").lower():
            return self.retry_count < self.max_retries
        return False
```

**Cost**: 3x max runtime (with exponential backoff, ~10 min total)
**Enables**: Automatic recovery from transient failures
**Note**: Still violates "cheaper to reverse" for non-transient failures

---

### Recommendation 6: Add Override Extension API

**Implementation**:
```python
@dataclass
class Override:
    # ... existing fields ...

    @classmethod
    def extend_existing(cls, existing: Override, additional_hours: int, extended_by: str, reason: str) -> Override:
        """Create new override that extends an existing one."""
        new_expires = datetime.fromisoformat(existing.expires_at) + timedelta(hours=additional_hours)
        return cls(
            override_id=f"{existing.override_id}-ext-{int(datetime.now(UTC).timestamp())}",
            approved_by=extended_by,
            approved_at=datetime.now(UTC).isoformat(),
            expires_at=new_expires.isoformat(),
            reason=f"Extension of {existing.override_id}: {reason}",
            scope=existing.scope,
            conditions=existing.conditions,
            parent_override_id=existing.override_id  # Link to original
        )
```

**Cost**: < 1 second (no approval needed if same approver)
**Enables**: Extend override without full re-approval

---

## PART 7: Summary of Findings

### Authority Gaps (5 identified)
1. **Category assignment conflict resolution** - No mechanism when scanner and human disagree
2. **Override scope validation** - Free text, no schema, parsed at runtime
3. **Temporal fingerprint collisions** - Algorithm assumes sameness, human cannot override
4. **Engine health interpretation** - System reports facts, but doesn't distinguish severity
5. **Category weight review enforcement** - Flag exists, but no enforcement

### Irreversible Decisions (3 identified)
1. **Override mark_used()** - Cannot un-mark, must create new override
2. **Temporal escalation flag** - escalated=True is permanent
3. **Past verdict impact** - Category/weight changes don't update past verdicts

### Cost Violations (4 identified)
1. **Override re-approval** - Same cost as initial approval
2. **Engine health re-run** - Same cost as initial run (10+ min)
3. **Temporal escalation reversal** - Requires data loss
4. **Past verdict reconciliation** - Infinite cost (impossible)

### Reversibility Breakdowns (7 use cases)
1. Override consumed during outage (single-use constraint)
2. Temporal false positive in monorepo (fingerprint collision)
3. Category correction after shipping (past verdicts unchanged)
4. Engine health transient failure (no auto-retry)
5. Override expires during approval chain (warning window insufficient)
6. Category weight review missed (no enforcement)
7. Verdict history discontinuity (weight version not tracked)

### Breakdown Signals (7 metrics)
1. Temporal store growth rate
2. Override expiry rate
3. Category assignment review rate
4. Engine health failure rate
5. Category weight staleness
6. Verdict history discontinuities
7. Audit trail conflicts

---

## CONCLUSION

**The system has clear authority gaps and reversibility failures that must be addressed before enforcement.**

**Highest Risk**:
- Temporal escalation (irreversible, false positives block shipping)
- Engine health (reversal cost equals enforcement cost)
- Past verdict impact (category/weight changes don't propagate)

**Before enforcement can be activated**:
1. ✅ Add override revocation API
2. ✅ Add temporal de-escalation mechanism
3. ✅ Add category assignment versioning
4. ✅ Add weight version to verdicts
5. ⚠️ Consider: Auto-retry for engine health timeouts
6. ⚠️ Consider: Override extension API without full re-approval

**These gaps exist by design (optimistic defaults, fail-safe choices), but make the system unsuitable for enforcement without reversibility guarantees.**

---

*Generated: 2026-02-01*
*Analysis Depth: Comprehensive (all primitives, all stages, all use cases)*
*Status: Pre-enforcement validation*
