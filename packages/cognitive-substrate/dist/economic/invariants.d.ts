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
export declare enum ComparisonOperator {
    LESS_THAN = "<",
    LESS_THAN_OR_EQUAL = "<=",
    GREATER_THAN = ">",
    GREATER_THAN_OR_EQUAL = ">=",
    EQUAL = "==",
    NOT_EQUAL = "!="
}
export interface InvariantViolation {
    readonly invariantId: string;
    readonly actualValue: number;
    readonly expectedValue: number;
    readonly operator: ComparisonOperator;
    readonly enforcement: EnforcementMode;
    readonly explanation: string;
}
export declare function createEconomicInvariant(invariantId: string, rule: InvariantRule, enforcement?: EnforcementMode, appliesTo?: string): EconomicInvariant;
export declare class EconomicInvariantEvaluator {
    private invariants;
    addInvariant(invariant: EconomicInvariant): void;
    removeInvariant(invariantId: string): void;
    evaluate(context: Map<string, number>): InvariantViolation[];
    private evaluateInvariant;
    private compareValues;
    getAllInvariants(): EconomicInvariant[];
}
export declare const COMMON_INVARIANTS: {
    COST_PER_DEPLOYMENT_MAX: EconomicInvariant;
    TOKEN_BUDGET_DAILY: EconomicInvariant;
    RISK_THRESHOLD_HIGH: EconomicInvariant;
};
//# sourceMappingURL=invariants.d.ts.map