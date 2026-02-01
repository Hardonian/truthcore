# TruthCore Spine Quick Reference
**For Engineers and Operators**

---

## What is TruthCore Spine?

A **read-only, consultative truth system** that:
- Remembers what the system believes and why
- Explains its reasoning when you ask
- Detects contradictions (but doesn't resolve them)
- Never enforces, blocks, or modifies behavior

**Key principle:** TruthCore explains; you decide.

---

## Quick Start (5 minutes)

### 1. Enable TruthCore Spine
```bash
# In your truthcore.config.yaml
spine:
  enabled: true
  assertions: true
  beliefs: true
  queries_enabled: true
```

### 2. Query a Belief
```bash
# Why does the system believe something?
truthctl spine why assertion_abc123

# Show me the evidence
truthctl spine evidence assertion_abc123

# What did we believe last week?
truthctl spine history assertion_abc123 --since 2026-01-25
```

### 3. Check for Contradictions
```bash
# Are there conflicting beliefs?
truthctl spine contradicts --severity high
```

---

## The 7 Query Types

| Question | Command | Use When |
|----------|---------|----------|
| Why is this believed? | `truthctl spine why <id>` | Debugging a decision |
| What evidence supports it? | `truthctl spine evidence <id>` | Verifying confidence |
| When did belief change? | `truthctl spine history <id>` | Understanding drift |
| Which meaning version? | `truthctl spine meaning <concept>` | Semantic drift |
| Who overrode this? | `truthctl spine override <id>` | Governance review |
| What does this depend on? | `truthctl spine dependencies <id>` | Impact analysis |
| What would invalidate this? | `truthctl spine invalidate <id>` | Risk assessment |

---

## Common Use Cases

### Scenario 1: Debugging a FAIL Verdict
```bash
# The system said NO_SHIP. Why?
truthctl spine why assertion_deployment_123

# Output shows:
# - Confidence: 0.72 (below 0.80 threshold)
# - Evidence: 3 HIGH findings, 1 BLOCKER
# - History: Confidence dropped from 0.91 yesterday
# - Dependencies: Security scan finding abc456

# Check the security finding
truthctl spine evidence assertion_security_456
```

### Scenario 2: Understanding an Override
```bash
# Someone shipped despite NO_SHIP. Who?
truthctl spine override decision_deployment_123

# Output shows:
# - Actor: user@example.com
# - Authority: team_lead
# - Scope: deployment_123 only
# - Expires: 2026-02-08 (7 days)
# - Rationale: "urgent hotfix, risk accepted"
```

### Scenario 3: Detecting Semantic Drift
```bash
# What does "deployment_ready" mean?
truthctl spine meaning deployment_ready

# Output shows:
# - Current version: 2.1.0
# - Definition: "score >= 90 AND all reviews complete"
# - Previous version (1.0.0): "score >= 90"
# - Changed: 2026-01-15

# Check for old versions in use
truthctl spine contradicts --type semantic_drift
```

### Scenario 4: Pre-Deploy Impact Analysis
```bash
# What assumptions does this deploy depend on?
truthctl spine dependencies assertion_deployment_123 --recursive

# Output shows dependency graph:
# - deployment_123 depends on:
#   - tests_pass (confidence: 0.95)
#   - security_scan_clean (confidence: 0.89)
#   - coverage_80%+ (confidence: 0.72 ← below threshold)
#     - depends on: coverage_report_789

# What could invalidate this?
truthctl spine invalidate assertion_deployment_123
```

---

## CLI Reference

### Query Commands

```bash
# Explain belief provenance
truthctl spine why <assertion-id> [--format json|md]

# Show supporting/weakening evidence
truthctl spine evidence <assertion-id> [--type raw|derived] [--strength supporting|weakening]

# Belief version history
truthctl spine history <assertion-id> [--since YYYY-MM-DD] [--format json]

# Semantic meaning resolution
truthctl spine meaning <concept> [--version X.Y.Z] [--at ISO8601]

# Override tracking
truthctl spine override <decision-id> [--format json]

# Dependency graph
truthctl spine dependencies <assertion-id> [--recursive] [--depth N]

# Counter-evidence patterns
truthctl spine invalidate <assertion-id> [--format json]
```

### Discovery Commands

```bash
# List detected contradictions
truthctl spine contradicts [--severity blocker|high|medium] [--unresolved]

# Show spine statistics
truthctl spine stats [--since YYYY-MM-DD]

# Health check
truthctl spine health
```

### Admin Commands

```bash
# Compact storage (remove expired evidence)
truthctl spine compact [--dry-run]

# Export data
truthctl spine export --format json --out ./spine-export.json

# Import data (for migration)
truthctl spine import --from ./spine-export.json
```

---

## API Reference

### REST Endpoints

```bash
# Get assertion lineage
GET /spine/v1/assertion/{id}/lineage

# Get belief history
GET /spine/v1/assertion/{id}/history

# Get evidence
GET /spine/v1/assertion/{id}/evidence

# Get meaning version
GET /spine/v1/meaning/{concept}?at={timestamp}

# List contradictions
GET /spine/v1/contradictions?severity={level}

# Query dependencies
POST /spine/v1/query/dependencies
{
  "assertion_ids": ["id1", "id2"],
  "recursive": true,
  "depth": 5
}
```

### Python SDK

```python
from truthcore.spine import SpineClient

# Initialize client
spine = SpineClient()

# Query lineage
lineage = spine.query.lineage(assertion_id="abc123")
print(f"Root evidence: {lineage.root_evidence}")
print(f"Confidence path: {lineage.confidence_computation}")

# Query history
history = spine.query.history(assertion_id="abc123")
for belief in history.beliefs:
    print(f"v{belief.version}: {belief.confidence} at {belief.formed_at}")

# Query meaning
meaning = spine.query.meaning(
    concept="deployment_ready",
    at="2026-02-01T00:00:00Z"
)
print(f"Definition: {meaning.definition}")
```

---

## Output Formats

### Markdown (Default)
```bash
truthctl spine why assertion_123

# Output:
# # Belief: assertion_123
# 
# ## Claim
# "Deployment is ready for production"
# 
# ## Current Confidence
# 0.85 (formed at 2026-02-01T12:00:00Z)
# 
# ## Evidence (3 items)
# 1. [evidence_abc] test_results.json (confidence: +0.30)
# 2. [evidence_def] security_scan.json (confidence: +0.35)
# 3. [evidence_ghi] coverage_report.json (confidence: +0.20)
# 
# ## Dependencies
# - tests_pass (confidence: 0.95)
# - security_clean (confidence: 0.89)
# 
# ## Confidence Computation
# base: 0.50 × evidence_weight: 1.70 = 0.85
```

### JSON (For scripting)
```bash
truthctl spine why assertion_123 --format json

# Output:
# {
#   "assertion_id": "assertion_123",
#   "claim": "Deployment is ready...",
#   "current_belief": {
#     "version": 3,
#     "confidence": 0.85,
#     "formed_at": "2026-02-01T12:00:00Z"
#   },
#   "evidence": [...],
#   "dependencies": [...]
# }
```

---

## Understanding Output

### Confidence Levels

| Value | Meaning | Action |
|-------|---------|--------|
| 0.95-1.0 | Very high confidence | Proceed with confidence |
| 0.80-0.94 | High confidence | Generally safe |
| 0.60-0.79 | Moderate confidence | Review assumptions |
| 0.40-0.59 | Low confidence | Exercise caution |
| 0.0-0.39 | Very low confidence | Consider blocking |

### Contradiction Severity

| Level | Meaning | Example |
|-------|---------|---------|
| BLOCKER | Cannot both be true | "ready" vs "not ready" |
| HIGH | Significant conflict | 85% vs 72% coverage |
| MEDIUM | Possible misalignment | Different thresholds |
| LOW | Minor discrepancy | Cosmetic differences |

### Evidence Types

| Type | Description | TTL |
|------|-------------|-----|
| RAW | Direct input (files, APIs) | 90 days |
| DERIVED | Computed from other evidence | 90 days |
| HUMAN | Explicit human assertion | Permanent |
| EXTERNAL | Third-party system | 90 days |

---

## FAQ

### Q: Can TruthCore block my deployment?
**A:** No. TruthCore is read-only. It explains; you decide.

### Q: Can I delete data from TruthCore?
**A:** Evidence expires after TTL (default 90 days). Assertions and beliefs are permanent for provenance.

### Q: What if TruthCore is wrong?
**A:** TruthCore records what the system believed at a point in time. If evidence was wrong, the belief reflected that. TruthCore tracks belief changes over time.

### Q: How do I fix a contradiction?
**A:** TruthCore detects contradictions but doesn't resolve them. You must:
1. Investigate which assertion is correct
2. Update the evidence or meaning version
3. A new belief will form automatically

### Q: Can I query TruthCore from my CI/CD pipeline?
**A:** Yes. Use the REST API or CLI. Query results are read-only and never block.

### Q: What if TruthCore is slow?
**A:** If queries exceed 100ms, check `truthctl spine stats`. You can:
- Enable caching
- Reduce query depth
- Compact storage

### Q: How do I know if my query is using stale data?
**A:** Check the `timestamp` and `is_stale` fields in output. Evidence shows staleness status.

### Q: Can I export TruthCore data?
**A:** Yes. Use `truthctl spine export`. Data is JSON format and portable.

---

## Troubleshooting

### Issue: "assertion not found"
**Cause:** ID doesn't exist or hasn't been ingested yet
**Fix:** Check the ID. If using Silent Instrumentation, ensure it's enabled and running.

### Issue: "query timeout"
**Cause:** Deep recursion or large graph
**Fix:** Use `--depth` flag to limit depth. Run `truthctl spine compact`.

### Issue: "contradiction detected" warnings
**Cause:** Two assertions conflict
**Fix:** Investigate both assertions. Check meaning versions. Update evidence if needed.

### Issue: Slow queries
**Cause:** Large dataset or complex lineage
**Fix:** 
```bash
# Check stats
truthctl spine stats

# Compact storage
truthctl spine compact

# Limit query depth
truthctl spine why <id> --depth 5
```

---

## Best Practices

### 1. Query Before Acting
When you see an unexpected verdict, query TruthCore first:
```bash
truthctl spine why <assertion-id> --format md
```

### 2. Check Meaning Versions
Before comparing metrics across time, verify meaning:
```bash
truthctl spine meaning <concept> --at <timestamp>
```

### 3. Monitor Contradictions
Weekly check for contradictions:
```bash
truthctl spine contradicts --unresolved --severity high
```

### 4. Document Overrides
When overriding, provide detailed rationale:
```bash
# Override is recorded automatically
# Make sure your rationale explains context
```

### 5. Use Lineage for Impact Analysis
Before making changes, check dependencies:
```bash
truthctl spine dependencies <assertion-id> --recursive
```

---

## Getting Help

- **Documentation:** `truthctl spine --help`
- **Specific command:** `truthctl spine <command> --help`
- **Issues:** Check `truthctl spine health`
- **Logs:** `.truthcore/spine/logs/`

---

**Remember:** TruthCore is your consultative partner. It remembers, explains, and warns. The decision is always yours.
