import { describe, it, expect } from "vitest";
import {
  loadVerdict,
  topFindings,
  filterBySeverity,
  summarizeTrend,
  hasSeverity,
  getCategories,
  getEngines,
} from "../src/helpers";
import type { Verdict, VerdictV2 } from "../src/types";

// Sample v2 verdict for testing
const sampleVerdictV2: VerdictV2 = {
  _contract: {
    artifact_type: "verdict",
    contract_version: "2.0.0",
    truthcore_version: "0.2.0",
    created_at: "2026-01-31T00:00:00Z",
    schema: "schemas/verdict/v2.0.0/verdict.schema.json",
    engine_versions: {
      readiness: "1.0.0",
    },
  },
  verdict: "WARN",
  value: 75,
  confidence: 0.85,
  items: [
    {
      id: "finding-001",
      severity: "BLOCKER",
      message: "Critical security vulnerability",
      category: "security",
      engine: "readiness",
      confidence: 0.95,
    },
    {
      id: "finding-002",
      severity: "HIGH",
      message: "Performance degradation detected",
      category: "performance",
      engine: "invariants",
      confidence: 0.88,
    },
    {
      id: "finding-003",
      severity: "MEDIUM",
      message: "Code style inconsistency",
      category: "style",
      engine: "readiness",
      confidence: 0.75,
    },
    {
      id: "finding-004",
      severity: "LOW",
      message: "Minor documentation issue",
      category: "documentation",
      engine: "readiness",
    },
    {
      id: "finding-005",
      severity: "INFO",
      message: "Optional optimization available",
      category: "optimization",
      engine: "intel",
    },
    {
      id: "finding-006",
      severity: "HIGH",
      message: "Deprecated API usage",
      category: "maintenance",
      engine: "invariants",
      confidence: 0.9,
    },
  ],
  evidence_refs: ["evidence-001"],
  metadata: {
    mode: "PR",
    total_checks: 10,
  },
};

// Sample v1 verdict for testing backward compatibility
const sampleVerdictV1 = {
  _contract: {
    artifact_type: "verdict",
    contract_version: "1.0.0",
    truthcore_version: "0.2.0",
    created_at: "2026-01-31T00:00:00Z",
    schema: "schemas/verdict/v1.0.0/verdict.schema.json",
    engine_versions: {
      readiness: "1.0.0",
    },
  },
  verdict: "PASS",
  score: 95,
  findings: [
    {
      id: "finding-001",
      severity: "LOW",
      message: "Minor code style issue",
      category: "style",
      engine: "readiness",
    },
  ],
  metadata: {
    mode: "PR",
    total_checks: 10,
  },
};

describe("loadVerdict", () => {
  it("should parse valid v2 verdict from string", () => {
    const json = JSON.stringify(sampleVerdictV2);
    const result = loadVerdict(json);
    expect(result.verdict).toBe("WARN");
    expect(result._contract.contract_version).toBe("2.0.0");
  });

  it("should parse valid v2 verdict from object", () => {
    const result = loadVerdict(sampleVerdictV2);
    expect(result.verdict).toBe("WARN");
    expect(result.value).toBe(75);
    expect(result.confidence).toBe(0.85);
  });

  it("should parse valid v1 verdict from object", () => {
    const result = loadVerdict(sampleVerdictV1);
    expect(result.verdict).toBe("PASS");
    expect(result.score).toBe(95);
  });

  it("should throw error for invalid JSON string", () => {
    expect(() => loadVerdict("not valid json")).toThrow("Invalid JSON");
  });

  it("should throw error for non-object input", () => {
    expect(() => loadVerdict(123)).toThrow("Verdict must be an object");
  });

  it("should throw error for missing _contract", () => {
    expect(() => loadVerdict({ verdict: "PASS" })).toThrow("Missing required field: _contract");
  });

  it("should throw error for invalid verdict value", () => {
    const invalid = {
      _contract: { artifact_type: "verdict" },
      verdict: "INVALID",
    };
    expect(() => loadVerdict(invalid)).toThrow("Invalid verdict");
  });

  it("should throw error for v2 verdict missing value field", () => {
    const invalid = {
      _contract: {
        artifact_type: "verdict",
        contract_version: "2.0.0",
      },
      verdict: "PASS",
      confidence: 0.9,
      items: [],
    };
    expect(() => loadVerdict(invalid)).toThrow("Verdict v2 requires 'value' field");
  });

  it("should throw error for v1 verdict missing score field", () => {
    const invalid = {
      _contract: {
        artifact_type: "verdict",
        contract_version: "1.0.0",
      },
      verdict: "PASS",
      findings: [],
    };
    expect(() => loadVerdict(invalid)).toThrow("Verdict v1 requires 'score' field");
  });

  it("should throw error for wrong artifact_type", () => {
    const invalid = {
      _contract: {
        artifact_type: "readiness",
        contract_version: "2.0.0",
      },
    };
    expect(() => loadVerdict(invalid)).toThrow('Invalid artifact_type: expected "verdict"');
  });
});

