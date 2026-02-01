import type { Verdict, Finding, SeverityLevel } from "./types";

/**
 * Load and validate a Verdict artifact from JSON string or object.
 * Performs runtime validation to ensure the object conforms to the expected shape.
 *
 * @param input - JSON string or object to parse and validate
 * @returns Parsed and validated Verdict object
 * @throws Error if input is invalid or malformed
 *
 * @example
 * ```typescript
 * const verdict = loadVerdict('{"_contract": {...}, "verdict": "PASS", ...}');
 * console.log(verdict.verdict); // "PASS"
 * ```
 */
export function loadVerdict(input: unknown): Verdict {
  let data: unknown;

  if (typeof input === "string") {
    try {
      data = JSON.parse(input);
    } catch (e) {
      throw new Error(`Invalid JSON: ${e instanceof Error ? e.message : "Unknown error"}`);
    }
  } else {
    data = input;
  }

  if (typeof data !== "object" || data === null) {
    throw new Error("Verdict must be an object");
  }

  const obj = data as Record<string, unknown>;

  // Validate required _contract field
  if (!obj._contract || typeof obj._contract !== "object") {
    throw new Error("Missing required field: _contract");
  }

  const contract = obj._contract as Record<string, unknown>;
  if (contract.artifact_type !== "verdict") {
    throw new Error(`Invalid artifact_type: expected "verdict", got "${String(contract.artifact_type)}"`);
  }

  // Validate verdict field
  if (!obj.verdict || !["PASS", "FAIL", "WARN", "UNKNOWN"].includes(obj.verdict as string)) {
    throw new Error(`Invalid verdict: must be one of PASS, FAIL, WARN, UNKNOWN`);
  }

  // Check version-specific fields
  const contractVersion = contract.contract_version as string;

  if (contractVersion === "2.0.0") {
    if (typeof obj.value !== "number") {
      throw new Error("Verdict v2 requires 'value' field (number)");
    }
    if (typeof obj.confidence !== "number") {
      throw new Error("Verdict v2 requires 'confidence' field (number)");
    }
    if (!Array.isArray(obj.items)) {
      throw new Error("Verdict v2 requires 'items' field (array)");
    }
  } else if (contractVersion === "1.0.0") {
    if (typeof obj.score !== "number") {
      throw new Error("Verdict v1 requires 'score' field (number)");
    }
    if (!Array.isArray(obj.findings)) {
      throw new Error("Verdict v1 requires 'findings' field (array)");
    }
  }

  return data as Verdict;
}

/**
 * Get the top N findings from a verdict, sorted by severity.
 * BLOCKER > HIGH > MEDIUM > LOW > INFO
 *
 * @param verdict - The Verdict object
 * @param limit - Maximum number of findings to return (default: 5)
 * @returns Array of top findings sorted by severity
 *
 * @example
 * ```typescript
 * const topIssues = topFindings(verdict, 3);
 * // Returns top 3 most severe findings
 * ```
 */
export function topFindings(verdict: Verdict, limit: number = 5): Finding[] {
  const items = getItems(verdict);

  const severityOrder: Record<SeverityLevel, number> = {
    BLOCKER: 0,
    HIGH: 1,
    MEDIUM: 2,
    LOW: 3,
    INFO: 4,
  };

  const sorted = [...items].sort((a, b) => {
    const aOrder = severityOrder[a.severity];
    const bOrder = severityOrder[b.severity];
    return aOrder - bOrder;
  });

  return sorted.slice(0, limit);
}

/**
 * Filter findings by severity level(s).
 * Supports filtering by single level or array of levels.
 *
 * @param verdict - The Verdict object
 * @param severity - Severity level(s) to filter by
 * @returns Filtered array of findings
 *
 * @example
 * ```typescript
 * const blockers = filterBySeverity(verdict, "BLOCKER");
 * const critical = filterBySeverity(verdict, ["BLOCKER", "HIGH"]);
 * ```
 */
