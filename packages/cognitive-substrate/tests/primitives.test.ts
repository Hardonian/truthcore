import { describe, it, expect } from '@jest/globals';
import {
  createEvidence,
  EvidenceType,
  isStale,
  createAssertion,
  createBelief,
  currentConfidence,
  isValid,
  updateBelief,
  createMeaningVersion,
  isCompatibleWith,
  createDecision,
  DecisionType,
  isExpired as isDecisionExpired,
  createEconomicSignal,
  EconomicSignalType,
  influenceWeight
} from '../src/primitives/index.js';

describe('Evidence', () => {
  it('should create evidence with all properties', () => {
    const evidence = createEvidence({
      evidenceType: EvidenceType.RAW,
      content: { test: 'data' },
      source: 'test-source',
      validityPeriod: 3600
    });

    expect(evidence.evidenceId).toBeDefined();
    expect(evidence.evidenceType).toBe(EvidenceType.RAW);
    expect(evidence.source).toBe('test-source');
    expect(evidence.validityPeriod).toBe(3600);
  });

  it('should detect stale evidence', () => {
    const evidence = createEvidence({
      evidenceType: EvidenceType.RAW,
      content: { test: 'data' },
      source: 'test-source',
      validityPeriod: 1
    });

    expect(isStale(evidence)).toBe(false);

    const futureTime = new Date(Date.now() + 2000);
    expect(isStale(evidence, futureTime)).toBe(true);
  });

  it('should never mark evidence as stale if no validity period', () => {
    const evidence = createEvidence({
      evidenceType: EvidenceType.DERIVED,
      content: { test: 'data' },
      source: 'test-source',
      validityPeriod: null
    });

    const farFuture = new Date(Date.now() + 1000000000);
    expect(isStale(evidence, farFuture)).toBe(false);
  });
});

describe('Assertion', () => {
  it('should create assertion with evidence references', () => {
    const assertion = createAssertion({
      claim: 'System is ready for deployment',
      evidenceIds: ['ev1', 'ev2', 'ev3'],
      source: 'readiness-engine',
      transformation: 'aggregated multiple checks'
    });

    expect(assertion.assertionId).toBeDefined();
    expect(assertion.claim).toBe('System is ready for deployment');
    expect(assertion.evidenceIds).toHaveLength(3);
    expect(assertion.transformation).toBe('aggregated multiple checks');
  });

  it('should freeze evidence IDs array', () => {
    const assertion = createAssertion({
      claim: 'Test claim',
      evidenceIds: ['ev1'],
      source: 'test'
    });

    expect(() => {
      (assertion.evidenceIds as string[]).push('ev2');
    }).toThrow();
  });
});

describe('Belief', () => {
  it('should create belief with confidence', () => {
    const belief = createBelief({
      assertionId: 'assertion-1',
      confidence: 0.85,
      decayRate: 0.01
    });

    expect(belief.beliefId).toBeDefined();
    expect(belief.confidence).toBe(0.85);
    expect(belief.version).toBe(1);
    expect(belief.decayRate).toBe(0.01);
  });

  it('should enforce confidence bounds', () => {
    expect(() => {
      createBelief({
        assertionId: 'assertion-1',
        confidence: 1.5
      });
    }).toThrow();

    expect(() => {
      createBelief({
        assertionId: 'assertion-1',
        confidence: -0.1
      });
    }).toThrow();
  });

  it('should decay confidence over time', () => {
    const belief = createBelief({
      assertionId: 'assertion-1',
      confidence: 0.9,
      decayRate: 0.1
    });

    const now = new Date(belief.createdAt);
    const oneDayLater = new Date(now.getTime() + 24 * 60 * 60 * 1000);

    const decayed = currentConfidence(belief, oneDayLater);

    expect(decayed).toBeLessThan(0.9);
    expect(decayed).toBeGreaterThan(0);
  });

  it('should not decay if decay rate is zero', () => {
    const belief = createBelief({
      assertionId: 'assertion-1',
      confidence: 0.9,
      decayRate: 0.0
    });

    const farFuture = new Date(Date.now() + 1000 * 60 * 60 * 24 * 365);
    const confidence = currentConfidence(belief, farFuture);

    expect(confidence).toBe(0.9);
  });

  it('should update belief and increment version', () => {
    const belief = createBelief({
      assertionId: 'assertion-1',
      confidence: 0.8
    });

    const updated = updateBelief(belief, 0.9);

    expect(updated.confidence).toBe(0.9);
    expect(updated.version).toBe(2);
    expect(updated.beliefId).toBe(belief.beliefId);
  });

  it('should respect validity period', () => {
    const now = new Date();
    const expiresIn = new Date(now.getTime() + 1000);

    const belief = createBelief({
      assertionId: 'assertion-1',
      confidence: 0.9,
      validityUntil: expiresIn.toISOString()
    });

    expect(isValid(belief, now)).toBe(true);

    const afterExpiry = new Date(expiresIn.getTime() + 1000);
    expect(isValid(belief, afterExpiry)).toBe(false);
  });
});

