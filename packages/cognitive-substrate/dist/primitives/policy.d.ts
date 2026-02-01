export declare enum PolicyType {
    BELIEF = "belief",
    ECONOMIC = "economic",
    GOVERNANCE = "governance",
    SEMANTIC = "semantic"
}
export declare enum EnforcementMode {
    OBSERVE = "observe",
    WARN = "warn",
    BLOCK = "block"
}
export interface CognitivePolicy {
    readonly policyId: string;
    readonly policyType: PolicyType;
    readonly rule: Record<string, unknown>;
    readonly enforcement: EnforcementMode;
    readonly appliesTo: string;
    readonly priority: number;
    readonly metadata: Record<string, unknown>;
}
export interface CognitivePolicyInput {
    policyId: string;
    policyType: PolicyType;
    rule: Record<string, unknown>;
    enforcement?: EnforcementMode;
    appliesTo?: string;
    priority?: number;
    metadata?: Record<string, unknown>;
}
export declare function createCognitivePolicy(input: CognitivePolicyInput): CognitivePolicy;
export declare function policyToDict(policy: CognitivePolicy): Record<string, unknown>;
export declare function policyFromDict(data: Record<string, unknown>): CognitivePolicy;
//# sourceMappingURL=policy.d.ts.map