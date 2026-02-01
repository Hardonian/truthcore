import { currentConfidence } from '../primitives/belief.js';
import { generateId } from '../utils/hash.js';
export var DivergenceType;
(function (DivergenceType) {
    DivergenceType["HIGH_CONFIDENCE_OVERRIDE"] = "high_confidence_override";
    DivergenceType["LOW_CONFIDENCE_ACCEPTANCE"] = "low_confidence_acceptance";
    DivergenceType["REPEATED_OVERRIDE"] = "repeated_override";
    DivergenceType["PATTERN_MISMATCH"] = "pattern_mismatch";
})(DivergenceType || (DivergenceType = {}));
export function createDivergence(input) {
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
    divergences = new Map();
    reconcile(systemBelief, humanOverride) {
        const systemConfidence = currentConfidence(systemBelief);
        const systemAction = this.inferActionFromBelief(systemBelief);
        const humanAction = humanOverride.overrideDecision.action;
        const aligned = systemAction === humanAction;
        const divergenceScore = aligned ? 0.0 : Math.abs(systemConfidence - 0.5);
        const suggestedActions = [];
        if (!aligned) {
            if (systemConfidence >= 0.8) {
                suggestedActions.push('Review system confidence calculation');
                suggestedActions.push('Document reason for override');
                suggestedActions.push('Consider adjusting belief parameters');
            }
            else if (systemConfidence <= 0.3) {
                suggestedActions.push('Increase evidence quality for this decision type');
                suggestedActions.push('Review if system has sufficient information');
            }
            else {
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
    inferActionFromBelief(belief) {
        const confidence = currentConfidence(belief);
        if (confidence >= 0.8) {
            return 'approve';
        }
        else if (confidence <= 0.3) {
            return 'reject';
        }
        return 'review';
    }
    detectDivergence(beliefs, decisions) {
        const detected = [];
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
                    }
                    else if (confidence <= 0.3 && decision.action === 'approve') {
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
    getAllDivergences() {
        return Array.from(this.divergences.values());
    }
    getDivergence(divergenceId) {
        return this.divergences.get(divergenceId);
    }
    stats() {
        const divergences = this.getAllDivergences();
        const byType = {};
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
//# sourceMappingURL=reconciliation.js.map