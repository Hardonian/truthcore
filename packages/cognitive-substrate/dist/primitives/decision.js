import { hashObject } from '../utils/hash.js';
export var DecisionType;
(function (DecisionType) {
    DecisionType["SYSTEM"] = "system";
    DecisionType["HUMAN_OVERRIDE"] = "human_override";
    DecisionType["POLICY_ENFORCED"] = "policy_enforced";
    DecisionType["ECONOMIC"] = "economic";
})(DecisionType || (DecisionType = {}));
export function createDecision(input) {
    const createdAt = new Date().toISOString();
    const decisionId = hashObject({
        type: input.decisionType,
        action: input.action,
        rationale: input.rationale,
        createdAt
    });
    return {
        decisionId,
        decisionType: input.decisionType,
        action: input.action,
        rationale: Object.freeze([...input.rationale]),
        beliefIds: Object.freeze(input.beliefIds ?? []),
        policyIds: Object.freeze(input.policyIds ?? []),
        authority: input.authority ?? null,
        scope: input.scope ?? null,
        expiresAt: input.expiresAt ?? null,
        createdAt,
        metadata: input.metadata ?? {}
    };
}
export function isExpired(decision, now = new Date()) {
    if (decision.expiresAt === null) {
        return false;
    }
    const expiryDate = new Date(decision.expiresAt);
    return now >= expiryDate;
}
export function conflictsWith(decision1, decision2) {
    if (decision1.scope !== decision2.scope || decision1.scope === null) {
        return false;
    }
    return decision1.action !== decision2.action;
}
export function decisionToDict(decision) {
    return {
        decision_id: decision.decisionId,
        decision_type: decision.decisionType,
        action: decision.action,
        rationale: [...decision.rationale],
        belief_ids: [...decision.beliefIds],
        policy_ids: [...decision.policyIds],
        authority: decision.authority,
        scope: decision.scope,
        expires_at: decision.expiresAt,
        created_at: decision.createdAt,
        metadata: decision.metadata
    };
}
export function decisionFromDict(data) {
    return {
        decisionId: data.decision_id,
        decisionType: data.decision_type,
        action: data.action,
        rationale: Object.freeze(data.rationale),
        beliefIds: Object.freeze(data.belief_ids ?? []),
        policyIds: Object.freeze(data.policy_ids ?? []),
        authority: data.authority,
        scope: data.scope,
        expiresAt: data.expires_at,
        createdAt: data.created_at,
        metadata: data.metadata ?? {}
    };
}
//# sourceMappingURL=decision.js.map