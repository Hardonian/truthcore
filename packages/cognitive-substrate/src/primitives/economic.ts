import { generateId } from '../utils/hash.js';

export enum EconomicSignalType {
  COST = 'cost',
  RISK = 'risk',
  VALUE = 'value',
  BUDGET_PRESSURE = 'budget_pressure'
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

export function createEconomicSignal(input: EconomicSignalInput): EconomicSignal {
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

export function influenceWeight(signal: EconomicSignal): number {
  const typeWeights: Record<EconomicSignalType, number> = {
    [EconomicSignalType.COST]: 0.8,
    [EconomicSignalType.RISK]: 1.0,
    [EconomicSignalType.VALUE]: 0.6,
    [EconomicSignalType.BUDGET_PRESSURE]: 0.9
  };

  return typeWeights[signal.signalType] * signal.confidence;
}

export function economicSignalToDict(signal: EconomicSignal): Record<string, unknown> {
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

export function economicSignalFromDict(data: Record<string, unknown>): EconomicSignal {
  return {
    signalId: data.signal_id as string,
    signalType: data.signal_type as EconomicSignalType,
    amount: data.amount as number,
    unit: data.unit as string,
    source: data.source as string,
    appliesTo: data.applies_to as string,
    confidence: data.confidence as number,
    timestamp: data.timestamp as string,
    metadata: (data.metadata as Record<string, unknown>) ?? {}
  };
}
