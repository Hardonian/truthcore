export interface Belief {
    readonly beliefId: string;
    readonly assertionId: string;
    confidence: number;
    version: number;
    readonly createdAt: string;
    updatedAt: string;
    readonly decayRate: number;
    readonly validityUntil: string | null;
    readonly upstreamDependencies: readonly string[];
    readonly metadata: Record<string, unknown>;
}
export interface BeliefInput {
    assertionId: string;
    confidence: number;
    decayRate?: number;
    validityUntil?: string | null;
    upstreamDependencies?: string[];
    metadata?: Record<string, unknown>;
}
export declare function createBelief(input: BeliefInput): Belief;
export declare function currentConfidence(belief: Belief, now?: Date): number;
export declare function isValid(belief: Belief, now?: Date): boolean;
export declare function updateBelief(belief: Belief, newConfidence: number, metadata?: Record<string, unknown>): Belief;
export declare function beliefToDict(belief: Belief): Record<string, unknown>;
export declare function beliefFromDict(data: Record<string, unknown>): Belief;
//# sourceMappingURL=belief.d.ts.map