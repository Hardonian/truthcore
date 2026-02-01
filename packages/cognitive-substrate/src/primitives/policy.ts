export enum PolicyType {
  BELIEF = 'belief',
  ECONOMIC = 'economic',
  GOVERNANCE = 'governance',
  SEMANTIC = 'semantic'
}

export enum EnforcementMode {
  OBSERVE = 'observe',
  WARN = 'warn',
  BLOCK = 'block'
}

export interface CognitivePolicy {
  readonly policyId: string;
  readonly policyType: PolicyType;
  readonly rule: Record<string, unknown>;
  readonly enforcement: EnforcementMode;
  readonly appliesTo: string;
  readonly priority: number;
  readonly metadata: Record<string, unknown>;
}

export interface CognitivePolicyInput {
  policyId: string;
  policyType: PolicyType;
  rule: Record<string, unknown>;
  enforcement?: EnforcementMode;
  appliesTo?: string;
  priority?: number;
  metadata?: Record<string, unknown>;
}

export function createCognitivePolicy(input: CognitivePolicyInput): CognitivePolicy {
  return {
    policyId: input.policyId,
    policyType: input.policyType,
    rule: input.rule,
    enforcement: input.enforcement ?? EnforcementMode.OBSERVE,
    appliesTo: input.appliesTo ?? '*',
    priority: input.priority ?? 0,
    metadata: input.metadata ?? {}
  };
}

export function policyToDict(policy: CognitivePolicy): Record<string, unknown> {
  return {
    policy_id: policy.policyId,
    policy_type: policy.policyType,
    rule: policy.rule,
    enforcement: policy.enforcement,
    applies_to: policy.appliesTo,
    priority: policy.priority,
    metadata: policy.metadata
  };
}

export function policyFromDict(data: Record<string, unknown>): CognitivePolicy {
  return {
    policyId: data.policy_id as string,
    policyType: data.policy_type as PolicyType,
    rule: data.rule as Record<string, unknown>,
    enforcement: data.enforcement as EnforcementMode,
    appliesTo: data.applies_to as string,
    priority: data.priority as number,
    metadata: (data.metadata as Record<string, unknown>) ?? {}
  };
}
