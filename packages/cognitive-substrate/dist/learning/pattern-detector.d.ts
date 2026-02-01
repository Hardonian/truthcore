import { Decision } from '../primitives/decision.js';
import { HumanOverride } from '../governance/human-override.js';
export declare enum PatternType {
    FREQUENT_OVERRIDE = "frequent_override",
    CONSISTENT_APPROVAL = "consistent_approval",
    RISK_AVERSE = "risk_averse",
    COST_SENSITIVE = "cost_sensitive",
    VELOCITY_FOCUSED = "velocity_focused"
}
export interface UsagePattern {
    readonly patternId: string;
    readonly patternType: PatternType;
    readonly frequency: string;
    readonly confidence: number;
    readonly firstSeen: string;
    readonly lastSeen: string;
    readonly exampleInstances: readonly string[];
    readonly metadata: Record<string, unknown>;
}
export interface UsagePatternInput {
    patternType: PatternType;
    frequency: string;
    confidence: number;
    firstSeen: string;
    lastSeen: string;
    exampleInstances: string[];
    metadata?: Record<string, unknown>;
}
export declare function createUsagePattern(input: UsagePatternInput): UsagePattern;
export declare class PatternDetector {
    private patterns;
    private decisions;
    private overrides;
    recordDecision(decision: Decision): void;
    recordOverride(override: HumanOverride): void;
    detectUsagePatterns(_organizationId: string, lookbackDays?: number): UsagePattern[];
    private detectFrequentOverrides;
    private detectConsistentApprovals;
    private detectRiskAversion;
    private calculateFrequency;
    getAllPatterns(): UsagePattern[];
    getPattern(patternId: string): UsagePattern | undefined;
    stats(): {
        totalPatterns: number;
        byType: Record<string, number>;
    };
}
//# sourceMappingURL=pattern-detector.d.ts.map