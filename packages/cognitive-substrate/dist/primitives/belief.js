import { generateId } from '../utils/hash.js';
export function createBelief(input) {
    const now = new Date().toISOString();
    const beliefId = generateId('belief', {
        assertionId: input.assertionId,
        timestamp: now
    });
    if (input.confidence < 0 || input.confidence > 1) {
        throw new Error(`Confidence must be between 0 and 1, got ${input.confidence}`);
    }
    return {
        beliefId,
        assertionId: input.assertionId,
        confidence: input.confidence,
        version: 1,
        createdAt: now,
        updatedAt: now,
        decayRate: input.decayRate ?? 0.0,
        validityUntil: input.validityUntil ?? null,
        upstreamDependencies: Object.freeze(input.upstreamDependencies ?? []),
        metadata: input.metadata ?? {}
    };
}
export function currentConfidence(belief, now = new Date()) {
    if (!isValid(belief, now)) {
        return 0.0;
    }
    if (belief.decayRate === 0) {
        return belief.confidence;
    }
    const createdAt = new Date(belief.createdAt);
    const deltaDays = (now.getTime() - createdAt.getTime()) / (1000 * 60 * 60 * 24);
    const decayed = belief.confidence * Math.exp(-belief.decayRate * deltaDays);
    return Math.max(0, Math.min(1, decayed));
}
export function isValid(belief, now = new Date()) {
    if (belief.validityUntil === null) {
        return true;
    }
    const expiryDate = new Date(belief.validityUntil);
    return now < expiryDate;
}
export function updateBelief(belief, newConfidence, metadata) {
    if (newConfidence < 0 || newConfidence > 1) {
        throw new Error(`Confidence must be between 0 and 1, got ${newConfidence}`);
    }
    return {
        ...belief,
        confidence: newConfidence,
        version: belief.version + 1,
        updatedAt: new Date().toISOString(),
        metadata: metadata ? { ...belief.metadata, ...metadata } : belief.metadata
    };
}
export function beliefToDict(belief) {
    return {
        belief_id: belief.beliefId,
        assertion_id: belief.assertionId,
        confidence: belief.confidence,
        version: belief.version,
        created_at: belief.createdAt,
        updated_at: belief.updatedAt,
        decay_rate: belief.decayRate,
        validity_until: belief.validityUntil,
        upstream_dependencies: [...belief.upstreamDependencies],
        metadata: belief.metadata
    };
}
export function beliefFromDict(data) {
    return {
        beliefId: data.belief_id,
        assertionId: data.assertion_id,
        confidence: data.confidence,
        version: data.version,
        createdAt: data.created_at,
        updatedAt: data.updated_at,
        decayRate: data.decay_rate,
        validityUntil: data.validity_until,
        upstreamDependencies: Object.freeze(data.upstream_dependencies),
        metadata: data.metadata ?? {}
    };
}
//# sourceMappingURL=belief.js.map