import { hashObject } from '../utils/hash.js';
export var EvidenceType;
(function (EvidenceType) {
    EvidenceType["RAW"] = "raw";
    EvidenceType["DERIVED"] = "derived";
    EvidenceType["HUMAN_INPUT"] = "human_input";
    EvidenceType["EXTERNAL"] = "external";
})(EvidenceType || (EvidenceType = {}));
export function createEvidence(input) {
    const timestamp = new Date().toISOString();
    const contentHash = hashObject(input.content);
    const evidenceId = hashObject({
        type: input.evidenceType,
        contentHash,
        source: input.source,
        timestamp
    });
    return {
        evidenceId,
        evidenceType: input.evidenceType,
        contentHash,
        source: input.source,
        timestamp,
        validityPeriod: input.validityPeriod ?? null,
        metadata: input.metadata ?? {}
    };
}
export function isStale(evidence, currentTime = new Date()) {
    if (evidence.validityPeriod === null) {
        return false;
    }
    const createdAt = new Date(evidence.timestamp);
    const expiresAt = new Date(createdAt.getTime() + evidence.validityPeriod * 1000);
    return currentTime >= expiresAt;
}
export function evidenceToDict(evidence) {
    return {
        evidence_id: evidence.evidenceId,
        evidence_type: evidence.evidenceType,
        content_hash: evidence.contentHash,
        source: evidence.source,
        timestamp: evidence.timestamp,
        validity_period: evidence.validityPeriod,
        metadata: evidence.metadata
    };
}
export function evidenceFromDict(data) {
    return {
        evidenceId: data.evidence_id,
        evidenceType: data.evidence_type,
        contentHash: data.content_hash,
        source: data.source,
        timestamp: data.timestamp,
        validityPeriod: data.validity_period,
        metadata: data.metadata ?? {}
    };
}
//# sourceMappingURL=evidence.js.map