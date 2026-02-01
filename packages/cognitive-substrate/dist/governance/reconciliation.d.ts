import { Belief } from '../primitives/belief.js';
import { Decision } from '../primitives/decision.js';
import { HumanOverride } from './human-override.js';
export declare enum DivergenceType {
    HIGH_CONFIDENCE_OVERRIDE = "high_confidence_override",
    LOW_CONFIDENCE_ACCEPTANCE = "low_confidence_acceptance",
    REPEATED_OVERRIDE = "repeated_override",
    PATTERN_MISMATCH = "pattern_mismatch"
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
export declare function createDivergence(input: DivergenceInput): Divergence;
export declare class ReconciliationEngine {
    private divergences;
    reconcile(systemBelief: Belief, humanOverride: HumanOverride): ReconciliationResult;
    private inferActionFromBelief;
    detectDivergence(beliefs: Belief[], decisions: Decision[]): Divergence[];
    getAllDivergences(): Divergence[];
    getDivergence(divergenceId: string): Divergence | undefined;
    stats(): {
        total: number;
        byType: Record<string, number>;
        averageMagnitude: number;
    };
}
//# sourceMappingURL=reconciliation.d.ts.map