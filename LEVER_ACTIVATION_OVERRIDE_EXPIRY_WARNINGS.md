# Lever Activation: Override Expiry Warnings

**Status:** Design Complete — Ready for Implementation
**Lever:** Override Expiry Warnings
**Mode:** Non-Blocking, Non-Authoritative Warning Only
**Date:** 2026-02-01
**Governance Version:** v3.0

---

## 1. LEVER SELECTION & JUSTIFICATION

### Selected Lever
**Override Expiry Warnings** — Proactive notifications when governance overrides are approaching expiration or have expired.

### Why This Lever Wins

**Evidence from Reality Capture Report:**
- Section 2.4: *"The 'override' concept exists in design but has no operational surface"*
- Question #7: *"How often does the system say NO_SHIP and something ships anyway?"*
- The report identified that overrides existed as threshold numbers but lacked governance flow

**Current State:**
- Override class fully implemented (severity.py:154-248) with:
  - `is_valid()`, `is_expired()` methods
  - `expires_at`, `approved_by`, `reason` tracking
  - Usage marking and verdict linking
- Overrides are registered and consumed in aggregator.py:536-561
- BUT: No proactive warnings before expiration

**Selection Criteria Scores:**

| Criterion | Score | Rationale |
|-----------|-------|-----------|
| **Insight per unit complexity** | ✅✅✅✅✅ | Trivial time check → high-value signal |
| **Low false positive risk** | ✅✅✅✅✅ | Deterministic (time-based), no heuristics |
| **Minimal domain coupling** | ✅✅✅✅✅ | Overrides are pure governance objects |
| **Clear standalone value** | ✅✅✅✅ | Actionable even if never escalated |
| **Evidence of need** | ✅✅✅✅✅ | Explicitly called out in Reality Capture |

**Rejected Alternatives:**

- **Temporal Escalation Warnings:** Higher complexity (fingerprinting), more false positives, already surfaces via escalation
- **Category Weight Review Warnings:** Organizational process coupling, lower operational urgency
- **Engine Health Warnings:** Already implemented via `degradation_reasons` (aggregator.py:401-405)
- **Policy Conflict Warnings:** Not yet observable in reality (no evidence of need)

---

## 2. WARNING SIGNAL DEFINITION

### Trigger Conditions

Warnings are emitted when:

1. **Imminent Expiry (24h window):**
   - Override expires within 24 hours
   - Level: `INFO`
   - Message: *"Override {override_id} expires in {hours}h {minutes}m (approved by {approver})"*

2. **Critical Expiry (6h window):**
   - Override expires within 6 hours
   - Level: `WARNING`
   - Message: *"Override {override_id} expires in {hours}h {minutes}m — consider extending (approved by {approver})"*

3. **Expired (0-24h post-expiry):**
   - Override expired less than 24 hours ago
   - Level: `ERROR` (non-blocking)
   - Message: *"Override {override_id} expired {hours}h {minutes}m ago (approved by {approver})"*

### Signal Structure

```python
@dataclass
class GovernanceWarning:
    """Non-blocking governance warning."""

    warning_id: str             # Unique ID for deduplication
    level: str                  # INFO | WARNING | ERROR
    category: str               # "override_expiry"
    message: str                # Human-readable explanation
    timestamp: str              # ISO8601 when warning was generated

    # Context (what changed, not what to do)
    context: dict[str, Any]     # {
                                #   "override_id": str,
                                #   "approved_by": str,
                                #   "scope": str,
                                #   "expires_at": str,
                                #   "time_until_expiry_seconds": int,
                                #   "is_expired": bool,
                                # }

    # Suppression (optional)
    suppressed: bool = False
    suppressed_reason: str | None = None
```

### Warning Content Philosophy

Warnings explain **what changed**, not **what to do**:

✅ Good: *"Override max_highs:10 expires in 4h 23m"*
❌ Bad: *"You should extend the override now"*

✅ Good: *"Override approved by alice@example.com expired 2h ago"*
❌ Bad: *"Your override is invalid, fix it immediately"*

The warning provides information. Humans decide action.

---

## 3. ACTIVATION SCOPE

### Where Warnings Appear