export function filterBySeverity(
  verdict: Verdict,
  severity: SeverityLevel | SeverityLevel[]
): Finding[] {
  const items = getItems(verdict);
  const severities = Array.isArray(severity) ? severity : [severity];
  return items.filter((item) => severities.includes(item.severity));
}

/**
 * Summarize the trend of a verdict based on its value/score and confidence.
 * Returns a human-readable summary string.
 *
 * @param verdict - The Verdict object
 * @returns Summary string describing the trend
 *
 * @example
 * ```typescript
 * console.log(summarizeTrend(verdict));
 * // "PASS: 95/100 with 92% confidence - 1 finding"
 * ```
 */
export function summarizeTrend(verdict: Verdict): string {
  const value = getValue(verdict);
  const confidence = getConfidence(verdict);
  const itemCount = getItems(verdict).length;

  const confidencePercent = Math.round((confidence || 0) * 100);
  const findingWord = itemCount === 1 ? "finding" : "findings";

  return `${verdict.verdict}: ${value}/100 with ${confidencePercent}% confidence - ${itemCount} ${findingWord}`;
}

/**
 * Check if a verdict has any findings of a specific severity or higher.
 *
 * @param verdict - The Verdict object
 * @param minSeverity - Minimum severity to check (default: "HIGH")
 * @returns True if any finding meets or exceeds the severity threshold
 */
export function hasSeverity(
  verdict: Verdict,
  minSeverity: SeverityLevel = "HIGH"
): boolean {
  const severityRanks: Record<SeverityLevel, number> = {
    BLOCKER: 5,
    HIGH: 4,
    MEDIUM: 3,
    LOW: 2,
    INFO: 1,
  };

  const minRank = severityRanks[minSeverity];
  const items = getItems(verdict);

  return items.some((item) => severityRanks[item.severity] >= minRank);
}

/**
 * Get all unique categories from findings.
 *
 * @param verdict - The Verdict object
 * @returns Array of unique category names
 */
export function getCategories(verdict: Verdict): string[] {
  const items = getItems(verdict);
  const categories = new Set<string>();

  items.forEach((item) => {
    if (item.category) {
      categories.add(item.category);
    }
  });

  return Array.from(categories);
}

/**
 * Get all unique engine names from findings.
 *
 * @param verdict - The Verdict object
 * @returns Array of unique engine names
 */
export function getEngines(verdict: Verdict): string[] {
  const items = getItems(verdict);
  const engines = new Set<string>();

  items.forEach((item) => {
    if (item.engine) {
      engines.add(item.engine);
    }
  });

  return Array.from(engines);
}

// Helper functions to abstract version differences

function getItems(verdict: Verdict): Finding[] {
  // Handle both v1 (findings) and v2 (items)
  if ("items" in verdict && Array.isArray(verdict.items)) {
    // Type assertion needed as items is unknown[] in VerdictV2
    // eslint-disable-next-line @typescript-eslint/no-unnecessary-type-assertion
    return verdict.items as Finding[];
  }
  if ("findings" in verdict && Array.isArray(verdict.findings)) {
    // Type assertion needed as findings is unknown[] in VerdictV1
    // eslint-disable-next-line @typescript-eslint/no-unnecessary-type-assertion
    return verdict.findings as Finding[];
  }
  return [];
}

function getValue(verdict: Verdict): number {
  // Handle both v1 (score) and v2 (value)
  if ("value" in verdict && typeof verdict.value === "number") {
    return verdict.value;
  }
  if ("score" in verdict && typeof verdict.score === "number") {
    return verdict.score;
  }
  return 0;
}

function getConfidence(verdict: Verdict): number {
  if ("confidence" in verdict && typeof verdict.confidence === "number") {
    return verdict.confidence;
  }
  // Default confidence for v1 verdicts
  return 1.0;
}
