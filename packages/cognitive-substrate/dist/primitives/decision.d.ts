export declare enum DecisionType {
    SYSTEM = "system",
    HUMAN_OVERRIDE = "human_override",
    POLICY_ENFORCED = "policy_enforced",
    ECONOMIC = "economic"
}
export interface Authority {
    readonly actor: string;
    readonly scope: string;
    readonly validUntil: string | null;
    readonly requiresRenewal: boolean;
}
export interface Decision {
    readonly decisionId: string;
    readonly decisionType: DecisionType;
    readonly action: string;
    readonly rationale: readonly string[];
    readonly beliefIds: readonly string[];
    readonly policyIds: readonly string[];
    readonly authority: Authority | null;
    readonly scope: string | null;
    readonly expiresAt: string | null;
    readonly createdAt: string;
    readonly metadata: Record<string, unknown>;
}
export interface DecisionInput {
    decisionType: DecisionType;
    action: string;
    rationale: string[];
    beliefIds?: string[];
    policyIds?: string[];
    authority?: Authority | null;
    scope?: string | null;
    expiresAt?: string | null;
    metadata?: Record<string, unknown>;
}
export declare function createDecision(input: DecisionInput): Decision;
export declare function isExpired(decision: Decision, now?: Date): boolean;
export declare function conflictsWith(decision1: Decision, decision2: Decision): boolean;
export declare function decisionToDict(decision: Decision): Record<string, unknown>;
export declare function decisionFromDict(data: Record<string, unknown>): Decision;
//# sourceMappingURL=decision.d.ts.map