import { Assertion } from '../primitives/assertion.js';
import { Belief, currentConfidence } from '../primitives/belief.js';
import { Decision } from '../primitives/decision.js';
import { MeaningVersion, isCompatibleWith } from '../primitives/meaning.js';
import { CognitivePolicy } from '../primitives/policy.js';
import { AssertionGraph } from './assertion-graph.js';
import { BeliefEngine } from './belief-engine.js';
import { generateId } from '../utils/hash.js';

export enum ContradictionType {
  ASSERTION_CONFLICT = 'assertion_conflict',
  BELIEF_DIVERGENCE = 'belief_divergence',
  POLICY_CONFLICT = 'policy_conflict',
  SEMANTIC_DRIFT = 'semantic_drift',
  ECONOMIC_VIOLATION = 'economic_violation'
}

export enum Severity {
  BLOCKER = 'blocker',
  HIGH = 'high',
  MEDIUM = 'medium',
  LOW = 'low',
  INFO = 'info'
}

export enum ResolutionStatus {
  UNRESOLVED = 'unresolved',
  HUMAN_OVERRIDE = 'human_override',
  POLICY_RULED = 'policy_ruled',
  IGNORED = 'ignored'
}

export interface Contradiction {
  readonly contradictionId: string;
  readonly contradictionType: ContradictionType;
  readonly conflictingItems: readonly string[];
  readonly severity: Severity;
  readonly explanation: string;
  readonly detectedAt: string;
  resolutionStatus: ResolutionStatus;
  readonly metadata: Record<string, unknown>;
}

export interface ContradictionInput {
  contradictionType: ContradictionType;
  conflictingItems: string[];
  severity: Severity;
  explanation: string;
  metadata?: Record<string, unknown>;
}

export function createContradiction(input: ContradictionInput): Contradiction {
  const detectedAt = new Date().toISOString();

  const contradictionId = generateId('contradiction', {
    type: input.contradictionType,
    items: input.conflictingItems,
    timestamp: detectedAt
  });

  return {
    contradictionId,
    contradictionType: input.contradictionType,
    conflictingItems: Object.freeze([...input.conflictingItems]),
    severity: input.severity,
    explanation: input.explanation,
    detectedAt,
    resolutionStatus: ResolutionStatus.UNRESOLVED,
    metadata: input.metadata ?? {}
  };
}

export class ContradictionDetector {
  private graph: AssertionGraph;
  // Belief engine for future belief-based contradiction detection
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  private _beliefEngine: BeliefEngine;
  private contradictions: Map<string, Contradiction> = new Map();

  constructor(graph: AssertionGraph, beliefEngine: BeliefEngine) {
    this.graph = graph;
    this._beliefEngine = beliefEngine;
  }

  detectAssertionConflicts(): Contradiction[] {
    const detected: Contradiction[] = [];
    const assertions = this.graph.getAllAssertions();

    const claimGroups = new Map<string, Assertion[]>();
    for (const assertion of assertions) {
      const normalized = this.normalizeClaim(assertion.claim);
      if (!claimGroups.has(normalized)) {
        claimGroups.set(normalized, []);
      }
      claimGroups.get(normalized)!.push(assertion);
    }

    for (const [claim, group] of claimGroups.entries()) {
      if (group.length > 1) {
        const hasConflict = this.detectClaimConflict(group);
        if (hasConflict) {
          const contradiction = createContradiction({
            contradictionType: ContradictionType.ASSERTION_CONFLICT,
            conflictingItems: group.map((a) => a.assertionId),
            severity: Severity.HIGH,
            explanation: `Multiple conflicting assertions about: ${claim}`
          });

          this.contradictions.set(contradiction.contradictionId, contradiction);
          detected.push(contradiction);
        }
      }
    }

    return detected;
  }

  private normalizeClaim(claim: string): string {
    return claim.toLowerCase().trim().replace(/\s+/g, ' ');
  }

  private detectClaimConflict(assertions: Assertion[]): boolean {
    if (assertions.length < 2) {
      return false;
    }

    for (let i = 0; i < assertions.length; i++) {
      for (let j = i + 1; j < assertions.length; j++) {
        if (assertions[i].source !== assertions[j].source) {
          return true;
        }
      }
    }

    return false;
  }

