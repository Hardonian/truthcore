import { SubstrateFlags, DEFAULT_FLAGS } from './flags.js';

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

export const DEFAULT_CONFIG: SubstrateConfig = {
  name: 'default',
  flags: DEFAULT_FLAGS,
  beliefDefaults: {
    defaultDecayRate: 0.0,
    confidenceThresholds: {
      high: 0.8,
      medium: 0.5,
      low: 0.3
    },
    maxGraphDepth: 100,
    pruneExpiredAfterDays: 90
  },
  economicDefaults: {
    defaultCostUnit: 'USD',
    budgetWarningThreshold: 0.8
  },
  governanceDefaults: {
    defaultOverrideExpiryDays: 7,
    requiresRenewal: true,
    maxOverrideScope: 'deployment'
  }
};

export function createConfig(overrides?: Partial<SubstrateConfig>): SubstrateConfig {
  return {
    ...DEFAULT_CONFIG,
    ...overrides,
    flags: {
      ...DEFAULT_CONFIG.flags,
      ...(overrides?.flags ?? {})
    },
    beliefDefaults: {
      ...DEFAULT_CONFIG.beliefDefaults,
      ...(overrides?.beliefDefaults ?? {})
    },
    economicDefaults: {
      ...DEFAULT_CONFIG.economicDefaults,
      ...(overrides?.economicDefaults ?? {})
    },
    governanceDefaults: {
      ...DEFAULT_CONFIG.governanceDefaults,
      ...(overrides?.governanceDefaults ?? {})
    }
  };
}
