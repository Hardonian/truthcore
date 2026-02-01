import { hashObject } from '../utils/hash.js';
export function createAssertion(input) {
    const timestamp = new Date().toISOString();
    const assertionId = hashObject({
        claim: input.claim,
        evidenceIds: input.evidenceIds,
        transformation: input.transformation,
        source: input.source,
        timestamp
    });
    return {
        assertionId,
        claim: input.claim,
        evidenceIds: Object.freeze([...input.evidenceIds]),
        transformation: input.transformation ?? null,
        source: input.source,
        timestamp,
        metadata: input.metadata ?? {}
    };
}
export function assertionToDict(assertion) {
    return {
        assertion_id: assertion.assertionId,
        claim: assertion.claim,
        evidence_ids: [...assertion.evidenceIds],
        transformation: assertion.transformation,
        source: assertion.source,
        timestamp: assertion.timestamp,
        metadata: assertion.metadata
    };
}
export function assertionFromDict(data) {
    return {
        assertionId: data.assertion_id,
        claim: data.claim,
        evidenceIds: Object.freeze(data.evidence_ids),
        transformation: data.transformation,
        source: data.source,
        timestamp: data.timestamp,
        metadata: data.metadata ?? {}
    };
}
//# sourceMappingURL=assertion.js.map