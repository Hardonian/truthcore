import { currentConfidence } from '../primitives/belief.js';
import { isCompatibleWith } from '../primitives/meaning.js';
import { generateId } from '../utils/hash.js';
export var ContradictionType;
(function (ContradictionType) {
    ContradictionType["ASSERTION_CONFLICT"] = "assertion_conflict";
    ContradictionType["BELIEF_DIVERGENCE"] = "belief_divergence";
    ContradictionType["POLICY_CONFLICT"] = "policy_conflict";
    ContradictionType["SEMANTIC_DRIFT"] = "semantic_drift";
    ContradictionType["ECONOMIC_VIOLATION"] = "economic_violation";
})(ContradictionType || (ContradictionType = {}));
export var Severity;
(function (Severity) {
    Severity["BLOCKER"] = "blocker";
    Severity["HIGH"] = "high";
    Severity["MEDIUM"] = "medium";
    Severity["LOW"] = "low";
    Severity["INFO"] = "info";
})(Severity || (Severity = {}));
export var ResolutionStatus;
(function (ResolutionStatus) {
    ResolutionStatus["UNRESOLVED"] = "unresolved";
    ResolutionStatus["HUMAN_OVERRIDE"] = "human_override";
    ResolutionStatus["POLICY_RULED"] = "policy_ruled";
    ResolutionStatus["IGNORED"] = "ignored";
})(ResolutionStatus || (ResolutionStatus = {}));
export function createContradiction(input) {
    const detectedAt = new Date().toISOString();
    const contradictionId = generateId('contradiction', {
        type: input.contradictionType,
        items: input.conflictingItems,
        timestamp: detectedAt
    });
    return {
        contradictionId,
        contradictionType: input.contradictionType,
        conflictingItems: Object.freeze([...input.conflictingItems]),
        severity: input.severity,
        explanation: input.explanation,
        detectedAt,
        resolutionStatus: ResolutionStatus.UNRESOLVED,
        metadata: input.metadata ?? {}
    };
}
export class ContradictionDetector {
    graph;
    // Belief engine for future belief-based contradiction detection
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    _beliefEngine;
    contradictions = new Map();
    constructor(graph, beliefEngine) {
        this.graph = graph;
        this._beliefEngine = beliefEngine;
    }
    detectAssertionConflicts() {
        const detected = [];
        const assertions = this.graph.getAllAssertions();
        const claimGroups = new Map();
        for (const assertion of assertions) {
            const normalized = this.normalizeClaim(assertion.claim);
            if (!claimGroups.has(normalized)) {
                claimGroups.set(normalized, []);
            }
            claimGroups.get(normalized).push(assertion);
        }
        for (const [claim, group] of claimGroups.entries()) {
            if (group.length > 1) {
                const hasConflict = this.detectClaimConflict(group);
                if (hasConflict) {
                    const contradiction = createContradiction({
                        contradictionType: ContradictionType.ASSERTION_CONFLICT,
                        conflictingItems: group.map((a) => a.assertionId),
                        severity: Severity.HIGH,
                        explanation: `Multiple conflicting assertions about: ${claim}`
                    });
                    this.contradictions.set(contradiction.contradictionId, contradiction);
                    detected.push(contradiction);
                }
            }
        }
        return detected;
    }
    normalizeClaim(claim) {
        return claim.toLowerCase().trim().replace(/\s+/g, ' ');
    }
    detectClaimConflict(assertions) {
        if (assertions.length < 2) {
            return false;
        }
        for (let i = 0; i < assertions.length; i++) {
            for (let j = i + 1; j < assertions.length; j++) {
                if (assertions[i].source !== assertions[j].source) {
                    return true;
                }
            }
        }
        return false;
    }
    detectBeliefDivergence(systemBelief, humanDecision, _threshold = 0.3) {
        const systemConfidence = currentConfidence(systemBelief);
        const isSystemHighConfidence = systemConfidence >= 0.8;
        const humanOverridesSystem = humanDecision.decisionType === 'human_override';
        if (isSystemHighConfidence && humanOverridesSystem) {
            const contradiction = createContradiction({
                contradictionType: ContradictionType.BELIEF_DIVERGENCE,
                conflictingItems: [systemBelief.beliefId, humanDecision.decisionId],
                severity: systemConfidence >= 0.9 ? Severity.HIGH : Severity.MEDIUM,
                explanation: `System has high confidence (${systemConfidence.toFixed(2)}) but human overrode decision`,
                metadata: {
                    system_confidence: systemConfidence,
                    decision_action: humanDecision.action
                }
            });
            this.contradictions.set(contradiction.contradictionId, contradiction);
            return contradiction;
        }
        return null;
    }
    detectPolicyConflicts(policies) {
        const detected = [];
        for (let i = 0; i < policies.length; i++) {
            for (let j = i + 1; j < policies.length; j++) {
                const p1 = policies[i];
                const p2 = policies[j];
                if (this.policiesConflict(p1, p2)) {
                    const contradiction = createContradiction({
                        contradictionType: ContradictionType.POLICY_CONFLICT,
                        conflictingItems: [p1.policyId, p2.policyId],
                        severity: Severity.MEDIUM,
                        explanation: `Policies ${p1.policyId} and ${p2.policyId} have conflicting rules`,
                        metadata: {
                            policy1_type: p1.policyType,
                            policy2_type: p2.policyType
                        }
                    });
                    this.contradictions.set(contradiction.contradictionId, contradiction);
                    detected.push(contradiction);
                }
            }
        }
        return detected;
    }
    policiesConflict(p1, p2) {
        if (p1.appliesTo !== p2.appliesTo && p1.appliesTo !== '*' && p2.appliesTo !== '*') {
            return false;
        }
        return p1.enforcement !== p2.enforcement && p1.policyType === p2.policyType;
    }
    detectSemanticDrift(meanings) {
        const detected = [];
        const meaningGroups = new Map();
        for (const meaning of meanings) {
            if (!meaningGroups.has(meaning.meaningId)) {
                meaningGroups.set(meaning.meaningId, []);
            }
            meaningGroups.get(meaning.meaningId).push(meaning);
        }
        for (const [meaningId, versions] of meaningGroups.entries()) {
            if (versions.length > 1) {
                const activeVersions = versions.filter((v) => !v.deprecated);
                if (activeVersions.length > 1) {
                    const incompatible = this.findIncompatibleVersions(activeVersions);
                    if (incompatible.length > 0) {
                        const contradiction = createContradiction({
                            contradictionType: ContradictionType.SEMANTIC_DRIFT,
                            conflictingItems: incompatible.map((v) => `${v.meaningId}@${v.version}`),
                            severity: Severity.MEDIUM,
                            explanation: `Multiple incompatible active versions of ${meaningId}`,
                            metadata: {
                                versions: incompatible.map((v) => v.version)
                            }
                        });
                        this.contradictions.set(contradiction.contradictionId, contradiction);
                        detected.push(contradiction);
                    }
                }
            }
        }
        return detected;
    }
    findIncompatibleVersions(versions) {
        const incompatible = [];
        for (let i = 0; i < versions.length; i++) {
            for (let j = i + 1; j < versions.length; j++) {
                if (!isCompatibleWith(versions[i], versions[j])) {
                    if (!incompatible.includes(versions[i])) {
                        incompatible.push(versions[i]);
                    }
                    if (!incompatible.includes(versions[j])) {
                        incompatible.push(versions[j]);
                    }
                }
            }
        }
        return incompatible;
    }
    getAllContradictions() {
        return Array.from(this.contradictions.values());
    }
    getContradiction(contradictionId) {
        return this.contradictions.get(contradictionId);
    }
    resolveContradiction(contradictionId, status) {
        const contradiction = this.contradictions.get(contradictionId);
        if (contradiction !== undefined) {
            contradiction.resolutionStatus = status;
        }
    }
    stats() {
        const contradictions = this.getAllContradictions();
        const bySeverity = {};
        const byType = {};
        for (const c of contradictions) {
            bySeverity[c.severity] = (bySeverity[c.severity] ?? 0) + 1;
            byType[c.contradictionType] = (byType[c.contradictionType] ?? 0) + 1;
        }
        return {
            total: contradictions.length,
            unresolved: contradictions.filter((c) => c.resolutionStatus === ResolutionStatus.UNRESOLVED).length,
            bySeverity,
            byType
        };
    }
}
//# sourceMappingURL=contradiction.js.map