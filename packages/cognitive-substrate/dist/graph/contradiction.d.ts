import { Belief } from '../primitives/belief.js';
import { Decision } from '../primitives/decision.js';
import { MeaningVersion } from '../primitives/meaning.js';
import { CognitivePolicy } from '../primitives/policy.js';
import { AssertionGraph } from './assertion-graph.js';
import { BeliefEngine } from './belief-engine.js';
export declare enum ContradictionType {
    ASSERTION_CONFLICT = "assertion_conflict",
    BELIEF_DIVERGENCE = "belief_divergence",
    POLICY_CONFLICT = "policy_conflict",
    SEMANTIC_DRIFT = "semantic_drift",
    ECONOMIC_VIOLATION = "economic_violation"
}
export declare enum Severity {
    BLOCKER = "blocker",
    HIGH = "high",
    MEDIUM = "medium",
    LOW = "low",
    INFO = "info"
}
export declare enum ResolutionStatus {
    UNRESOLVED = "unresolved",
    HUMAN_OVERRIDE = "human_override",
    POLICY_RULED = "policy_ruled",
    IGNORED = "ignored"
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
export declare function createContradiction(input: ContradictionInput): Contradiction;
export declare class ContradictionDetector {
    private graph;
    private _beliefEngine;
    private contradictions;
    constructor(graph: AssertionGraph, beliefEngine: BeliefEngine);
    detectAssertionConflicts(): Contradiction[];
    private normalizeClaim;
    private detectClaimConflict;
    detectBeliefDivergence(systemBelief: Belief, humanDecision: Decision, _threshold?: number): Contradiction | null;
    detectPolicyConflicts(policies: CognitivePolicy[]): Contradiction[];
    private policiesConflict;
    detectSemanticDrift(meanings: MeaningVersion[]): Contradiction[];
    private findIncompatibleVersions;
    getAllContradictions(): Contradiction[];
    getContradiction(contradictionId: string): Contradiction | undefined;
    resolveContradiction(contradictionId: string, status: ResolutionStatus): void;
    stats(): {
        total: number;
        unresolved: number;
        bySeverity: Record<string, number>;
        byType: Record<string, number>;
    };
}
//# sourceMappingURL=contradiction.d.ts.map