1. **VerdictResult.governance_warnings** (new field)
   - Type: `list[GovernanceWarning]`
   - Added to VerdictResult dataclass (verdict/models.py:276)
   - Serialized in `to_dict()` under `"governance"."warnings"`

2. **Markdown Reports** (optional, if verbose)
   - New section: `## Governance Warnings`
   - Only shown if warnings exist
   - Sorted by level (ERROR → WARNING → INFO)

3. **JSON Output**
   - Included in verdict JSON at `verdict.governance.warnings[]`
   - Parseable by CI/CD systems

4. **Console Output** (stderr, if verbose mode enabled)
   - Not implemented in initial activation
   - Reserved for future opt-in telemetry

### Who Can See Warnings

**Read Access:**
- Anyone with access to VerdictResult (JSON or Markdown)
- CI/CD systems parsing verdict output
- Developers viewing reports

**No Special Permissions Required:**
- Warnings are informational, not access-controlled
- Override metadata is already in verdict output

### Rate Limiting

**Per-Override, Per-Run:**
- Maximum one warning per override per aggregation run
- Deduplication by `warning_id = f"override_expiry_{override.override_id}_{run_id}"`

**No Cross-Run Persistence:**
- Warnings are stateless
- Each aggregation run re-evaluates all registered overrides
- No warning history accumulation

### Suppression Mechanism

**Automatic Suppression (built-in):**
- Overrides expired >24 hours ago: no warning (natural cleanup)
- Overrides not yet registered: no warning (not in scope)

**Manual Suppression (future):**
- Not implemented in initial activation
- Reserved: `TRUTHCORE_SUPPRESS_WARNINGS=override_expiry` env var

### Explicit Exclusions (What NOT to Warn About)

1. **Overrides that expired >24 hours ago**
   - Rationale: Already inactive, no action needed, reduces noise

2. **Overrides that were never used and expired**
   - Rationale: Natural cleanup, not urgent

3. **Overrides in future runs where verdict doesn't use them**
   - Rationale: Only warn when override is in active context

4. **Valid overrides with >24 hours remaining**
   - Rationale: No urgency, reduces noise

---

## 4. IMPLEMENTATION DESIGN

### Code Changes (Minimal)

**File:** `src/truthcore/severity.py`
```python
# Add GovernanceWarning dataclass (after Override class)
@dataclass
class GovernanceWarning:
    """Non-blocking governance warning for observability."""

    warning_id: str
    level: str  # INFO | WARNING | ERROR
    category: str  # override_expiry | category_review | temporal_drift
    message: str
    timestamp: str
    context: dict[str, Any]
    suppressed: bool = False
    suppressed_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "warning_id": self.warning_id,
            "level": self.level,
            "category": self.category,
            "message": self.message,
            "timestamp": self.timestamp,
            "context": self.context,
            "suppressed": self.suppressed,
            "suppressed_reason": self.suppressed_reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GovernanceWarning:
        """Create from dictionary."""
        return cls(
            warning_id=data["warning_id"],
            level=data["level"],
            category=data["category"],
            message=data["message"],
            timestamp=data["timestamp"],
            context=data["context"],
            suppressed=data.get("suppressed", False),
            suppressed_reason=data.get("suppressed_reason"),
        )
```

**File:** `src/truthcore/verdict/models.py`
```python
# Add to VerdictResult dataclass (after line 319)
# Governance warnings (non-blocking)
governance_warnings: list[GovernanceWarning] = field(default_factory=list)

# Update to_dict() method (after line 357)
"governance": {
    "overrides_applied": [o.to_dict() for o in self.overrides_applied],
    "temporal_escalations": [t.to_dict() for t in self.temporal_escalations],
    "category_assignments": [c.to_dict() for c in self.category_assignments],
    "warnings": [w.to_dict() for w in self.governance_warnings],  # NEW
},
```

