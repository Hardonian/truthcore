import { EnforcementMode } from '../primitives/policy.js';
import { EconomicSignalType } from '../primitives/economic.js';
export var ComparisonOperator;
(function (ComparisonOperator) {
    ComparisonOperator["LESS_THAN"] = "<";
    ComparisonOperator["LESS_THAN_OR_EQUAL"] = "<=";
    ComparisonOperator["GREATER_THAN"] = ">";
    ComparisonOperator["GREATER_THAN_OR_EQUAL"] = ">=";
    ComparisonOperator["EQUAL"] = "==";
    ComparisonOperator["NOT_EQUAL"] = "!=";
})(ComparisonOperator || (ComparisonOperator = {}));
export function createEconomicInvariant(invariantId, rule, enforcement = EnforcementMode.OBSERVE, appliesTo = '*') {
    return {
        invariantId,
        rule,
        enforcement,
        appliesTo,
        metadata: {}
    };
}
export class EconomicInvariantEvaluator {
    invariants = new Map();
    addInvariant(invariant) {
        this.invariants.set(invariant.invariantId, invariant);
    }
    removeInvariant(invariantId) {
        this.invariants.delete(invariantId);
    }
    evaluate(context) {
        const violations = [];
        for (const invariant of this.invariants.values()) {
            const violation = this.evaluateInvariant(invariant, context);
            if (violation !== null) {
                violations.push(violation);
            }
        }
        return violations;
    }
    evaluateInvariant(invariant, context) {
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
    compareValues(left, right, operator) {
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
    getAllInvariants() {
        return Array.from(this.invariants.values());
    }
}
export const COMMON_INVARIANTS = {
    COST_PER_DEPLOYMENT_MAX: createEconomicInvariant('cost.deployment.max', {
        operator: ComparisonOperator.LESS_THAN_OR_EQUAL,
        left: 'deployment.cost',
        right: 100,
        signalType: EconomicSignalType.COST
    }, EnforcementMode.WARN),
    TOKEN_BUDGET_DAILY: createEconomicInvariant('token.budget.daily', {
        operator: ComparisonOperator.LESS_THAN_OR_EQUAL,
        left: 'daily_tokens',
        right: 1_000_000,
        signalType: EconomicSignalType.COST
    }, EnforcementMode.OBSERVE),
    RISK_THRESHOLD_HIGH: createEconomicInvariant('risk.threshold.high', {
        operator: ComparisonOperator.LESS_THAN,
        left: 'decision.risk',
        right: 1000,
        signalType: EconomicSignalType.RISK
    }, EnforcementMode.WARN)
};
//# sourceMappingURL=invariants.js.map