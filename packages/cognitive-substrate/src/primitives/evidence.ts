import { hashObject } from '../utils/hash.js';

export enum EvidenceType {
  RAW = 'raw',
  DERIVED = 'derived',
  HUMAN_INPUT = 'human_input',
  EXTERNAL = 'external'
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

export function createEvidence(input: EvidenceInput): Evidence {
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

export function isStale(evidence: Evidence, currentTime: Date = new Date()): boolean {
  if (evidence.validityPeriod === null) {
    return false;
  }

  const createdAt = new Date(evidence.timestamp);
  const expiresAt = new Date(createdAt.getTime() + evidence.validityPeriod * 1000);

  return currentTime >= expiresAt;
}

export function evidenceToDict(evidence: Evidence): Record<string, unknown> {
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

export function evidenceFromDict(data: Record<string, unknown>): Evidence {
  return {
    evidenceId: data.evidence_id as string,
    evidenceType: data.evidence_type as EvidenceType,
    contentHash: data.content_hash as string,
    source: data.source as string,
    timestamp: data.timestamp as string,
    validityPeriod: data.validity_period as number | null,
    metadata: (data.metadata as Record<string, unknown>) ?? {}
  };
}