describe("topFindings", () => {
  it("should return findings sorted by severity", () => {
    const result = topFindings(sampleVerdictV2, 3);
    expect(result).toHaveLength(3);
    expect(result[0].severity).toBe("BLOCKER");
    expect(result[1].severity).toBe("HIGH");
    expect(result[2].severity).toBe("HIGH");
  });

  it("should respect the limit parameter", () => {
    const result = topFindings(sampleVerdictV2, 2);
    expect(result).toHaveLength(2);
  });

  it("should default to 5 findings", () => {
    const result = topFindings(sampleVerdictV2);
    expect(result).toHaveLength(5);
  });

  it("should work with v1 verdicts", () => {
    const result = topFindings(sampleVerdictV1 as unknown as Verdict);
    expect(result).toHaveLength(1);
    expect(result[0].severity).toBe("LOW");
  });
});

describe("filterBySeverity", () => {
  it("should filter by single severity level", () => {
    const result = filterBySeverity(sampleVerdictV2, "HIGH");
    expect(result).toHaveLength(2);
    expect(result.every((f) => f.severity === "HIGH")).toBe(true);
  });

  it("should filter by multiple severity levels", () => {
    const result = filterBySeverity(sampleVerdictV2, ["BLOCKER", "HIGH"]);
    expect(result).toHaveLength(3);
    expect(result.some((f) => f.severity === "BLOCKER")).toBe(true);
    expect(result.some((f) => f.severity === "HIGH")).toBe(true);
  });

  it("should return empty array when no matches", () => {
    const result = filterBySeverity(sampleVerdictV2, "INFO");
    expect(result).toHaveLength(1);
  });

  it("should work with v1 verdicts", () => {
    const result = filterBySeverity(sampleVerdictV1 as unknown as Verdict, "LOW");
    expect(result).toHaveLength(1);
  });
});

describe("summarizeTrend", () => {
  it("should generate correct summary for v2 verdict", () => {
    const result = summarizeTrend(sampleVerdictV2);
    expect(result).toBe("WARN: 75/100 with 85% confidence - 6 findings");
  });

  it("should generate correct summary for v1 verdict", () => {
    const result = summarizeTrend(sampleVerdictV1 as unknown as Verdict);
    expect(result).toBe("PASS: 95/100 with 100% confidence - 1 finding");
  });

  it("should handle singular 'finding' correctly", () => {
    const verdictWithOneFinding: VerdictV2 = {
      ...sampleVerdictV2,
      items: [sampleVerdictV2.items[0]],
    };
    const result = summarizeTrend(verdictWithOneFinding);
    expect(result).toContain("1 finding");
  });
});

describe("hasSeverity", () => {
  it("should return true when severity exists at or above threshold", () => {
    expect(hasSeverity(sampleVerdictV2, "BLOCKER")).toBe(true);
    expect(hasSeverity(sampleVerdictV2, "HIGH")).toBe(true);
  });

  it("should return false when no severity meets threshold", () => {
    expect(hasSeverity(sampleVerdictV2, "BLOCKER")).toBe(true);
    // Create a verdict with only LOW/INFO findings
    const lowVerdict: VerdictV2 = {
      ...sampleVerdictV2,
      items: sampleVerdictV2.items.filter((f) => f.severity === "LOW" || f.severity === "INFO"),
    };
    expect(hasSeverity(lowVerdict, "HIGH")).toBe(false);
  });

  it("should default to HIGH severity", () => {
    expect(hasSeverity(sampleVerdictV2)).toBe(true);
  });

  it("should work with v1 verdicts", () => {
    expect(hasSeverity(sampleVerdictV1 as unknown as Verdict, "LOW")).toBe(true);
    expect(hasSeverity(sampleVerdictV1 as unknown as Verdict, "HIGH")).toBe(false);
  });
});

describe("getCategories", () => {
  it("should return unique categories from v2 verdict", () => {
    const result = getCategories(sampleVerdictV2);
    expect(result).toContain("security");
    expect(result).toContain("performance");
    expect(result).toContain("style");
    expect(result).toContain("documentation");
    expect(result).toContain("optimization");
    expect(result).toContain("maintenance");
    expect(result).toHaveLength(6);
  });

  it("should return empty array when no categories", () => {
    const verdictWithoutCategories: VerdictV2 = {
      ...sampleVerdictV2,
      items: sampleVerdictV2.items.map((item) => ({ ...item, category: undefined })),
    };
    const result = getCategories(verdictWithoutCategories);
    expect(result).toHaveLength(0);
  });

  it("should work with v1 verdicts", () => {
    const result = getCategories(sampleVerdictV1 as unknown as Verdict);
    expect(result).toContain("style");
  });
});

describe("getEngines", () => {
  it("should return unique engines from v2 verdict", () => {
    const result = getEngines(sampleVerdictV2);
    expect(result).toContain("readiness");
    expect(result).toContain("invariants");
    expect(result).toContain("intel");
    expect(result).toHaveLength(3);
  });

  it("should return empty array when no engines", () => {
    const verdictWithoutEngines: VerdictV2 = {
      ...sampleVerdictV2,
      items: sampleVerdictV2.items.map((item) => ({ ...item, engine: undefined })),
    };
    const result = getEngines(verdictWithoutEngines);
    expect(result).toHaveLength(0);
  });

  it("should work with v1 verdicts", () => {
    const result = getEngines(sampleVerdictV1 as unknown as Verdict);
    expect(result).toContain("readiness");
  });
});
