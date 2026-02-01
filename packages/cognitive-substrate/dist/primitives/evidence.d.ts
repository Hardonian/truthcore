export declare enum EvidenceType {
    RAW = "raw",
    DERIVED = "derived",
    HUMAN_INPUT = "human_input",
    EXTERNAL = "external"
}
export interface Evidence {
    readonly evidenceId: string;
    readonly evidenceType: EvidenceType;
    readonly contentHash: string;
    readonly source: string;
    readonly timestamp: string;
    readonly validityPeriod: number | null;
    readonly metadata: Record<string, unknown>;
}
export interface EvidenceInput {
    evidenceType: EvidenceType;
    content: unknown;
    source: string;
    validityPeriod?: number | null;
    metadata?: Record<string, unknown>;
}
export declare function createEvidence(input: EvidenceInput): Evidence;
export declare function isStale(evidence: Evidence, currentTime?: Date): boolean;
export declare function evidenceToDict(evidence: Evidence): Record<string, unknown>;
export declare function evidenceFromDict(data: Record<string, unknown>): Evidence;
//# sourceMappingURL=evidence.d.ts.map