**File:** `src/truthcore/verdict/aggregator.py`
```python
# Add method to VerdictAggregator class (after line 256)
def _check_override_expiry_warnings(self, run_id: str | None) -> list[GovernanceWarning]:
    """Check for override expiry warnings (non-blocking).

    This is the ONLY active governance lever in v3.1.

    Returns:
        List of governance warnings (may be empty)
    """
    from truthcore.severity import GovernanceWarning

    warnings = []
    now = datetime.now(UTC)

    for override in self.overrides:
        try:
            # Parse expiry time
            expires_dt = datetime.fromisoformat(override.expires_at.replace("Z", "+00:00"))
            time_until_expiry = expires_dt - now
            seconds_remaining = time_until_expiry.total_seconds()

            # Skip if expired >24h ago (natural cleanup)
            if seconds_remaining < -86400:
                continue

            # Determine warning level and message
            level = None
            message = None

            if seconds_remaining < 0:
                # Expired (within last 24h)
                level = "ERROR"
                hours_ago = abs(int(seconds_remaining // 3600))
                minutes_ago = abs(int((seconds_remaining % 3600) // 60))
                message = (
                    f"Override {override.override_id} expired {hours_ago}h {minutes_ago}m ago "
                    f"(approved by {override.approved_by})"
                )
            elif seconds_remaining < 21600:  # 6 hours
                # Critical window
                level = "WARNING"
                hours = int(seconds_remaining // 3600)
                minutes = int((seconds_remaining % 3600) // 60)
                message = (
                    f"Override {override.override_id} expires in {hours}h {minutes}m — "
                    f"consider extending (approved by {override.approved_by})"
                )
            elif seconds_remaining < 86400:  # 24 hours
                # Imminent window
                level = "INFO"
                hours = int(seconds_remaining // 3600)
                minutes = int((seconds_remaining % 3600) // 60)
                message = (
                    f"Override {override.override_id} expires in {hours}h {minutes}m "
                    f"(approved by {override.approved_by})"
                )
            else:
                # No warning needed (>24h remaining)
                continue

            # Create warning
            warning = GovernanceWarning(
                warning_id=f"override_expiry_{override.override_id}_{run_id or 'unknown'}",
                level=level,
                category="override_expiry",
                message=message,
                timestamp=now.isoformat(),
                context={
                    "override_id": override.override_id,
                    "approved_by": override.approved_by,
                    "scope": override.scope,
                    "expires_at": override.expires_at,
                    "time_until_expiry_seconds": int(seconds_remaining),
                    "is_expired": seconds_remaining < 0,
                    "reason": override.reason,
                },
            )
            warnings.append(warning)

        except (ValueError, AttributeError):
            # Fail silent — if we can't parse, don't warn
            continue

    return warnings

# Update aggregate() method (before line 491, after temporal escalations)
# Check for governance warnings (non-blocking)
result.governance_warnings = self._check_override_expiry_warnings(run_id)
```

### Feature Flag

**Environment Variable:**
```bash
TRUTHCORE_ENABLE_OVERRIDE_EXPIRY_WARNINGS=true
```

**Default:** `false` (opt-in)

**Activation:**
```python
# In aggregator.py:aggregate() method
enable_warnings = os.environ.get("TRUTHCORE_ENABLE_OVERRIDE_EXPIRY_WARNINGS", "false").lower() == "true"

if enable_warnings:
    result.governance_warnings = self._check_override_expiry_warnings(run_id)
```

### Failure Behavior

**Fail Silent:**
- If datetime parsing fails → skip warning
- If override object is malformed → skip warning
- If exception during warning generation → log to stderr (optional), continue verdict

**Never:**
- Block verdict computation
- Mutate verdict status
- Raise exceptions to caller
- Retry or persist warnings

**Guarantees:**
- Warnings are best-effort only
- Verdict correctness is unaffected
- System degrades gracefully

---

## 5. ACTIVATION PLAN

### Scope

**One Application Only:**
- VerdictAggregator in `src/truthcore/verdict/aggregator.py`

**One Execution Path Only:**
- During `aggregate()` method execution
- After findings are processed, before verdict is finalized

**One Surface:**
- Override objects registered via `register_override()`

### Activation Steps

1. **Add GovernanceWarning dataclass** (severity.py)
   - No behavioral changes
   - Pure data structure

2. **Add governance_warnings field** (verdict/models.py)
   - Default: empty list
   - Backward compatible (field has default)

