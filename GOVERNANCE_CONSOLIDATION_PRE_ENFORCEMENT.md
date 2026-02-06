# Pre-Enforcement Governance Consolidation

**Status**: One lever active (Override Expiry Warning), no enforcement
**Purpose**: Determine if the system deserves authority
**Audience**: Humans who must decide whether to trust automation

---

## PART A: Authority Map (Truth of Power)

### Where Decisions Are Actually Made

**Fully Automated (No human in loop)**
- **Severity assignment**: Scanners detect issues → assign LOW/MEDIUM/HIGH/BLOCKER
- **Points calculation**: Formula applies severity × category weight (e.g., SECURITY × 2.0)
- **Temporal escalation**: System bumps severity after 3+ occurrences (LOW → MEDIUM → HIGH)
- **Engine health signals**: CI/CD reports success/failure/timeout per engine
- **Threshold evaluation**: Five sequential checks determine SHIP vs NO_SHIP

*Reality*: These decisions happen every run, invisibly, with no approval gate.

**Human-Initiated (Requires explicit approval)**
- **Override creation**: Tech lead approves exception to threshold (e.g., "allow 10 highs instead of 5")
- **Category weight updates**: Security team reviews organizational values every 90 days
- **Override extension**: Humans must create new override before expiry (no auto-renewal)

*Reality*: These require `approved_by` field, ISO timestamp, and written justification.

**Hybrid (Automated with human review option)**
- **Category assignment**: Scanner assigns category (0.8 confidence) → human can review and confirm (1.0 confidence)
- **Threshold customization**: System provides defaults per mode (PR/MAIN/RELEASE) → teams can customize

*Reality*: Most organizations never review; scanner defaults become de facto policy.

### Where Authority Is Assumed But Not Explicit

1. **Category multipliers** (SECURITY=2.0x, PRIVACY=1.5x) encode organizational values but are rarely reviewed
   - *Assumption*: Initial weights remain correct forever
   - *Reality*: 90-day review required, not enforced

2. **Fingerprint algorithm** (rule_id:file_path:line) determines "sameness" for temporal tracking
   - *Assumption*: Hash collisions are acceptable
   - *Reality*: False positives escalate innocent findings

3. **Scanner confidence** (typically 0.8) determines category assignment weight
   - *Assumption*: 80% is "good enough" to 2x the finding's impact
   - *Reality*: No calibration against actual error rates

4. **Override scope** (e.g., "max_highs: 10") is free text
   - *Assumption*: Humans write clear, parseable scope strings
   - *Reality*: No validation, no schema, no enforcement of conditions list

### Where Authority Is Ambiguous or Contested

**Category Assignment**
- Scanner says "SECURITY" (confidence 0.8)
- Human reviewer says "BUILD" (confidence 1.0)
- System has no conflict resolution: last write wins

**Temporal Escalation vs Override**
- Temporal escalation bumps severity automatically (cannot be overridden)
- Override allows exceeding thresholds for HIGH severity
- If temporal escalation promotes MEDIUM → HIGH, override scope may no longer apply
- *Contested*: Should override intent survive escalation?

**Engine Health Failure**
- Engine reports `ran=False, succeeded=False`
- Tech lead creates override for "max_highs: 10"
- Verdict still degrades to DEGRADED (override ignored)
- *Ambiguous*: Does override cover infrastructure failures?

**Expired Override in Verdict History**
- Override used at T0, expires at T0+24h
- Verdict at T0 said SHIP (override applied)
- At T0+25h, was that verdict legitimate?
- *Contested*: Does expiry invalidate past decisions?

### Where Authority Shifts Over Time or Context

**Progressive Enforcement Modes**
```
Observe → Warn → Enforce
(today)   (next)  (unknown)
```
- *Observe*: System records governance signals, no behavior change
- *Warn*: System emits non-blocking warnings (Override Expiry active now)
- *Enforce*: System blocks actions (not activated)

*Shift*: Authority moves from advisory to controlling without code change (lever activation).

**Override Lifecycle**
```
Created → Valid → Used → Invalid
(Human)   (Time)   (Auto)  (Time)
```
- T0: Human creates override, has authority
- T0 to T+24h: System consumes override if needed
- T+24h: Override expires, authority revoked
- *Shift*: Human authority decays over 24 hours

**Category Weight Review**
```
Day 0-89: Weights trusted
Day 90+:  Weights "overdue for review" (signal only)
```
- *Shift*: Legitimacy erodes over time, but no enforcement

---

## PART B: Right to Be Wrong (Reversibility)

### Core Principle

**Every decision that blocks human action must be cheaper to reverse than to enforce.**

