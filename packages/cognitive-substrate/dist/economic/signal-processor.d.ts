import { EconomicSignal } from '../primitives/economic.js';
import { Belief } from '../primitives/belief.js';
export declare enum PressureLevel {
    LOW = "low",
    MEDIUM = "medium",
    HIGH = "high",
    CRITICAL = "critical"
}
export interface BudgetPressure {
    readonly currentSpend: number;
    readonly budgetLimit: number | null;
    readonly pressureLevel: PressureLevel;
    readonly timeToLimit: number | null;
}
export declare class EconomicSignalProcessor {
    private signals;
    recordSignal(signal: EconomicSignal): void;
    getSignal(signalId: string): EconomicSignal | undefined;
    getSignalsForTarget(targetId: string): EconomicSignal[];
    computeTotalCost(decisionId: string): number;
    computeTotalRisk(decisionId: string): number;
    computeTotalValue(decisionId: string): number;
    evaluateBudgetPressure(organizationId: string, budgetLimit?: number | null): BudgetPressure;
    private estimateBurnRate;
    influenceBelief(belief: Belief, economicSignals: EconomicSignal[]): Belief;
    stats(): {
        totalSignals: number;
        totalCost: number;
        totalRisk: number;
        totalValue: number;
        byType: Record<string, number>;
    };
    clear(): void;
}
//# sourceMappingURL=signal-processor.d.ts.map