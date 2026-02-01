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

export function createMeaningVersion(input: MeaningVersionInput): MeaningVersion {
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

export function isCompatibleWith(
  meaning1: MeaningVersion,
  meaning2: MeaningVersion
): boolean {
  if (meaning1.meaningId !== meaning2.meaningId) {
    return false;
  }

  const v1 = parseSemanticVersion(meaning1.version);
  const v2 = parseSemanticVersion(meaning2.version);

  return v1.major === v2.major;
}

function parseSemanticVersion(version: string): { major: number; minor: number; patch: number } {
  const parts = version.split('.').map(Number);
  return {
    major: parts[0] ?? 0,
    minor: parts[1] ?? 0,
    patch: parts[2] ?? 0
  };
}

export function meaningToDict(meaning: MeaningVersion): Record<string, unknown> {
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

export function meaningFromDict(data: Record<string, unknown>): MeaningVersion {
  return {
    meaningId: data.meaning_id as string,
    version: data.version as string,
    definition: data.definition as string,
    computation: data.computation as string | null,
    examples: Object.freeze((data.examples as Record<string, unknown>[]) ?? []),
    deprecated: data.deprecated as boolean,
    supersededBy: data.superseded_by as string | null,
    validFrom: data.valid_from as string,
    validUntil: data.valid_until as string | null,
    metadata: (data.metadata as Record<string, unknown>) ?? {}
  };
}
