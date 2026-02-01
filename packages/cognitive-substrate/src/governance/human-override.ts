import { Decision, Authority } from '../primitives/decision.js';
import { generateId } from '../utils/hash.js';

export enum ScopeType {
  SINGLE_DECISION = 'single_decision',
  RULE = 'rule',
  ORG = 'org',
  TIME_WINDOW = 'time_window'
}

export interface OverrideScope {
  readonly scopeType: ScopeType;
  readonly target: string;
  readonly constraints: Record<string, unknown>;
}

export interface HumanOverride {
  readonly overrideId: string;
  readonly originalDecision: Decision;
  readonly overrideDecision: Decision;
  readonly authority: Authority;
  readonly scope: OverrideScope;
  readonly rationale: string;
  readonly expiresAt: string;
  readonly requiresRenewal: boolean;
  readonly renewalHistory: readonly string[];
  readonly createdAt: string;
  readonly metadata: Record<string, unknown>;
}

export interface HumanOverrideInput {
  originalDecision: Decision;
  overrideDecision: Decision;
  authority: Authority;
  scope: OverrideScope;
  rationale: string;
  expiresAt: string;
  requiresRenewal?: boolean;
  metadata?: Record<string, unknown>;
}

export function createHumanOverride(input: HumanOverrideInput): HumanOverride {
  const createdAt = new Date().toISOString();

  const overrideId = generateId('override', {
    original: input.originalDecision.decisionId,
    override: input.overrideDecision.decisionId,
    timestamp: createdAt
  });

  return {
    overrideId,
    originalDecision: input.originalDecision,
    overrideDecision: input.overrideDecision,
    authority: input.authority,
    scope: input.scope,
    rationale: input.rationale,
    expiresAt: input.expiresAt,
    requiresRenewal: input.requiresRenewal ?? true,
    renewalHistory: Object.freeze([]),
    createdAt,
    metadata: input.metadata ?? {}
  };
}

export function isExpired(override: HumanOverride, now: Date = new Date()): boolean {
  const expiryDate = new Date(override.expiresAt);
  return now >= expiryDate;
}

export function isRenewable(override: HumanOverride): boolean {
  return override.requiresRenewal;
}

export function renewOverride(
  override: HumanOverride,
  newExpiresAt: string,
  renewalDecisionId: string
): HumanOverride {
  return {
    ...override,
    expiresAt: newExpiresAt,
    renewalHistory: Object.freeze([...override.renewalHistory, renewalDecisionId])
  };
}

export class HumanOverrideManager {
  private overrides: Map<string, HumanOverride> = new Map();

  createOverride(input: HumanOverrideInput): HumanOverride {
    const override = createHumanOverride(input);
    this.overrides.set(override.overrideId, override);
    return override;
  }

  getOverride(overrideId: string): HumanOverride | undefined {
    return this.overrides.get(overrideId);
  }

  getActiveOverrides(now: Date = new Date()): HumanOverride[] {
    return Array.from(this.overrides.values()).filter((o) => !isExpired(o, now));
  }

  getExpiredOverrides(now: Date = new Date()): HumanOverride[] {
    return Array.from(this.overrides.values()).filter((o) => isExpired(o, now));
  }

  renewOverride(overrideId: string, newExpiresAt: string, renewalDecisionId: string): HumanOverride {
    const override = this.overrides.get(overrideId);
    if (override === undefined) {
      throw new Error(`Override ${overrideId} not found`);
    }

    if (!isRenewable(override)) {
      throw new Error(`Override ${overrideId} is not renewable`);
    }

    const renewed = renewOverride(override, newExpiresAt, renewalDecisionId);
    this.overrides.set(overrideId, renewed);

    return renewed;
  }

  stats(): {
    total: number;
    active: number;
    expired: number;
    averageRenewals: number;
  } {
    const all = Array.from(this.overrides.values());
    const now = new Date();

    const active = all.filter((o) => !isExpired(o, now));
    const expired = all.filter((o) => isExpired(o, now));

    const totalRenewals = all.reduce((sum, o) => sum + o.renewalHistory.length, 0);

    return {
      total: all.length,
      active: active.length,
      expired: expired.length,
      averageRenewals: all.length > 0 ? totalRenewals / all.length : 0
    };
  }
}
