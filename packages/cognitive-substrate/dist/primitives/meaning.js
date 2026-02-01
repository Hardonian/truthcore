export function createMeaningVersion(input) {
    return {
        meaningId: input.meaningId,
        version: input.version,
        definition: input.definition,
        computation: input.computation ?? null,
        examples: Object.freeze(input.examples ?? []),
        deprecated: input.deprecated ?? false,
        supersededBy: input.supersededBy ?? null,
        validFrom: input.validFrom ?? new Date().toISOString(),
        validUntil: input.validUntil ?? null,
        metadata: input.metadata ?? {}
    };
}
export function isCompatibleWith(meaning1, meaning2) {
    if (meaning1.meaningId !== meaning2.meaningId) {
        return false;
    }
    const v1 = parseSemanticVersion(meaning1.version);
    const v2 = parseSemanticVersion(meaning2.version);
    return v1.major === v2.major;
}
function parseSemanticVersion(version) {
    const parts = version.split('.').map(Number);
    return {
        major: parts[0] ?? 0,
        minor: parts[1] ?? 0,
        patch: parts[2] ?? 0
    };
}
export function meaningToDict(meaning) {
    return {
        meaning_id: meaning.meaningId,
        version: meaning.version,
        definition: meaning.definition,
        computation: meaning.computation,
        examples: [...meaning.examples],
        deprecated: meaning.deprecated,
        superseded_by: meaning.supersededBy,
        valid_from: meaning.validFrom,
        valid_until: meaning.validUntil,
        metadata: meaning.metadata
    };
}
export function meaningFromDict(data) {
    return {
        meaningId: data.meaning_id,
        version: data.version,
        definition: data.definition,
        computation: data.computation,
        examples: Object.freeze(data.examples ?? []),
        deprecated: data.deprecated,
        supersededBy: data.superseded_by,
        validFrom: data.valid_from,
        validUntil: data.valid_until,
        metadata: data.metadata ?? {}
    };
}
//# sourceMappingURL=meaning.js.map