3. **Add _check_override_expiry_warnings() method** (aggregator.py)
   - Private method, no external callers
   - Returns empty list if feature flag disabled

4. **Integrate into aggregate() method** (aggregator.py)
   - Single line: `result.governance_warnings = ...`
   - Guarded by feature flag check

5. **Update tests** (test_verdict_governance.py)
   - Add test for override expiry warnings
   - Verify warnings don't affect verdict

### Rollback Condition

**Immediate Rollback If:**
- Warnings cause verdict computation to fail (exception)
- Warnings mutate verdict status
- Warning generation takes >100ms per override
- False positive rate >5% (warnings for valid overrides >24h out)

**Rollback Procedure:**
1. Set `TRUTHCORE_ENABLE_OVERRIDE_EXPIRY_WARNINGS=false`
2. No code changes required (feature flag controls activation)
3. Warnings field remains in VerdictResult (backward compatible) but stays empty

### Success Criteria

**Signal Quality (Not Behavior Change):**

1. **Accuracy:** 100% of warnings correspond to real expiry events
2. **Timeliness:** Warnings appear within 5 minutes of threshold crossing
3. **Completeness:** All registered overrides within warning windows are detected
4. **Non-interference:** Zero impact on verdict computation time (<1ms overhead)

**Not Success Criteria:**
- Number of warnings generated (could be zero)
- Human response to warnings (observe-only)
- Reduction in expired overrides (not measuring behavior change)

**Measurement Window:** 7 days

**Evaluation:**
- Review 20 random verdict runs with registered overrides
- Verify warnings match manual calculation
- Verify no performance degradation

---

## 6. EXPECTED BENEFITS

### Immediate (Week 1)

1. **Override Visibility:**
   - Humans see when temporary permissions expire
   - Proactive notice enables extension decisions
   - Reduces "surprise" failures when overrides lapse

2. **Governance Observability:**
   - First signal from governance layer to operational surface
   - Validates warning infrastructure for future levers
   - Establishes pattern for non-blocking signals

3. **Trust Building:**
   - System provides information without control
   - Demonstrates usefulness before authority
   - Low-risk demonstration of governance value

### Medium-Term (Month 1)

1. **Operational Learning:**
   - How often are overrides extended vs. allowed to expire?
   - What is the typical override lifespan?
   - Which approvers use short vs. long expiry windows?

2. **Signal Quality Data:**
   - False positive rate (should be ~0%)
   - Warning lead time effectiveness
   - Human response patterns (if instrumented)

3. **Governance Refinement:**
   - Informed decisions about default expiry durations
   - Evidence for override extension policies
   - Baseline for future override governance

### Long-Term (Quarter 1)

1. **Platform for Additional Levers:**
   - Reuse GovernanceWarning infrastructure
   - Add: temporal escalation warnings, category review warnings
   - Graduated activation based on proven value

2. **Organizational Awareness:**
   - Governance becomes visible and normalized
   - Reduces resistance to future enforcement
   - Builds institutional knowledge of override lifecycle

---

## 7. EXPLICIT RISKS & ACCEPTANCE

### Risks (And Why They're Acceptable)

1. **Warning Fatigue (Low Risk)**
   - **Risk:** Too many warnings, humans ignore them
   - **Why Acceptable:**
     - Warnings only for overrides within 24h of expiry
     - Typical deployment: 0-3 active overrides at once
     - Expected: 0-1 warnings per verdict run
   - **Mitigation:** Explicit exclusion of far-future and far-past overrides

2. **Datetime Parsing Failures (Negligible Risk)**
   - **Risk:** Malformed timestamps cause crashes
   - **Why Acceptable:**
     - Fail-silent behavior (try-except, continue)
     - Overrides are created by system (well-formed)
     - No impact on verdict correctness
   - **Mitigation:** Defensive parsing with fallback

3. **False Positives on Timezone Edge Cases (Low Risk)**
   - **Risk:** Warning says "6 hours" but expires in 5h 58m
   - **Why Acceptable:**
     - All times in UTC (normalized)
     - Threshold windows are generous (6h, 24h)
     - 2-minute variance is operationally irrelevant
   - **Mitigation:** UTC-only, no local timezone conversion