  detectBeliefDivergence(systemBelief: Belief, humanDecision: Decision, _threshold: number = 0.3): Contradiction | null {
    const systemConfidence = currentConfidence(systemBelief);

    const isSystemHighConfidence = systemConfidence >= 0.8;
    const humanOverridesSystem = humanDecision.decisionType === 'human_override';

    if (isSystemHighConfidence && humanOverridesSystem) {
      const contradiction = createContradiction({
        contradictionType: ContradictionType.BELIEF_DIVERGENCE,
        conflictingItems: [systemBelief.beliefId, humanDecision.decisionId],
        severity: systemConfidence >= 0.9 ? Severity.HIGH : Severity.MEDIUM,
        explanation: `System has high confidence (${systemConfidence.toFixed(2)}) but human overrode decision`,
        metadata: {
          system_confidence: systemConfidence,
          decision_action: humanDecision.action
        }
      });

      this.contradictions.set(contradiction.contradictionId, contradiction);
      return contradiction;
    }

    return null;
  }

  detectPolicyConflicts(policies: CognitivePolicy[]): Contradiction[] {
    const detected: Contradiction[] = [];

    for (let i = 0; i < policies.length; i++) {
      for (let j = i + 1; j < policies.length; j++) {
        const p1 = policies[i];
        const p2 = policies[j];

        if (this.policiesConflict(p1, p2)) {
          const contradiction = createContradiction({
            contradictionType: ContradictionType.POLICY_CONFLICT,
            conflictingItems: [p1.policyId, p2.policyId],
            severity: Severity.MEDIUM,
            explanation: `Policies ${p1.policyId} and ${p2.policyId} have conflicting rules`,
            metadata: {
              policy1_type: p1.policyType,
              policy2_type: p2.policyType
            }
          });

          this.contradictions.set(contradiction.contradictionId, contradiction);
          detected.push(contradiction);
        }
      }
    }

    return detected;
  }

  private policiesConflict(p1: CognitivePolicy, p2: CognitivePolicy): boolean {
    if (p1.appliesTo !== p2.appliesTo && p1.appliesTo !== '*' && p2.appliesTo !== '*') {
      return false;
    }

    return p1.enforcement !== p2.enforcement && p1.policyType === p2.policyType;
  }

  detectSemanticDrift(meanings: MeaningVersion[]): Contradiction[] {
    const detected: Contradiction[] = [];

    const meaningGroups = new Map<string, MeaningVersion[]>();
    for (const meaning of meanings) {
      if (!meaningGroups.has(meaning.meaningId)) {
        meaningGroups.set(meaning.meaningId, []);
      }
      meaningGroups.get(meaning.meaningId)!.push(meaning);
    }

    for (const [meaningId, versions] of meaningGroups.entries()) {
      if (versions.length > 1) {
        const activeVersions = versions.filter((v) => !v.deprecated);

        if (activeVersions.length > 1) {
          const incompatible = this.findIncompatibleVersions(activeVersions);

          if (incompatible.length > 0) {
            const contradiction = createContradiction({
              contradictionType: ContradictionType.SEMANTIC_DRIFT,
              conflictingItems: incompatible.map((v) => `${v.meaningId}@${v.version}`),
              severity: Severity.MEDIUM,
              explanation: `Multiple incompatible active versions of ${meaningId}`,
              metadata: {
                versions: incompatible.map((v) => v.version)
              }
            });

            this.contradictions.set(contradiction.contradictionId, contradiction);
            detected.push(contradiction);
          }
        }
      }
    }

    return detected;
  }

  private findIncompatibleVersions(versions: MeaningVersion[]): MeaningVersion[] {
    const incompatible: MeaningVersion[] = [];

    for (let i = 0; i < versions.length; i++) {
      for (let j = i + 1; j < versions.length; j++) {
        if (!isCompatibleWith(versions[i], versions[j])) {
          if (!incompatible.includes(versions[i])) {
            incompatible.push(versions[i]);
          }
          if (!incompatible.includes(versions[j])) {
            incompatible.push(versions[j]);
          }
        }
      }
    }

    return incompatible;
  }

  getAllContradictions(): Contradiction[] {
    return Array.from(this.contradictions.values());
  }

  getContradiction(contradictionId: string): Contradiction | undefined {
    return this.contradictions.get(contradictionId);
  }

  resolveContradiction(contradictionId: string, status: ResolutionStatus): void {
    const contradiction = this.contradictions.get(contradictionId);
    if (contradiction !== undefined) {
      contradiction.resolutionStatus = status;
    }
  }

  stats(): {
    total: number;
    unresolved: number;
    bySeverity: Record<string, number>;
    byType: Record<string, number>;
  } {
    const contradictions = this.getAllContradictions();

    const bySeverity: Record<string, number> = {};
    const byType: Record<string, number> = {};

    for (const c of contradictions) {
      bySeverity[c.severity] = (bySeverity[c.severity] ?? 0) + 1;
      byType[c.contradictionType] = (byType[c.contradictionType] ?? 0) + 1;
    }

    return {
      total: contradictions.length,
      unresolved: contradictions.filter((c) => c.resolutionStatus === ResolutionStatus.UNRESOLVED).length,
      bySeverity,
      byType
    };
  }
}
