import { describe, it, expect } from "vitest";
import {
  isVerdict,
  isReadiness,
  isVerdictV1,
  isVerdictV2,
} from "../src/types";
import type { VerdictV2, ReadinessV1, VerdictV1 } from "../src/types";

describe("Type Guards", () => {
  const sampleVerdictV2: VerdictV2 = {
    _contract: {
      artifact_type: "verdict",
      contract_version: "2.0.0",
      truthcore_version: "0.2.0",
      created_at: "2026-01-31T00:00:00Z",
      schema: "schemas/verdict/v2.0.0/verdict.schema.json",
    },
    verdict: "PASS",
    value: 95,
    confidence: 0.92,
    items: [],
  };

  const sampleVerdictV1: VerdictV1 = {
    _contract: {
      artifact_type: "verdict",
      contract_version: "1.0.0",
      truthcore_version: "0.2.0",
      created_at: "2026-01-31T00:00:00Z",
      schema: "schemas/verdict/v1.0.0/verdict.schema.json",
    },
    verdict: "PASS",
    score: 95,
    findings: [],
  };

  const sampleReadiness: ReadinessV1 = {
    _contract: {
      artifact_type: "readiness",
      contract_version: "1.0.0",
      truthcore_version: "0.2.0",
      created_at: "2026-01-31T00:00:00Z",
      schema: "schemas/readiness/v1.0.0/readiness.schema.json",
    },
    ready: true,
    checks: [],
  };

  describe("isVerdict", () => {
    it("should return true for verdict artifacts", () => {
      expect(isVerdict(sampleVerdictV2)).toBe(true);
      expect(isVerdict(sampleVerdictV1)).toBe(true);
    });

    it("should return false for non-verdict artifacts", () => {
      expect(isVerdict(sampleReadiness)).toBe(false);
    });
  });

  describe("isReadiness", () => {
    it("should return true for readiness artifacts", () => {
      expect(isReadiness(sampleReadiness)).toBe(true);
    });

    it("should return false for non-readiness artifacts", () => {
      expect(isReadiness(sampleVerdictV2)).toBe(false);
      expect(isReadiness(sampleVerdictV1)).toBe(false);
    });
  });

  describe("isVerdictV2", () => {
    it("should return true for v2 verdicts", () => {
      expect(isVerdictV2(sampleVerdictV2)).toBe(true);
    });

    it("should return false for v1 verdicts", () => {
      expect(isVerdictV2(sampleVerdictV1)).toBe(false);
    });
  });

  describe("isVerdictV1", () => {
    it("should return true for v1 verdicts", () => {
      expect(isVerdictV1(sampleVerdictV1)).toBe(true);
    });

    it("should return false for v2 verdicts", () => {
      expect(isVerdictV1(sampleVerdictV2)).toBe(false);
    });
  });
});
