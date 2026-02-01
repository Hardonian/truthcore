import { SubstrateFlags } from './flags.js';
export interface SubstrateConfig {
    name: string;
    flags: SubstrateFlags;
    beliefDefaults: BeliefDefaults;
    economicDefaults: EconomicDefaults;
    governanceDefaults: GovernanceDefaults;
}
export interface BeliefDefaults {
    defaultDecayRate: number;
    confidenceThresholds: ConfidenceThresholds;
    maxGraphDepth: number;
    pruneExpiredAfterDays: number;
}
export interface ConfidenceThresholds {
    high: number;
    medium: number;
    low: number;
}
export interface EconomicDefaults {
    defaultCostUnit: string;
    budgetWarningThreshold: number;
}
export interface GovernanceDefaults {
    defaultOverrideExpiryDays: number;
    requiresRenewal: boolean;
    maxOverrideScope: string;
}
export declare const DEFAULT_CONFIG: SubstrateConfig;
export declare function createConfig(overrides?: Partial<SubstrateConfig>): SubstrateConfig;
//# sourceMappingURL=substrate-config.d.ts.map