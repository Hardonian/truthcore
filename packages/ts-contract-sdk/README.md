# @truth-core/contract-sdk

TypeScript SDK for truth-core contracts. Provides typed models and validators for Verdict and Readiness artifacts with full backward compatibility.

## Features

- **Full Type Safety**: Complete TypeScript definitions for truth-core artifact contracts
- **Version Compatibility**: Supports both v1 and v2 verdict formats
- **Runtime Validation**: Helper functions to load and validate verdict artifacts
- **Analysis Utilities**: Filter, sort, and summarize findings
- **Zero Dependencies**: Lightweight with no runtime dependencies
- **ESM + CJS**: Works with both module systems

## Installation

```bash
npm install @truth-core/contract-sdk
# or
yarn add @truth-core/contract-sdk
# or
pnpm add @truth-core/contract-sdk
```

## Quick Start

```typescript
import { loadVerdict, topFindings, filterBySeverity, summarizeTrend } from "@truth-core/contract-sdk";

// Load a verdict from JSON
const verdict = loadVerdict(jsonString);

// Get top 5 most severe findings
const critical = topFindings(verdict, 5);

// Filter by severity
const blockers = filterBySeverity(verdict, "BLOCKER");
const highAndCritical = filterBySeverity(verdict, ["BLOCKER", "HIGH"]);

// Get a human-readable summary
console.log(summarizeTrend(verdict));
// Output: "WARN: 75/100 with 85% confidence - 6 findings"
```

## API Reference

### Types

```typescript
import type { Verdict, VerdictV2, Finding, SeverityLevel } from "@truth-core/contract-sdk";
```

### Helper Functions

#### `loadVerdict(input: string | unknown): Verdict`

Load and validate a Verdict artifact from JSON string or object.

```typescript
const verdict = loadVerdict('{"_contract": {...}, "verdict": "PASS"}');
const verdict = loadVerdict(parsedObject);
```

#### `topFindings(verdict: Verdict, limit?: number): Finding[]`

Get the top N findings sorted by severity (BLOCKER > HIGH > MEDIUM > LOW > INFO).

```typescript
const top10 = topFindings(verdict, 10);
const top5 = topFindings(verdict); // default is 5
```

#### `filterBySeverity(verdict: Verdict, severity: SeverityLevel | SeverityLevel[]): Finding[]`

Filter findings by severity level(s).

```typescript
const blockers = filterBySeverity(verdict, "BLOCKER");
const critical = filterBySeverity(verdict, ["BLOCKER", "HIGH"]);
```

#### `summarizeTrend(verdict: Verdict): string`

Generate a human-readable summary of the verdict.

```typescript
console.log(summarizeTrend(verdict));
// "PASS: 95/100 with 92% confidence - 3 findings"
```

#### `hasSeverity(verdict: Verdict, minSeverity?: SeverityLevel): boolean`

Check if the verdict has any findings of a specific severity or higher.

```typescript
if (hasSeverity(verdict, "HIGH")) {
  console.error("Critical issues found!");
}
```

#### `getCategories(verdict: Verdict): string[]`

Get all unique categories from findings.

```typescript
const categories = getCategories(verdict);
// ["security", "performance", "style"]
```

#### `getEngines(verdict: Verdict): string[]`

Get all unique engine names from findings.

```typescript
const engines = getEngines(verdict);
// ["readiness", "invariants", "intel"]
```

### Type Guards

```typescript
import { isVerdict, isReadiness, isVerdictV1, isVerdictV2 } from "@truth-core/contract-sdk";

if (isVerdict(artifact)) {
  // artifact is Verdict
  if (isVerdictV2(artifact)) {
    // artifact is VerdictV2 - has `value`, `confidence`, `items`
    console.log(artifact.confidence);
  }
}
```

## Version Compatibility

This SDK supports both v1 and v2 verdict formats:

| Field | v1 | v2 |
|-------|-----|-----|
| Score field | `score` | `value` |
| Findings field | `findings` | `items` |
| Confidence | Not present | `confidence` (0-1) |
| Evidence refs | Not present | `evidence_refs` |

The helper functions abstract these differences, so your code works with both versions.

## License

MIT
