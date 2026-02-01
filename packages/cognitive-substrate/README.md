# @truthcore/cognitive-substrate

> Shared cognitive substrate for truth representation, belief formation, and decision governance

[![TypeScript](https://img.shields.io/badge/TypeScript-5.3-blue)](https://www.typescriptlang.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](./LICENSE)

## Overview

The Cognitive Substrate is a foundational engine-level architecture that introduces truth representation, belief formation, semantic versioning, decision governance, and economic reasoning as first-class primitives. It is designed to be adopted across multiple applications **without forcing activation**.

**Design Philosophy:** This is a spinal cord, not a brain. It provides infrastructure for reasoning, not reasoning itself.

### Key Characteristics

- **Opt-in by default:** All features are feature-flagged; default mode is observe-only
- **Zero-overhead when disabled:** <1ms runtime cost for inactive features
- **Non-breaking:** Existing builds, flows, and contracts remain unchanged
- **Deterministic:** All operations support replay and inspection
- **Signal-based:** Emits graded signals and reports, never hard failures

## Installation

```bash
npm install @truthcore/cognitive-substrate
```

## Quick Start

```typescript
import { SubstrateRuntime, OBSERVE_ONLY_FLAGS, EvidenceType } from '@truthcore/cognitive-substrate';

// Create runtime with observe-only mode (safe, non-blocking)
const runtime = new SubstrateRuntime({
  name: 'my-app',
  flags: OBSERVE_ONLY_FLAGS
});

// Record evidence
const evidence = runtime.recordEvidence({
  evidenceType: EvidenceType.RAW,
  content: { tests: 'all passed' },
  source: 'test-runner'
});

// Create assertion
const assertion = runtime.recordAssertion({
  claim: 'System is ready',
  evidenceIds: [evidence.evidenceId],
  source: 'readiness-engine'
});

// Form belief with confidence
const belief = runtime.formBelief({
  assertionId: assertion.assertionId,
  confidence: 0.9,
  decayRate: 0.01 // Confidence decays over time
});

// Generate report
const report = runtime.generateMarkdownReport('org-id', 30);
console.log(report);
```

## Core Primitives

### 1. Evidence

Raw or derived data that supports assertions.

```typescript
const evidence = createEvidence({
  evidenceType: EvidenceType.DERIVED,
  content: { coverage: 0.85 },
  source: 'coverage-tool',
  validityPeriod: 3600 // seconds
});
```

### 2. Assertion

A claim the system believes to be true, backed by evidence.

```typescript
const assertion = createAssertion({
  claim: 'Code coverage is above threshold',
  evidenceIds: [evidence.evidenceId],
  source: 'quality-engine',
  transformation: 'aggregated coverage metrics'
});
```

### 3. Belief

An assertion with confidence, temporal validity, and decay characteristics.

```typescript
const belief = createBelief({
  assertionId: assertion.assertionId,
  confidence: 0.85, // [0.0, 1.0]
  decayRate: 0.02, // confidence loss per day
  validityUntil: null // or ISO 8601 timestamp
});

// Confidence decays over time
const currentConf = currentConfidence(belief); // considers time-based decay
```

### 4. MeaningVersion

Semantic versioning of what a concept *means*, separate from schema versions.

```typescript
const meaning = createMeaningVersion({
  meaningId: 'deployment.success',
  version: '2.0.0',
  definition: 'Deployment succeeded AND health checks passed',
  computation: 'deploy_status == "ok" && health_check_status == "healthy"'
});
```

### 5. Decision

An action taken by the system or a human, with governance metadata.

```typescript
const decision = createDecision({
  decisionType: DecisionType.SYSTEM,
  action: 'approve',
  rationale: ['High confidence', 'All checks passed'],
  beliefIds: [belief.beliefId]
});
```

### 6. EconomicSignal

Cost, risk, or value indicators that influence decisions.

```typescript
const signal = createEconomicSignal({
  signalType: EconomicSignalType.COST,
  amount: 150.0,
  unit: 'USD',
  source: 'billing-api',
  appliesTo: 'deployment-123'
});
```

## Architecture Layers

```
┌─────────────────────────────────────────────────────────┐
│  LEARNING LAYER (observe-only)                          │
│  • Pattern detection • Stage-gate • Mismatch warnings   │
├─────────────────────────────────────────────────────────┤
│  ECONOMIC LAYER                                         │
│  • Signals • Invariants • Budget tracking               │
├─────────────────────────────────────────────────────────┤
│  GOVERNANCE LAYER                                       │
│  • Human overrides • Authority • Reconciliation         │
├─────────────────────────────────────────────────────────┤
│  GRAPH LAYER                                            │
│  • Assertion graph • Belief engine • Contradictions     │
├─────────────────────────────────────────────────────────┤
│  PRIMITIVES LAYER                                       │
│  • 7 core abstractions • Serializable • Versioned       │
└─────────────────────────────────────────────────────────┘
```

## Feature Flags

### Default (Dormant)

```typescript
import { DEFAULT_FLAGS } from '@truthcore/cognitive-substrate';

// All features OFF, minimal telemetry only
const runtime = new SubstrateRuntime({
  name: 'app',
  flags: DEFAULT_FLAGS
});
```

### Observe-Only Mode (Recommended)

```typescript
import { OBSERVE_ONLY_FLAGS } from '@truthcore/cognitive-substrate';

// Full tracking, no enforcement, all reports
const runtime = new SubstrateRuntime({
  name: 'app',
  flags: OBSERVE_ONLY_FLAGS
});
```

### Custom Configuration

```typescript
import { createFlags, EnforcementMode } from '@truthcore/cognitive-substrate';

const flags = createFlags({
  enabled: true,
  assertionGraphEnabled: true,
  beliefEngineEnabled: true,
  contradictionDetection: true,
  humanGovernance: false,
  economicSignals: false,
  patternDetection: true,
  enforcementMode: EnforcementMode.OBSERVE
});
```

## Advanced Features

### Belief Composition

Combine multiple beliefs about the same assertion:

```typescript
// Multiple sources assert "deployment is ready" with different confidence
const composed = runtime.composeBeliefsForAssertion(
  assertionId,
  CompositionStrategy.WEIGHTED_AVERAGE
);
```

**Available strategies:**
- `AVERAGE` - Simple average
- `MAX` - Most optimistic
- `MIN` - Most conservative
- `WEIGHTED_AVERAGE` - Inverse-variance weighting (default)
- `BAYESIAN` - Bayesian update chain

### Contradiction Detection

```typescript
// Detect conflicting assertions
runtime.detectContradictions();

// Detect semantic drift across meaning versions
runtime.detectSemanticDrift(meaningVersions);

// Detect policy conflicts
runtime.detectPolicyConflicts(policies);
```

### Human Overrides

```typescript
const override = runtime.createHumanOverride(
  originalDecision,
  overrideDecision,
  {
    actor: 'alice@example.com',
    scope: 'deployment',
    validUntil: null,
    requiresRenewal: true
  },
  {
    scopeType: ScopeType.SINGLE_DECISION,
    target: 'deploy-123',
    constraints: {}
  },
  'Urgent hotfix required',
  expiresAt // ISO 8601, REQUIRED - no permanent overrides
);
```

### Economic Influence

```typescript
// Economic signals adjust belief confidence
const signals = [costSignal, riskSignal];
const influenced = runtime.influenceBeliefWithEconomics(belief, signals);

// Confidence reduced due to high cost/risk
console.log(`Original: ${belief.confidence}, Influenced: ${influenced.confidence}`);
```

### Pattern Detection

```typescript
// Detect organizational usage patterns (observe-only)
const patterns = runtime.detectPatterns('org-id', 30);

for (const pattern of patterns) {
  console.log(`Pattern: ${pattern.patternType}`);
  console.log(`Frequency: ${pattern.frequency}`);
  console.log(`Confidence: ${pattern.confidence}`);
}
```

### Stage-Gate Detection

```typescript
// Automatically detect organizational maturity stage
const stageGate = runtime.detectStageGate(
  {
    teamSize: 25,
    policyCount: 12,
    overrideRate: 0.15,
    deployFrequency: 3,
    avgDecisionTime: 120
  },
  policies,
  decisions
);

console.log(`Detected stage: ${stageGate.stage}`); // EARLY, SCALING, or MATURE
console.log(`Confidence: ${stageGate.confidence}`);
```

## Reports

### Markdown Report

```typescript
const report = runtime.generateMarkdownReport('org-id', 30);
```

Output:
```markdown
# Cognitive Substrate Report

**Generated:** 2026-02-01T12:00:00Z
**Organization:** org-id
**Period:** Last 30 days

## Belief Health
- Total beliefs: 1,245
- High confidence (>0.8): 892 (71.6%)
- Low confidence (<0.5): 23 (1.8%)
- Average confidence: 0.82

## Contradictions
- Total detected: 12
- Resolved: 8
- Unresolved: 4

## Human Overrides
- Total overrides: 56
- Active: 12
- Expired: 44
- **Recommendation:** Consider adjusting policy thresholds

## Economic Signals
- Total cost tracked: $12,450.00
- Average cost per decision: $89.00
- Budget pressure: MEDIUM
```

### JSON Report

```typescript
const report = runtime.generateJSONReport('org-id', 30);
const parsed = JSON.parse(report);
```

## Performance

### Zero-Cost Abstraction

When disabled, overhead is <1ms per operation:

```typescript
const disabled = new SubstrateRuntime(DEFAULT_FLAGS);

// 1000 operations in <10ms
for (let i = 0; i < 1000; i++) {
  disabled.recordAssertion({ ... }); // Immediate return
}
```

### Enabled Mode

Typical overhead: <10ms per operation with full tracking.

## Testing

```bash
npm test                # Run all tests
npm run test:coverage   # Coverage report
npm run test:watch      # Watch mode
```

## TypeScript Support

Fully typed with strict mode:

```typescript
import type {
  Assertion,
  Belief,
  Decision,
  EconomicSignal,
  Contradiction,
  SubstrateConfig
} from '@truthcore/cognitive-substrate';
```

## Examples

See `examples/` directory for:
- `basic-usage.ts` - Getting started
- `advanced-patterns.ts` - Complex workflows
- `integration-example.ts` - Integrating with existing systems

## Architecture Documentation

For comprehensive design documentation, see:
- `COGNITIVE_SUBSTRATE_ARCHITECTURE.md` - Full specification
- `COGNITIVE_SUBSTRATE_SUMMARY.md` - Quick reference

## License

MIT © TruthCore Team

## Contributing

Contributions welcome! Please read CONTRIBUTING.md first.

## Support

- Issues: https://github.com/truthcore/truthcore/issues
- Docs: https://truthcore.dev/docs/cognitive-substrate
