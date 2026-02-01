import { describe, it, expect, beforeEach } from '@jest/globals';
import {
  SubstrateRuntime,
  DEFAULT_CONFIG,
  OBSERVE_ONLY_FLAGS,
  EvidenceType,
  DecisionType,
  EconomicSignalType,
  CompositionStrategy
} from '../src/index.js';

describe('SubstrateRuntime', () => {
  let runtime: SubstrateRuntime;

  beforeEach(() => {
    runtime = new SubstrateRuntime({
      ...DEFAULT_CONFIG,
      flags: OBSERVE_ONLY_FLAGS
    });
  });

  describe('Assertion and Evidence', () => {
    it('should record assertion when enabled', () => {
      const evidence = runtime.recordEvidence({
        evidenceType: EvidenceType.RAW,
        content: { checks: ['passed', 'passed'] },
        source: 'test-engine'
      });

      expect(evidence).not.toBeNull();

      const assertion = runtime.recordAssertion({
        claim: 'All tests passed',
        evidenceIds: [evidence!.evidenceId],
        source: 'test-engine'
      });

      expect(assertion).not.toBeNull();
      expect(assertion!.claim).toBe('All tests passed');
      expect(assertion!.evidenceIds).toContain(evidence!.evidenceId);
    });

    it('should return null when disabled', () => {
      const disabledRuntime = new SubstrateRuntime(DEFAULT_CONFIG);

      const assertion = disabledRuntime.recordAssertion({
        claim: 'Test',
        evidenceIds: [],
        source: 'test'
      });

      expect(assertion).toBeNull();
    });

    it('should retrieve assertion lineage', () => {
      const evidence = runtime.recordEvidence({
        evidenceType: EvidenceType.RAW,
        content: { test: 'data' },
        source: 'source-1'
      });

      const assertion = runtime.recordAssertion({
        claim: 'Test claim',
        evidenceIds: [evidence!.evidenceId],
        source: 'engine-1'
      });

      const lineage = runtime.getLineage(assertion!.assertionId);

      expect(lineage).not.toBeNull();
      expect(lineage!.rootAssertion.assertionId).toBe(assertion!.assertionId);
      expect(lineage!.evidenceChain).toHaveLength(1);
    });
  });

  describe('Beliefs', () => {
    it('should form belief from assertion', () => {
      const assertion = runtime.recordAssertion({
        claim: 'Deployment is ready',
        evidenceIds: [],
        source: 'readiness-engine'
      });

      const belief = runtime.formBelief({
        assertionId: assertion!.assertionId,
        confidence: 0.85,
        decayRate: 0.01
      });

      expect(belief).not.toBeNull();
      expect(belief!.confidence).toBe(0.85);
      expect(belief!.assertionId).toBe(assertion!.assertionId);
    });

    it('should update belief confidence', () => {
      const assertion = runtime.recordAssertion({
        claim: 'Test',
        evidenceIds: [],
        source: 'test'
      });

      const belief = runtime.formBelief({
        assertionId: assertion!.assertionId,
        confidence: 0.7
      });

      const updated = runtime.updateBeliefConfidence(belief!.beliefId, 0.9);

      expect(updated).not.toBeNull();
      expect(updated!.confidence).toBe(0.9);
      expect(updated!.version).toBe(2);
    });

    it('should compose multiple beliefs for same assertion', () => {
      const assertion = runtime.recordAssertion({
        claim: 'System is healthy',
        evidenceIds: [],
        source: 'health-check'
      });

      runtime.formBelief({
        assertionId: assertion!.assertionId,
        confidence: 0.9
      });

      runtime.formBelief({
        assertionId: assertion!.assertionId,
        confidence: 0.7
      });

      runtime.formBelief({
        assertionId: assertion!.assertionId,
        confidence: 0.85
      });

      const composed = runtime.composeBeliefsForAssertion(
        assertion!.assertionId,
        CompositionStrategy.AVERAGE
      );

      expect(composed).toBeGreaterThan(0.7);
      expect(composed).toBeLessThan(0.9);
    });
  });

  describe('Contradictions', () => {
    it('should detect assertion conflicts', () => {
      runtime.recordAssertion({
        claim: 'Coverage is 85%',
        evidenceIds: [],
        source: 'engine-a'
      });

      runtime.recordAssertion({
        claim: 'Coverage is 72%',
        evidenceIds: [],
        source: 'engine-b'
      });

      runtime.detectContradictions();

      const stats = runtime.stats();
      expect(stats.contradictions.total).toBeGreaterThan(0);
    });
  });

  describe('Economic Signals', () => {
    it('should record economic signals', () => {
      const signal = runtime.recordEconomicSignal({
        signalType: EconomicSignalType.COST,
        amount: 150.0,
        unit: 'USD',
        source: 'billing-api',
        appliesTo: 'deployment-123'
      });

      expect(signal).not.toBeNull();
      expect(signal!.amount).toBe(150.0);
    });

    it('should evaluate budget pressure', () => {
      runtime.recordEconomicSignal({
        signalType: EconomicSignalType.COST,
        amount: 800,
        unit: 'USD',
        source: 'billing',
        appliesTo: 'org-1'
      });

      const pressure = runtime.evaluateBudgetPressure('org-1', 1000);

      expect(pressure).not.toBeNull();
      expect(pressure!.currentSpend).toBe(800);
      expect(pressure!.pressureLevel).toBe('high');
    });
  });

  describe('Patterns and Learning', () => {
    it('should detect usage patterns', () => {
      for (let i = 0; i < 5; i++) {
        runtime.recordDecision({
          decisionType: DecisionType.SYSTEM,
          action: 'approve',
          rationale: ['Automated approval']
        });
      }

      const patterns = runtime.detectPatterns('org-1', 30);

      expect(patterns).toBeDefined();
    });
  });

  describe('Reporting', () => {
    it('should generate markdown report', () => {
      const assertion = runtime.recordAssertion({
        claim: 'System ready',
        evidenceIds: [],
        source: 'test'
      });

      runtime.formBelief({
        assertionId: assertion!.assertionId,
        confidence: 0.9
      });

      const report = runtime.generateMarkdownReport('org-1', 30);

      expect(report).not.toBeNull();
      expect(report).toContain('# Cognitive Substrate Report');
      expect(report).toContain('Belief Health');
    });

    it('should generate JSON report', () => {
      const report = runtime.generateJSONReport('org-1', 30);

      expect(report).not.toBeNull();

      const parsed = JSON.parse(report!);
      expect(parsed.organizationId).toBe('org-1');
      expect(parsed.beliefHealth).toBeDefined();
    });
  });

  describe('Stats and Utilities', () => {
    it('should provide comprehensive stats', () => {
      runtime.recordAssertion({
        claim: 'Test',
        evidenceIds: [],
        source: 'test'
      });

      const stats = runtime.stats();

      expect(stats.assertions).toBe(1);
      expect(stats.beliefs).toBeDefined();
      expect(stats.contradictions).toBeDefined();
      expect(stats.overrides).toBeDefined();
      expect(stats.economic).toBeDefined();
      expect(stats.telemetry).toBeDefined();
    });

    it('should report enabled status', () => {
      expect(runtime.isEnabled()).toBe(true);

      const disabledRuntime = new SubstrateRuntime(DEFAULT_CONFIG);
      expect(disabledRuntime.isEnabled()).toBe(false);
    });
  });

  describe('Zero-Cost Abstraction', () => {
    it('should have minimal overhead when disabled', () => {
      const disabledRuntime = new SubstrateRuntime(DEFAULT_CONFIG);

      const start = Date.now();

      for (let i = 0; i < 1000; i++) {
        disabledRuntime.recordAssertion({
          claim: 'Test',
          evidenceIds: [],
          source: 'test'
        });
      }

      const elapsed = Date.now() - start;

      expect(elapsed).toBeLessThan(10);
    });
  });
});
