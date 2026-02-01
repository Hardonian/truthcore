import { Decision, Authority } from '../primitives/decision.js';
export declare enum ScopeType {
    SINGLE_DECISION = "single_decision",
    RULE = "rule",
    ORG = "org",
    TIME_WINDOW = "time_window"
}
export interface OverrideScope {
    readonly scopeType: ScopeType;
    readonly target: string;
    readonly constraints: Record<string, unknown>;
}
export interface HumanOverride {
    readonly overrideId: string;
    readonly originalDecision: Decision;
    readonly overrideDecision: Decision;
    readonly authority: Authority;
    readonly scope: OverrideScope;
    readonly rationale: string;
    readonly expiresAt: string;
    readonly requiresRenewal: boolean;
    readonly renewalHistory: readonly string[];
    readonly createdAt: string;
    readonly metadata: Record<string, unknown>;
}
export interface HumanOverrideInput {
    originalDecision: Decision;
    overrideDecision: Decision;
    authority: Authority;
    scope: OverrideScope;
    rationale: string;
    expiresAt: string;
    requiresRenewal?: boolean;
    metadata?: Record<string, unknown>;
}
export declare function createHumanOverride(input: HumanOverrideInput): HumanOverride;
export declare function isExpired(override: HumanOverride, now?: Date): boolean;
export declare function isRenewable(override: HumanOverride): boolean;
export declare function renewOverride(override: HumanOverride, newExpiresAt: string, renewalDecisionId: string): HumanOverride;
export declare class HumanOverrideManager {
    private overrides;
    createOverride(input: HumanOverrideInput): HumanOverride;
    getOverride(overrideId: string): HumanOverride | undefined;
    getActiveOverrides(now?: Date): HumanOverride[];
    getExpiredOverrides(now?: Date): HumanOverride[];
    renewOverride(overrideId: string, newExpiresAt: string, renewalDecisionId: string): HumanOverride;
    stats(): {
        total: number;
        active: number;
        expired: number;
        averageRenewals: number;
    };
}
//# sourceMappingURL=human-override.d.ts.map