This system does not yet enforce blocking decisions. Before it can:
- Reversal paths must exist for every enforcement
- Reversal must cost less than the original decision
- Reversal must be visible in the audit trail
- No decision may become permanently "correct" simply by aging

### What "Being Wrong" Looks Like Operationally

**Wrong Category Assignment**
- Scanner assigns SECURITY (2.0x multiplier) to a BUILD issue (1.0x)
- Finding accumulates 2x the points it should
- Verdict flips from SHIP to NO_SHIP

*Observable*: Finding ID appears in `category_assignments[]` with `assigned_by="scanner"`, `confidence=0.8`

**Wrong Temporal Escalation**
- Fingerprint collision causes unrelated finding to escalate
- Issue appears 3x in different contexts (dev/staging/prod)
- Severity bumps from MEDIUM to HIGH

*Observable*: Finding appears in `temporal_escalations[]` with occurrence count

**Wrong Override Scope**
- Override says "max_highs: 10" but was intended for specific subsystem
- Unrelated highs consume the override
- Intended usage fails

*Observable*: Override `verdict_id` points to wrong verdict in audit trail

**Wrong Engine Health Signal**
- Engine reports `ran=False` due to timeout (not failure)
- System treats as infrastructure failure
- Verdict degrades to DEGRADED

*Observable*: `EngineHealth.error_message` shows timeout, not logic error

### How Reversals Should Behave

**Scope**: Reversals affect forward decisions only
- Cannot retroactively change verdicts already used for shipping
- Can prevent future verdicts from repeating the mistake
- Example: Correcting category assignment updates confidence to 1.0, future runs use corrected value

**Decay**: Authority to reverse expires over time
- Override reversals only matter before `expires_at` timestamp
- Category weight reversals only affect findings categorized after update
- Temporal escalation reversals require clearing history (nuclear option)

**Notification**: Reversals must be visible
- Category assignment updates: `reviewed=True`, `reviewer="human@example.com"`, `reviewed_at` timestamp
- Override revocation: Create new override with negative scope (not implemented)
- Engine health correction: Re-run with updated health signal

**Cost**: Reversal must be cheaper than enforcement
- ✅ Category review: Read finding, update assignment, save (< 30 seconds)
- ✅ Override extension: Create new override before expiry (< 2 minutes)
- ❌ Temporal escalation: Clear entire temporal store (lose all history)
- ❌ Engine health: Re-run entire CI/CD pipeline (10+ minutes)

### Signals That Reversibility Is Breaking Down

**Temporal Store as Permanent Record**
- Once escalation happens, no reversal path exists
- Clearing store loses ALL history, not just the mistake
- *Signal*: Percentage of findings with `temporal_escalations` > 0

**Override Expiry Without Extension Option**
- If override expires during decision-making, no way to recover
- System only warns at T-24h, T-6h (may miss notification)
- *Signal*: Count of overrides expired < 24h ago still showing in warnings

**Category Assignment Confidence Drift**
- Scanner confidence stays at 0.8 forever
- Human reviews don't improve scanner's future accuracy
- *Signal*: Ratio of scanner-assigned (0.8) vs human-reviewed (1.0) over time

**Audit Trail Without Correction Path**
- All governance records are append-only
- No mechanism to mark entry as "superseded" or "corrected"
- *Signal*: Duplicate entries in `category_assignments[]` for same finding ID

---

## PART C: Never-Automate Boundary

### Decisions That Must Remain Human

**1. Override Approval**
*Why*: Ambiguity + Value Judgment + Irreversible Impact

Deciding to ship despite high-severity findings requires:
- Understanding organizational risk tolerance (context-dependent)
- Weighing urgency vs safety (value judgment)
- Accepting accountability for consequences (ethical)

*Observable*: `Override.approved_by` field, `reason` field required
*Boundary*: System can suggest thresholds were exceeded; only human can say "proceed anyway"

**2. Category Weight Updates**
*Why*: Semantic Instability + Organizational Values

What makes a security issue 2x more important than a build issue changes over time:
- Post-incident: Security weight increases
- Compliance audit: Privacy weight increases
- After outage: Reliability weight increases

*Observable*: `CategoryWeightConfig.reviewed_by`, 90-day review cycle
*Boundary*: System can flag review due; only humans can decide "still appropriate"

**3. Override Extension**
*Why*: Institutional Risk + Value Judgment

Extending an override beyond original 24h requires justifying:
- Why original time estimate was wrong
- Whether issue severity has changed
- Whether organizational context shifted

*Observable*: Creating new override before old one expires (not auto-renewal)
*Boundary*: System can warn at T-24h; only human can decide "extend or expire"

