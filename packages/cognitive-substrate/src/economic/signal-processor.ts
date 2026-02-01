import { EconomicSignal, EconomicSignalType, influenceWeight } from '../primitives/economic.js';
import { Belief, updateBelief } from '../primitives/belief.js';

export enum PressureLevel {
  LOW = 'low',
  MEDIUM = 'medium',
  HIGH = 'high',
  CRITICAL = 'critical'
}

export interface BudgetPressure {
  readonly currentSpend: number;
  readonly budgetLimit: number | null;
  readonly pressureLevel: PressureLevel;
  readonly timeToLimit: number | null;
}

export class EconomicSignalProcessor {
  private signals: Map<string, EconomicSignal> = new Map();

  recordSignal(signal: EconomicSignal): void {
    this.signals.set(signal.signalId, signal);
  }

  getSignal(signalId: string): EconomicSignal | undefined {
    return this.signals.get(signalId);
  }

  getSignalsForTarget(targetId: string): EconomicSignal[] {
    return Array.from(this.signals.values()).filter((s) => s.appliesTo === targetId);
  }

  computeTotalCost(decisionId: string): number {
    return this.getSignalsForTarget(decisionId)
      .filter((s) => s.signalType === EconomicSignalType.COST)
      .reduce((sum, s) => sum + s.amount, 0);
  }

  computeTotalRisk(decisionId: string): number {
    return this.getSignalsForTarget(decisionId)
      .filter((s) => s.signalType === EconomicSignalType.RISK)
      .reduce((sum, s) => sum + s.amount, 0);
  }

  computeTotalValue(decisionId: string): number {
    return this.getSignalsForTarget(decisionId)
      .filter((s) => s.signalType === EconomicSignalType.VALUE)
      .reduce((sum, s) => sum + s.amount, 0);
  }

  evaluateBudgetPressure(organizationId: string, budgetLimit: number | null = null): BudgetPressure {
    const orgSignals = this.getSignalsForTarget(organizationId);

    const currentSpend = orgSignals
      .filter((s) => s.signalType === EconomicSignalType.COST)
      .reduce((sum, s) => sum + s.amount, 0);

    let pressureLevel = PressureLevel.LOW;
    let timeToLimit: number | null = null;

    if (budgetLimit !== null) {
      const ratio = currentSpend / budgetLimit;

      if (ratio >= 0.95) {
        pressureLevel = PressureLevel.CRITICAL;
      } else if (ratio >= 0.8) {
        pressureLevel = PressureLevel.HIGH;
      } else if (ratio >= 0.6) {
        pressureLevel = PressureLevel.MEDIUM;
      }

      const remaining = budgetLimit - currentSpend;
      if (remaining > 0) {
        const burnRate = this.estimateBurnRate(orgSignals);
        if (burnRate > 0) {
          timeToLimit = remaining / burnRate;
        }
      }
    }

    return {
      currentSpend,
      budgetLimit,
      pressureLevel,
      timeToLimit
    };
  }

  private estimateBurnRate(signals: EconomicSignal[]): number {
    const costSignals = signals
      .filter((s) => s.signalType === EconomicSignalType.COST)
      .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());

    if (costSignals.length < 2) {
      return 0;
    }

    const recent = costSignals.slice(-10);
    const firstTimestamp = new Date(recent[0].timestamp).getTime();
    const lastTimestamp = new Date(recent[recent.length - 1].timestamp).getTime();

    const timeSpanDays = (lastTimestamp - firstTimestamp) / (1000 * 60 * 60 * 24);

    if (timeSpanDays === 0) {
      return 0;
    }

    const totalCost = recent.reduce((sum, s) => sum + s.amount, 0);
    return totalCost / timeSpanDays;
  }

  influenceBelief(belief: Belief, economicSignals: EconomicSignal[]): Belief {
    if (economicSignals.length === 0) {
      return belief;
    }

    let adjustmentFactor = 1.0;

    for (const signal of economicSignals) {
      const weight = influenceWeight(signal);

      switch (signal.signalType) {
        case EconomicSignalType.COST:
          adjustmentFactor *= 1.0 - weight * 0.1;
          break;

        case EconomicSignalType.RISK:
          adjustmentFactor *= 1.0 - weight * 0.15;
          break;

        case EconomicSignalType.VALUE:
          adjustmentFactor *= 1.0 + weight * 0.1;
          break;

        case EconomicSignalType.BUDGET_PRESSURE:
          adjustmentFactor *= 1.0 - weight * 0.2;
          break;
      }
    }

    const newConfidence = Math.max(0, Math.min(1, belief.confidence * adjustmentFactor));

    return updateBelief(belief, newConfidence, {
      economic_adjustment: adjustmentFactor,
      economic_signals: economicSignals.map((s) => s.signalId)
    });
  }

  stats(): {
    totalSignals: number;
    totalCost: number;
    totalRisk: number;
    totalValue: number;
    byType: Record<string, number>;
  } {
    const signals = Array.from(this.signals.values());

    const byType: Record<string, number> = {};
    let totalCost = 0;
    let totalRisk = 0;
    let totalValue = 0;

    for (const signal of signals) {
      byType[signal.signalType] = (byType[signal.signalType] ?? 0) + 1;

      switch (signal.signalType) {
        case EconomicSignalType.COST:
          totalCost += signal.amount;
          break;
        case EconomicSignalType.RISK:
          totalRisk += signal.amount;
          break;
        case EconomicSignalType.VALUE:
          totalValue += signal.amount;
          break;
      }
    }

    return {
      totalSignals: signals.length,
      totalCost,
      totalRisk,
      totalValue,
      byType
    };
  }

  clear(): void {
    this.signals.clear();
  }
}
