import { hashObject } from '../utils/hash.js';

export enum DecisionType {
  SYSTEM = 'system',
  HUMAN_OVERRIDE = 'human_override',
  POLICY_ENFORCED = 'policy_enforced',
  ECONOMIC = 'economic'
}

export interface Authority {
  readonly actor: string;
  readonly scope: string;
  readonly validUntil: string | null;
  readonly requiresRenewal: boolean;
}

export interface Decision {
  readonly decisionId: string;
  readonly decisionType: DecisionType;
  readonly action: string;
  readonly rationale: readonly string[];
  readonly beliefIds: readonly string[];
  readonly policyIds: readonly string[];
  readonly authority: Authority | null;
  readonly scope: string | null;
  readonly expiresAt: string | null;
  readonly createdAt: string;
  readonly metadata: Record<string, unknown>;
}

export interface DecisionInput {
  decisionType: DecisionType;
  action: string;
  rationale: string[];
  beliefIds?: string[];
  policyIds?: string[];
  authority?: Authority | null;
  scope?: string | null;
  expiresAt?: string | null;
  metadata?: Record<string, unknown>;
}

export function createDecision(input: DecisionInput): Decision {
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

export function isExpired(decision: Decision, now: Date = new Date()): boolean {
  if (decision.expiresAt === null) {
    return false;
  }

  const expiryDate = new Date(decision.expiresAt);
  return now >= expiryDate;
}

export function conflictsWith(decision1: Decision, decision2: Decision): boolean {
  if (decision1.scope !== decision2.scope || decision1.scope === null) {
    return false;
  }

  return decision1.action !== decision2.action;
}

export function decisionToDict(decision: Decision): Record<string, unknown> {
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

export function decisionFromDict(data: Record<string, unknown>): Decision {
  return {
    decisionId: data.decision_id as string,
    decisionType: data.decision_type as DecisionType,
    action: data.action as string,
    rationale: Object.freeze(data.rationale as string[]),
    beliefIds: Object.freeze((data.belief_ids as string[]) ?? []),
    policyIds: Object.freeze((data.policy_ids as string[]) ?? []),
    authority: data.authority as Authority | null,
    scope: data.scope as string | null,
    expiresAt: data.expires_at as string | null,
    createdAt: data.created_at as string,
    metadata: (data.metadata as Record<string, unknown>) ?? {}
  };
}
