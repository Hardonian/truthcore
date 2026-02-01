export declare enum EconomicSignalType {
    COST = "cost",
    RISK = "risk",
    VALUE = "value",
    BUDGET_PRESSURE = "budget_pressure"
}
export interface EconomicSignal {
    readonly signalId: string;
    readonly signalType: EconomicSignalType;
    readonly amount: number;
    readonly unit: string;
    readonly source: string;
    readonly appliesTo: string;
    readonly confidence: number;
    readonly timestamp: string;
    readonly metadata: Record<string, unknown>;
}
export interface EconomicSignalInput {
    signalType: EconomicSignalType;
    amount: number;
    unit: string;
    source: string;
    appliesTo: string;
    confidence?: number;
    metadata?: Record<string, unknown>;
}
export declare function createEconomicSignal(input: EconomicSignalInput): EconomicSignal;
export declare function influenceWeight(signal: EconomicSignal): number;
export declare function economicSignalToDict(signal: EconomicSignal): Record<string, unknown>;
export declare function economicSignalFromDict(data: Record<string, unknown>): EconomicSignal;
//# sourceMappingURL=economic.d.ts.map