**4. Temporal Escalation Suppression**
*Why*: Ambiguity + False Positive Risk

System cannot distinguish:
- Same issue appearing 3x (legitimate escalation)
- 3 different issues with same fingerprint (false positive)
- Same issue in 3 environments (operational necessity)

*Observable*: `TemporalFinding.occurrence_count`, `escalated=True` flag
*Boundary*: System can escalate; human must review to suppress or confirm

**5. Engine Health Interpretation**
*Why*: Semantic Instability + Infrastructure vs Logic

When engine reports failure, distinguishing:
- Infrastructure timeout (retry, don't block)
- Logic error (fix immediately, block)
- Expected failure (test case, ignore)

*Observable*: `EngineHealth.error_message`, `execution_time_ms`
*Boundary*: System reports facts (ran, succeeded, error); human interprets severity

### Decisions That Must Remain Advisory Only

**1. Governance Warnings (All Types)**
*Why*: Irreversible Impact + Institutional Risk

Currently active: Override Expiry Warning
Designed but inactive: Engine Health Warning, Temporal Escalation Warning

Warnings inform humans of state changes but must never block because:
- False positives would halt development
- Context (urgency, risk) determines appropriate response
- Organizations must learn warning accuracy before enforcing

*Observable*: `GovernanceWarning` in verdict, INFO/WARNING/ERROR levels
*Boundary*: System warns; human decides whether to act

**2. Category Assignment by Scanner**
*Why*: Semantic Instability + False Positive Risk

Scanner confidence is 0.8 (80% accurate), meaning:
- 1 in 5 categories are wrong
- 2.0x multiplier means wrong category = 2x wrong points
- SHIP vs NO_SHIP decision may flip on false assignment

*Observable*: `CategoryAssignment.confidence=0.8`, `assigned_by="scanner"`
*Boundary*: Scanner suggests; human reviews on high-impact findings

### Decisions Requiring Renewed Consent Every Time

**1. Threshold Customization**
*Why*: Value Judgment + Institutional Risk

Changing `max_highs` from 5 to 10 is not a configuration setting—it's a risk decision.

Each increase must be justified:
- For this codebase (not globally)
- At this time (not forever)
- Given current organizational risk tolerance

*Observable*: No mechanism exists yet (thresholds are per-Mode)
*Boundary*: Should require approval like overrides, with expiry

**2. Category Weight Deviation from Baseline**
*Why*: Organizational Values + Semantic Instability

If SECURITY weight changes from 2.0 → 3.0, all past verdicts become incomparable to future verdicts.

Renewal required:
- Every 90 days: Review current weights
- After incidents: Re-evaluate weights
- When adding new category: Justify weight relative to existing

*Observable*: `CategoryWeightConfig.last_reviewed_at`
*Boundary*: Review flag active, enforcement not active

### Precision Notes

**NOT Never-Automate:**
- **Points calculation**: Formula is deterministic, no ambiguity
- **Severity detection**: Scanner accuracy improves with training, not inherently human
- **Fingerprinting**: Hash collisions are engineering problem, not judgment call
- **Threshold evaluation**: Boolean logic (count > limit) is pure computation

**Borderline Cases:**
- **Temporal escalation**: Currently automated, should require human confirmation before enforcement
- **Engine health blocking**: Currently designed for enforcement, should remain advisory until accuracy proven
- **Category multipliers**: Currently static, should require review but not per-use approval

---

## How This Protects Trust Before Enforcement

### The Problem
A system that enforces without earning trust becomes an obstacle to route around.

### The Protection
This consolidation maps three critical questions:

1. **Authority Map**: Where is power actually exercised?
   *Protects*: Reveals hidden assumptions before they become invisible enforcement

2. **Right to Be Wrong**: Can we undo this decision?
   *Protects*: Prevents irreversible automation from blocking humans permanently

3. **Never-Automate Boundary**: What must humans always own?
   *Protects*: Reserves judgment, ambiguity, and values for human decision-makers

### The Test
Before activating enforcement:
- Can we explain who decided what, and why? (Authority Map)
- Can we reverse the decision cheaper than we made it? (Right to Be Wrong)
- Did we automate something that requires human judgment? (Never-Automate Boundary)

If any answer is "no," enforcement will damage trust.

### Current State
- **One lever active**: Override Expiry Warnings (observe mode)
- **No enforcement**: All signals are informational
- **Reversibility**: Untested (no decisions to reverse yet)
- **Authority**: Clearly mapped, but gaps identified

**This artifact exists to prevent enforcement from activating before the system deserves it.**

---

*Generated: 2026-02-01*
*Governance Version: v3.0*
*Enforcement Status: OBSERVE*