4. **Performance Overhead (Negligible Risk)**
   - **Risk:** Checking every override slows down verdict
   - **Why Acceptable:**
     - Typical: 0-5 overrides per verdict
     - Per-override cost: <1ms (datetime comparison)
     - Total overhead: <5ms per verdict
   - **Mitigation:** Rollback if >100ms per override observed

5. **Confusion About Warning vs. Error (Medium Risk)**
   - **Risk:** Humans see "ERROR" level and think verdict failed
   - **Why Acceptable:**
     - Warning category clearly states "governance" not "verdict"
     - Documentation emphasizes non-blocking nature
     - Markdown output has separate "Governance Warnings" section
   - **Mitigation:** Clear messaging, separate section in reports

### Unacceptable Risks (Guarded Against)

❌ **Warnings mutate verdict status** → Prevented by: warnings added AFTER verdict determined
❌ **Warning failures crash aggregation** → Prevented by: try-except, fail-silent
❌ **Warnings change finding scores** → Prevented by: warnings operate on result object only
❌ **Warnings persist across runs** → Prevented by: stateless, per-run generation

---

## 8. WHAT REMAINS OBSERVE-ONLY

### Still in Observe-Only Mode

1. **Temporal Escalation Warnings**
   - Escalation happens (aggregator.py:191-207)
   - BUT: No proactive warning before escalation
   - Future lever candidate

2. **Category Weight Review Warnings**
   - `CategoryWeightConfig.is_review_overdue()` exists
   - BUT: No warnings emitted
   - Future lever candidate

3. **Engine Health Degradation**
   - Already surfaces via `degradation_reasons`
   - NOT adding new warnings (already visible)

4. **Category Assignment Auditing**
   - Audit trail captured (CategoryAssignment objects)
   - BUT: No warnings for low-confidence assignments
   - Future lever candidate

5. **Finding Contradiction Detection**
   - Not yet implemented (no infrastructure)
   - Future lever, requires semantic layer

### Governance Mechanisms Active But Not Warning

- **Unified Severity Enum:** Active (type safety)
- **Override Validation:** Active (is_valid() checks during registration)
- **Temporal Tracking:** Active (occurrence counting)
- **Engine Health Checks:** Active (affects verdict via degradation)
- **Category Weights:** Active (applied to scoring)

**Only Override Expiry Warnings cross from observe to warn.**

---

## 9. IMPLEMENTATION CHECKLIST

- [ ] Add `GovernanceWarning` dataclass to severity.py
- [ ] Add `governance_warnings` field to VerdictResult
- [ ] Update VerdictResult.to_dict() to include warnings
- [ ] Add `_check_override_expiry_warnings()` to VerdictAggregator
- [ ] Integrate warning check into aggregate() with feature flag
- [ ] Add unit tests for warning generation
- [ ] Add unit tests for warning suppression logic
- [ ] Add integration test with expired override
- [ ] Update VerdictResult.to_markdown() to include warnings section
- [ ] Document feature flag in README
- [ ] Create activation runbook (this document)

---

## 10. DEACTIVATION CRITERIA

**Deactivate If (Any):**

1. **Performance:** Warning generation adds >100ms per verdict
2. **Correctness:** Warning generation causes any verdict failure
3. **Signal Quality:** False positive rate >5%
4. **Operational Noise:** Warnings flagged as "too noisy" by >2 teams

**Deactivation Is Success If:**
- We learn that override expiry is not operationally relevant
- Evidence shows warnings provide no value
- System evolves beyond needing temporary overrides

**Deactivation ≠ Failure.** This is an experiment to earn trust.

---

## SUMMARY

**Lever:** Override Expiry Warnings
**Why:** Highest insight/complexity ratio, evidence from Reality Capture, zero coupling
**How:** Non-blocking GovernanceWarning objects in VerdictResult
**When:** During aggregate(), guarded by feature flag
**Risk:** Minimal (fail-silent, stateless, <5ms overhead)
**Value:** Proactive override visibility, trust building, governance platform

**This step exists to earn trust, not power.**

---

*Document Version: 1.0*
*Author: Principal Systems Architect*
*Review Status: Ready for Implementation*
