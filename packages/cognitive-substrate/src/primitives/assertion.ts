import { hashObject } from '../utils/hash.js';

export interface Assertion {
  readonly assertionId: string;
  readonly claim: string;
  readonly evidenceIds: readonly string[];
  readonly transformation: string | null;
  readonly source: string;
  readonly timestamp: string;
  readonly metadata: Record<string, unknown>;
}

export interface AssertionInput {
  claim: string;
  evidenceIds: string[];
  transformation?: string | null;
  source: string;
  metadata?: Record<string, unknown>;
}

export function createAssertion(input: AssertionInput): Assertion {
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

export function assertionToDict(assertion: Assertion): Record<string, unknown> {
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

export function assertionFromDict(data: Record<string, unknown>): Assertion {
  return {
    assertionId: data.assertion_id as string,
    claim: data.claim as string,
    evidenceIds: Object.freeze(data.evidence_ids as string[]),
    transformation: data.transformation as string | null,
    source: data.source as string,
    timestamp: data.timestamp as string,
    metadata: (data.metadata as Record<string, unknown>) ?? {}
  };
}
