import { generateId } from '../utils/hash.js';
export var EconomicSignalType;
(function (EconomicSignalType) {
    EconomicSignalType["COST"] = "cost";
    EconomicSignalType["RISK"] = "risk";
    EconomicSignalType["VALUE"] = "value";
    EconomicSignalType["BUDGET_PRESSURE"] = "budget_pressure";
})(EconomicSignalType || (EconomicSignalType = {}));
export function createEconomicSignal(input) {
    const timestamp = new Date().toISOString();
    const signalId = generateId('econ', {
        type: input.signalType,
        amount: input.amount,
        appliesTo: input.appliesTo,
        timestamp
    });
    const confidence = input.confidence ?? 1.0;
    if (confidence < 0 || confidence > 1) {
        throw new Error(`Confidence must be between 0 and 1, got ${confidence}`);
    }
    return {
        signalId,
        signalType: input.signalType,
        amount: input.amount,
        unit: input.unit,
        source: input.source,
        appliesTo: input.appliesTo,
        confidence,
        timestamp,
        metadata: input.metadata ?? {}
    };
}
export function influenceWeight(signal) {
    const typeWeights = {
        [EconomicSignalType.COST]: 0.8,
        [EconomicSignalType.RISK]: 1.0,
        [EconomicSignalType.VALUE]: 0.6,
        [EconomicSignalType.BUDGET_PRESSURE]: 0.9
    };
    return typeWeights[signal.signalType] * signal.confidence;
}
export function economicSignalToDict(signal) {
    return {
        signal_id: signal.signalId,
        signal_type: signal.signalType,
        amount: signal.amount,
        unit: signal.unit,
        source: signal.source,
        applies_to: signal.appliesTo,
        confidence: signal.confidence,
        timestamp: signal.timestamp,
        metadata: signal.metadata
    };
}
export function economicSignalFromDict(data) {
    return {
        signalId: data.signal_id,
        signalType: data.signal_type,
        amount: data.amount,
        unit: data.unit,
        source: data.source,
        appliesTo: data.applies_to,
        confidence: data.confidence,
        timestamp: data.timestamp,
        metadata: data.metadata ?? {}
    };
}
//# sourceMappingURL=economic.js.map