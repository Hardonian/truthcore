import { UsagePattern } from './pattern-detector.js';
import { CognitivePolicy } from '../primitives/policy.js';
import { Decision } from '../primitives/decision.js';
export declare enum Stage {
    EARLY = "early",
    SCALING = "scaling",
    MATURE = "mature"
}
export interface StageGate {
    readonly stage: Stage;
    readonly confidence: number;
    readonly indicators: readonly string[];
    readonly detectedAt: string;
    readonly metadata: Record<string, unknown>;
}
export interface StageIndicators {
    teamSize: number;
    policyCount: number;
    overrideRate: number;
    deployFrequency: number;
    avgDecisionTime: number;
}
export declare function detectStageGate(indicators: StageIndicators, patterns: UsagePattern[], _policies: CognitivePolicy[], _decisions: Decision[]): StageGate;
export declare enum MismatchType {
    OVER_ENGINEERED = "over_engineered",
    UNDER_GOVERNED = "under_governed",
    WRONG_FOCUS = "wrong_focus"
}
export declare enum MismatchSeverity {
    LOW = "low",
    MEDIUM = "medium",
    HIGH = "high"
}
export interface ToolingMismatch {
    readonly mismatchType: MismatchType;
    readonly currentStage: Stage;
    readonly currentTooling: string;
    readonly severity: MismatchSeverity;
    readonly recommendation: string;
    readonly detectedAt: string;
    readonly metadata: Record<string, unknown>;
}
export declare function detectToolingMismatch(stageGate: StageGate, indicators: StageIndicators): ToolingMismatch | null;
//# sourceMappingURL=stage-gate.d.ts.map