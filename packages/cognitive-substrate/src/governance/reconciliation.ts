import { Belief, currentConfidence } from '../primitives/belief.js';
import { Decision } from '../primitives/decision.js';
import { HumanOverride } from './human-override.js';
import { generateId } from '../utils/hash.js';

export enum DivergenceType {
  HIGH_CONFIDENCE_OVERRIDE = 'high_confidence_override',
  LOW_CONFIDENCE_ACCEPTANCE = 'low_confidence_acceptance',
  REPEATED_OVERRIDE = 'repeated_override',
  PATTERN_MISMATCH = 'pattern_mismatch'
}

export interface ReconciliationResult {
  readonly aligned: boolean;
  readonly divergenceScore: number;
  readonly explanation: string;
  readonly suggestedActions: readonly string[];
}

export interface Divergence {
  readonly divergenceId: string;
  readonly divergenceType: DivergenceType;
  readonly systemBeliefId: string;
  readonly humanDecisionId: string;
  readonly magnitude: number;
  readonly explanation: string;
  readonly detectedAt: string;
  readonly metadata: Record<string, unknown>;
}

export interface DivergenceInput {
  divergenceType: DivergenceType;
  systemBeliefId: string;
  humanDecisionId: string;
  magnitude: number;
  explanation: string;
  metadata?: Record<string, unknown>;
}

export function createDivergence(input: DivergenceInput): Divergence {
  const detectedAt = new Date().toISOString();

  const divergenceId = generateId('divergence', {
    belief: input.systemBeliefId,
    decision: input.humanDecisionId,
    timestamp: detectedAt
  });

  return {
    divergenceId,
    divergenceType: input.divergenceType,
    systemBeliefId: input.systemBeliefId,
    humanDecisionId: input.humanDecisionId,
    magnitude: input.magnitude,
    explanation: input.explanation,
    detectedAt,
    metadata: input.metadata ?? {}
  };
}

export class ReconciliationEngine {
  private divergences: Map<string, Divergence> = new Map();

  reconcile(systemBelief: Belief, humanOverride: HumanOverride): ReconciliationResult {
    const systemConfidence = currentConfidence(systemBelief);
    const systemAction = this.inferActionFromBelief(systemBelief);
    const humanAction = humanOverride.overrideDecision.action;

    const aligned = systemAction === humanAction;
    const divergenceScore = aligned ? 0.0 : Math.abs(systemConfidence - 0.5);

    const suggestedActions: string[] = [];

    if (!aligned) {
      if (systemConfidence >= 0.8) {
        suggestedActions.push('Review system confidence calculation');
        suggestedActions.push('Document reason for override');
        suggestedActions.push('Consider adjusting belief parameters');
      } else if (systemConfidence <= 0.3) {
        suggestedActions.push('Increase evidence quality for this decision type');
        suggestedActions.push('Review if system has sufficient information');
      } else {
        suggestedActions.push('Borderline case - human judgment appropriate');
      }
    }

    const explanation = aligned
      ? 'System and human decisions are aligned'
      : `System suggested ${systemAction} (confidence: ${systemConfidence.toFixed(2)}) but human chose ${humanAction}`;

    return {
      aligned,
      divergenceScore,
      explanation,
      suggestedActions: Object.freeze(suggestedActions)
    };
  }

  private inferActionFromBelief(belief: Belief): string {
    const confidence = currentConfidence(belief);

    if (confidence >= 0.8) {
      return 'approve';
    } else if (confidence <= 0.3) {
      return 'reject';
    }

    return 'review';
  }

  detectDivergence(beliefs: Belief[], decisions: Decision[]): Divergence[] {
    const detected: Divergence[] = [];

    for (const belief of beliefs) {
      const relatedDecisions = decisions.filter((d) => d.beliefIds.includes(belief.beliefId));

      for (const decision of relatedDecisions) {
        if (decision.decisionType === 'human_override') {
          const confidence = currentConfidence(belief);

          if (confidence >= 0.8) {
            const divergence = createDivergence({
              divergenceType: DivergenceType.HIGH_CONFIDENCE_OVERRIDE,
              systemBeliefId: belief.beliefId,
              humanDecisionId: decision.decisionId,
              magnitude: confidence,
              explanation: `System had high confidence (${confidence.toFixed(2)}) but human overrode`,
              metadata: {
                system_confidence: confidence,
                decision_action: decision.action
              }
            });

            this.divergences.set(divergence.divergenceId, divergence);
            detected.push(divergence);
          } else if (confidence <= 0.3 && decision.action === 'approve') {
            const divergence = createDivergence({
              divergenceType: DivergenceType.LOW_CONFIDENCE_ACCEPTANCE,
              systemBeliefId: belief.beliefId,
              humanDecisionId: decision.decisionId,
              magnitude: 1.0 - confidence,
              explanation: `System had low confidence (${confidence.toFixed(2)}) but human approved`,
              metadata: {
                system_confidence: confidence,
                decision_action: decision.action
              }
            });

            this.divergences.set(divergence.divergenceId, divergence);
            detected.push(divergence);
          }
        }
      }
    }

    return detected;
  }

  getAllDivergences(): Divergence[] {
    return Array.from(this.divergences.values());
  }

  getDivergence(divergenceId: string): Divergence | undefined {
    return this.divergences.get(divergenceId);
  }

  stats(): {
    total: number;
    byType: Record<string, number>;
    averageMagnitude: number;
  } {
    const divergences = this.getAllDivergences();

    const byType: Record<string, number> = {};
    let totalMagnitude = 0;

    for (const d of divergences) {
      byType[d.divergenceType] = (byType[d.divergenceType] ?? 0) + 1;
      totalMagnitude += d.magnitude;
    }

    return {
      total: divergences.length,
      byType,
      averageMagnitude: divergences.length > 0 ? totalMagnitude / divergences.length : 0
    };
  }
}