describe('MeaningVersion', () => {
  it('should create meaning version', () => {
    const meaning = createMeaningVersion({
      meaningId: 'coverage',
      version: '1.0.0',
      definition: 'Line coverage percentage',
      computation: 'covered_lines / total_lines'
    });

    expect(meaning.meaningId).toBe('coverage');
    expect(meaning.version).toBe('1.0.0');
    expect(meaning.deprecated).toBe(false);
  });

  it('should detect compatible versions', () => {
    const v1 = createMeaningVersion({
      meaningId: 'coverage',
      version: '1.0.0',
      definition: 'Line coverage'
    });

    const v1_1 = createMeaningVersion({
      meaningId: 'coverage',
      version: '1.1.0',
      definition: 'Line coverage enhanced'
    });

    const v2 = createMeaningVersion({
      meaningId: 'coverage',
      version: '2.0.0',
      definition: 'Branch coverage'
    });

    expect(isCompatibleWith(v1, v1_1)).toBe(true);
    expect(isCompatibleWith(v1, v2)).toBe(false);
  });

  it('should not allow cross-meaning compatibility', () => {
    const m1 = createMeaningVersion({
      meaningId: 'coverage',
      version: '1.0.0',
      definition: 'Coverage'
    });

    const m2 = createMeaningVersion({
      meaningId: 'quality',
      version: '1.0.0',
      definition: 'Quality'
    });

    expect(isCompatibleWith(m1, m2)).toBe(false);
  });
});

describe('Decision', () => {
  it('should create system decision', () => {
    const decision = createDecision({
      decisionType: DecisionType.SYSTEM,
      action: 'approve',
      rationale: ['All checks passed', 'Confidence above threshold']
    });

    expect(decision.decisionId).toBeDefined();
    expect(decision.decisionType).toBe(DecisionType.SYSTEM);
    expect(decision.action).toBe('approve');
    expect(decision.rationale).toHaveLength(2);
  });

  it('should create human override decision', () => {
    const decision = createDecision({
      decisionType: DecisionType.HUMAN_OVERRIDE,
      action: 'ship',
      rationale: ['Urgent hotfix needed'],
      authority: {
        actor: 'alice@example.com',
        scope: 'deployment',
        validUntil: null,
        requiresRenewal: false
      },
      expiresAt: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString()
    });

    expect(decision.authority).toBeDefined();
    expect(decision.authority?.actor).toBe('alice@example.com');
  });

  it('should detect expired decisions', () => {
    const now = new Date();
    const expiresIn = new Date(now.getTime() + 1000);

    const decision = createDecision({
      decisionType: DecisionType.HUMAN_OVERRIDE,
      action: 'approve',
      rationale: ['Test'],
      expiresAt: expiresIn.toISOString()
    });

    expect(isDecisionExpired(decision, now)).toBe(false);

    const afterExpiry = new Date(expiresIn.getTime() + 1000);
    expect(isDecisionExpired(decision, afterExpiry)).toBe(true);
  });
});

describe('EconomicSignal', () => {
  it('should create economic signal', () => {
    const signal = createEconomicSignal({
      signalType: EconomicSignalType.COST,
      amount: 150.0,
      unit: 'USD',
      source: 'billing-system',
      appliesTo: 'deployment-123'
    });

    expect(signal.signalId).toBeDefined();
    expect(signal.signalType).toBe(EconomicSignalType.COST);
    expect(signal.amount).toBe(150.0);
    expect(signal.unit).toBe('USD');
  });

  it('should calculate influence weight', () => {
    const costSignal = createEconomicSignal({
      signalType: EconomicSignalType.COST,
      amount: 100,
      unit: 'USD',
      source: 'test',
      appliesTo: 'test',
      confidence: 1.0
    });

    const riskSignal = createEconomicSignal({
      signalType: EconomicSignalType.RISK,
      amount: 500,
      unit: 'USD',
      source: 'test',
      appliesTo: 'test',
      confidence: 0.8
    });

    expect(influenceWeight(costSignal)).toBeGreaterThan(0);
    expect(influenceWeight(riskSignal)).toBeGreaterThan(influenceWeight(costSignal));
  });
});
