import { generateId } from '../utils/hash.js';
export var ScopeType;
(function (ScopeType) {
    ScopeType["SINGLE_DECISION"] = "single_decision";
    ScopeType["RULE"] = "rule";
    ScopeType["ORG"] = "org";
    ScopeType["TIME_WINDOW"] = "time_window";
})(ScopeType || (ScopeType = {}));
export function createHumanOverride(input) {
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
export function isExpired(override, now = new Date()) {
    const expiryDate = new Date(override.expiresAt);
    return now >= expiryDate;
}
export function isRenewable(override) {
    return override.requiresRenewal;
}
export function renewOverride(override, newExpiresAt, renewalDecisionId) {
    return {
        ...override,
        expiresAt: newExpiresAt,
        renewalHistory: Object.freeze([...override.renewalHistory, renewalDecisionId])
    };
}
export class HumanOverrideManager {
    overrides = new Map();
    createOverride(input) {
        const override = createHumanOverride(input);
        this.overrides.set(override.overrideId, override);
        return override;
    }
    getOverride(overrideId) {
        return this.overrides.get(overrideId);
    }
    getActiveOverrides(now = new Date()) {
        return Array.from(this.overrides.values()).filter((o) => !isExpired(o, now));
    }
    getExpiredOverrides(now = new Date()) {
        return Array.from(this.overrides.values()).filter((o) => isExpired(o, now));
    }
    renewOverride(overrideId, newExpiresAt, renewalDecisionId) {
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
    stats() {
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
//# sourceMappingURL=human-override.js.map