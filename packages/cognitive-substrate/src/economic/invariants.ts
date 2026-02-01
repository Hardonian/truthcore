import { EnforcementMode } from '../primitives/policy.js';
import { EconomicSignalType } from '../primitives/economic.js';

export interface EconomicInvariant {
  readonly invariantId: string;
  readonly rule: InvariantRule;
  readonly enforcement: EnforcementMode;
  readonly appliesTo: string;
  readonly metadata: Record<string, unknown>;
}

export interface InvariantRule {
  readonly operator: ComparisonOperator;
  readonly left: string;
  readonly right: number | string;
  readonly signalType?: EconomicSignalType;
}

export enum ComparisonOperator {
  LESS_THAN = '<',
  LESS_THAN_OR_EQUAL = '<=',
  GREATER_THAN = '>',
  GREATER_THAN_OR_EQUAL = '>=',
  EQUAL = '==',
  NOT_EQUAL = '!='
}

export interface InvariantViolation {
  readonly invariantId: string;
  readonly actualValue: number;
  readonly expectedValue: number;
  readonly operator: ComparisonOperator;
  readonly enforcement: EnforcementMode;
  readonly explanation: string;
}

export function createEconomicInvariant(
  invariantId: string,
  rule: InvariantRule,
  enforcement: EnforcementMode = EnforcementMode.OBSERVE,
  appliesTo: string = '*'
): EconomicInvariant {
  return {
    invariantId,
    rule,
    enforcement,
    appliesTo,
    metadata: {}
  };
}

export class EconomicInvariantEvaluator {
  private invariants: Map<string, EconomicInvariant> = new Map();

  addInvariant(invariant: EconomicInvariant): void {
    this.invariants.set(invariant.invariantId, invariant);
  }

  removeInvariant(invariantId: string): void {
    this.invariants.delete(invariantId);
  }

  evaluate(context: Map<string, number>): InvariantViolation[] {
    const violations: InvariantViolation[] = [];

    for (const invariant of this.invariants.values()) {
      const violation = this.evaluateInvariant(invariant, context);
      if (violation !== null) {
        violations.push(violation);
      }
    }

    return violations;
  }

  private evaluateInvariant(invariant: EconomicInvariant, context: Map<string, number>): InvariantViolation | null {
    const actualValue = context.get(invariant.rule.left);

    if (actualValue === undefined) {
      return null;
    }

    const expectedValue = typeof invariant.rule.right === 'number' ? invariant.rule.right : parseFloat(invariant.rule.right);

    const passes = this.compareValues(actualValue, expectedValue, invariant.rule.operator);

    if (!passes) {
      return {
        invariantId: invariant.invariantId,
        actualValue,
        expectedValue,
        operator: invariant.rule.operator,
        enforcement: invariant.enforcement,
        explanation: `${invariant.rule.left} (${actualValue}) ${invariant.rule.operator} ${expectedValue} failed`
      };
    }

    return null;
  }

  private compareValues(left: number, right: number, operator: ComparisonOperator): boolean {
    switch (operator) {
      case ComparisonOperator.LESS_THAN:
        return left < right;
      case ComparisonOperator.LESS_THAN_OR_EQUAL:
        return left <= right;
      case ComparisonOperator.GREATER_THAN:
        return left > right;
      case ComparisonOperator.GREATER_THAN_OR_EQUAL:
        return left >= right;
      case ComparisonOperator.EQUAL:
        return left === right;
      case ComparisonOperator.NOT_EQUAL:
        return left !== right;
      default:
        return false;
    }
  }

  getAllInvariants(): EconomicInvariant[] {
    return Array.from(this.invariants.values());
  }
}

export const COMMON_INVARIANTS = {
  COST_PER_DEPLOYMENT_MAX: createEconomicInvariant(
    'cost.deployment.max',
    {
      operator: ComparisonOperator.LESS_THAN_OR_EQUAL,
      left: 'deployment.cost',
      right: 100,
      signalType: EconomicSignalType.COST
    },
    EnforcementMode.WARN
  ),

  TOKEN_BUDGET_DAILY: createEconomicInvariant(
    'token.budget.daily',
    {
      operator: ComparisonOperator.LESS_THAN_OR_EQUAL,
      left: 'daily_tokens',
      right: 1_000_000,
      signalType: EconomicSignalType.COST
    },
    EnforcementMode.OBSERVE
  ),

  RISK_THRESHOLD_HIGH: createEconomicInvariant(
    'risk.threshold.high',
    {
      operator: ComparisonOperator.LESS_THAN,
      left: 'decision.risk',
      right: 1000,
      signalType: EconomicSignalType.RISK
    },
    EnforcementMode.WARN
  )
};
