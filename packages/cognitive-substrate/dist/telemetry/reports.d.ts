import { BeliefEngine } from '../graph/belief-engine.js';
import { ContradictionDetector } from '../graph/contradiction.js';
import { HumanOverrideManager } from '../governance/human-override.js';
import { EconomicSignalProcessor } from '../economic/signal-processor.js';
import { PatternDetector } from '../learning/pattern-detector.js';
import { StageGate } from '../learning/stage-gate.js';
export interface CognitiveSummary {
    readonly generatedAt: string;
    readonly organizationId: string;
    readonly periodDays: number;
    readonly beliefHealth: BeliefHealthSummary;
    readonly contradictions: ContradictionSummary;
    readonly humanOverrides: OverrideSummary;
    readonly economic: EconomicSummary;
    readonly organizational: OrganizationalSummary;
}
export interface BeliefHealthSummary {
    readonly totalBeliefs: number;
    readonly highConfidence: number;
    readonly highConfidencePercent: number;
    readonly lowConfidence: number;
    readonly lowConfidencePercent: number;
    readonly decayedBeliefs: number;
    readonly decayedPercent: number;
    readonly averageConfidence: number;
}
export interface ContradictionSummary {
    readonly total: number;
    readonly resolved: number;
    readonly unresolved: number;
    readonly bySeverity: Record<string, number>;
    readonly topContradictions: Array<{
        type: string;
        count: number;
    }>;
}
export interface OverrideSummary {
    readonly total: number;
    readonly active: number;
    readonly expired: number;
    readonly averageRenewals: number;
    readonly mostOverriddenRule: {
        ruleId: string;
        count: number;
    } | null;
}
export interface EconomicSummary {
    readonly totalCost: number;
    readonly averageCostPerDecision: number;
    readonly budgetPressure: string;
    readonly budgetUtilization: number | null;
    readonly highCostDecisions: number;
}
export interface OrganizationalSummary {
    readonly detectedStage: string;
    readonly stageConfidence: number;
    readonly keyIndicators: readonly string[];
    readonly toolingMismatch: string | null;
    readonly recommendation: string | null;
}
export declare class ReportGenerator {
    generateCognitiveSummary(organizationId: string, periodDays: number, beliefEngine: BeliefEngine, contradictionDetector: ContradictionDetector, overrideManager: HumanOverrideManager, economicProcessor: EconomicSignalProcessor, _patternDetector: PatternDetector, stageGate: StageGate | null): CognitiveSummary;
    generateMarkdownReport(summary: CognitiveSummary): string;
    generateJSONReport(summary: CognitiveSummary): string;
}
//# sourceMappingURL=reports.d.ts.map