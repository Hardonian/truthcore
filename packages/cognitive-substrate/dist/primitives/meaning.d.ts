export interface MeaningVersion {
    readonly meaningId: string;
    readonly version: string;
    readonly definition: string;
    readonly computation: string | null;
    readonly examples: readonly Record<string, unknown>[];
    readonly deprecated: boolean;
    readonly supersededBy: string | null;
    readonly validFrom: string;
    readonly validUntil: string | null;
    readonly metadata: Record<string, unknown>;
}
export interface MeaningVersionInput {
    meaningId: string;
    version: string;
    definition: string;
    computation?: string | null;
    examples?: Record<string, unknown>[];
    deprecated?: boolean;
    supersededBy?: string | null;
    validFrom?: string;
    validUntil?: string | null;
    metadata?: Record<string, unknown>;
}
export declare function createMeaningVersion(input: MeaningVersionInput): MeaningVersion;
export declare function isCompatibleWith(meaning1: MeaningVersion, meaning2: MeaningVersion): boolean;
export declare function meaningToDict(meaning: MeaningVersion): Record<string, unknown>;
export declare function meaningFromDict(data: Record<string, unknown>): MeaningVersion;
//# sourceMappingURL=meaning.d.ts.map