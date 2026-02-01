export var PolicyType;
(function (PolicyType) {
    PolicyType["BELIEF"] = "belief";
    PolicyType["ECONOMIC"] = "economic";
    PolicyType["GOVERNANCE"] = "governance";
    PolicyType["SEMANTIC"] = "semantic";
})(PolicyType || (PolicyType = {}));
export var EnforcementMode;
(function (EnforcementMode) {
    EnforcementMode["OBSERVE"] = "observe";
    EnforcementMode["WARN"] = "warn";
    EnforcementMode["BLOCK"] = "block";
})(EnforcementMode || (EnforcementMode = {}));
export function createCognitivePolicy(input) {
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
export function policyToDict(policy) {
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
export function policyFromDict(data) {
    return {
        policyId: data.policy_id,
        policyType: data.policy_type,
        rule: data.rule,
        enforcement: data.enforcement,
        appliesTo: data.applies_to,
        priority: data.priority,
        metadata: data.metadata ?? {}
    };
}
//# sourceMappingURL=policy.js.map