import { generateId } from '../utils/hash.js';
export var PatternType;
(function (PatternType) {
    PatternType["FREQUENT_OVERRIDE"] = "frequent_override";
    PatternType["CONSISTENT_APPROVAL"] = "consistent_approval";
    PatternType["RISK_AVERSE"] = "risk_averse";
    PatternType["COST_SENSITIVE"] = "cost_sensitive";
    PatternType["VELOCITY_FOCUSED"] = "velocity_focused";
})(PatternType || (PatternType = {}));
export function createUsagePattern(input) {
    const patternId = generateId('pattern', {
        type: input.patternType,
        frequency: input.frequency,
        firstSeen: input.firstSeen
    });
    return {
        patternId,
        patternType: input.patternType,
        frequency: input.frequency,
        confidence: input.confidence,
        firstSeen: input.firstSeen,
        lastSeen: input.lastSeen,
        exampleInstances: Object.freeze([...input.exampleInstances]),
        metadata: input.metadata ?? {}
    };
}
export class PatternDetector {
    patterns = new Map();
    decisions = [];
    overrides = [];
    recordDecision(decision) {
        this.decisions.push(decision);
    }
    recordOverride(override) {
        this.overrides.push(override);
    }
    detectUsagePatterns(_organizationId, lookbackDays = 30) {
        const now = new Date();
        const cutoff = new Date(now.getTime() - lookbackDays * 24 * 60 * 60 * 1000);
        const recentDecisions = this.decisions.filter((d) => new Date(d.createdAt) >= cutoff);
        const recentOverrides = this.overrides.filter((o) => new Date(o.createdAt) >= cutoff);
        const detected = [];
        const frequentOverridePattern = this.detectFrequentOverrides(recentOverrides);
        if (frequentOverridePattern !== null) {
            this.patterns.set(frequentOverridePattern.patternId, frequentOverridePattern);
            detected.push(frequentOverridePattern);
        }
        const consistentApprovalPattern = this.detectConsistentApprovals(recentDecisions);
        if (consistentApprovalPattern !== null) {
            this.patterns.set(consistentApprovalPattern.patternId, consistentApprovalPattern);
            detected.push(consistentApprovalPattern);
        }
        const riskAversionPattern = this.detectRiskAversion(recentDecisions);
        if (riskAversionPattern !== null) {
            this.patterns.set(riskAversionPattern.patternId, riskAversionPattern);
            detected.push(riskAversionPattern);
        }
        return detected;
    }
    detectFrequentOverrides(overrides) {
        if (overrides.length < 5) {
            return null;
        }
        const overridesByRule = new Map();
        for (const override of overrides) {
            const ruleId = override.originalDecision.policyIds[0] ?? 'unknown';
            if (!overridesByRule.has(ruleId)) {
                overridesByRule.set(ruleId, []);
            }
            overridesByRule.get(ruleId).push(override);
        }
        for (const [ruleId, ruleOverrides] of overridesByRule.entries()) {
            if (ruleOverrides.length >= 3) {
                const frequency = this.calculateFrequency(ruleOverrides);
                return createUsagePattern({
                    patternType: PatternType.FREQUENT_OVERRIDE,
                    frequency,
                    confidence: Math.min(1.0, ruleOverrides.length / 10),
                    firstSeen: ruleOverrides[0].createdAt,
                    lastSeen: ruleOverrides[ruleOverrides.length - 1].createdAt,
                    exampleInstances: ruleOverrides.slice(0, 5).map((o) => o.overrideId),
                    metadata: {
                        rule_id: ruleId,
                        override_count: ruleOverrides.length
                    }
                });
            }
        }
        return null;
    }
    detectConsistentApprovals(decisions) {
        const approvals = decisions.filter((d) => d.action === 'approve' || d.action === 'ship');
        if (approvals.length < 10) {
            return null;
        }
        const approvalRate = approvals.length / decisions.length;
        if (approvalRate >= 0.9) {
            return createUsagePattern({
                patternType: PatternType.CONSISTENT_APPROVAL,
                frequency: 'daily',
                confidence: approvalRate,
                firstSeen: decisions[0].createdAt,
                lastSeen: decisions[decisions.length - 1].createdAt,
                exampleInstances: approvals.slice(0, 5).map((d) => d.decisionId),
                metadata: {
                    approval_rate: approvalRate,
                    total_decisions: decisions.length
                }
            });
        }
        return null;
    }
    detectRiskAversion(decisions) {
        const riskRelatedDecisions = decisions.filter((d) => d.rationale.some((r) => r.toLowerCase().includes('risk')));
        if (riskRelatedDecisions.length < 5) {
            return null;
        }
        const rejections = riskRelatedDecisions.filter((d) => d.action === 'reject' || d.action === 'block');
        const rejectionRate = rejections.length / riskRelatedDecisions.length;
        if (rejectionRate >= 0.7) {
            return createUsagePattern({
                patternType: PatternType.RISK_AVERSE,
                frequency: this.calculateFrequency(riskRelatedDecisions),
                confidence: rejectionRate,
                firstSeen: riskRelatedDecisions[0].createdAt,
                lastSeen: riskRelatedDecisions[riskRelatedDecisions.length - 1].createdAt,
                exampleInstances: rejections.slice(0, 5).map((d) => d.decisionId),
                metadata: {
                    rejection_rate: rejectionRate,
                    risk_decisions: riskRelatedDecisions.length
                }
            });
        }
        return null;
    }
    calculateFrequency(items) {
        if (items.length < 2) {
            return 'rare';
        }
        const timestamps = items.map((item) => new Date(item.createdAt).getTime()).sort((a, b) => a - b);
        const intervals = [];
        for (let i = 1; i < timestamps.length; i++) {
            intervals.push(timestamps[i] - timestamps[i - 1]);
        }
        const avgInterval = intervals.reduce((sum, interval) => sum + interval, 0) / intervals.length;
        const avgDays = avgInterval / (1000 * 60 * 60 * 24);
        if (avgDays < 1) {
            return 'daily';
        }
        else if (avgDays < 7) {
            return 'weekly';
        }
        else if (avgDays < 30) {
            return 'monthly';
        }
        return 'rare';
    }
    getAllPatterns() {
        return Array.from(this.patterns.values());
    }
    getPattern(patternId) {
        return this.patterns.get(patternId);
    }
    stats() {
        const patterns = this.getAllPatterns();
        const byType = {};
        for (const pattern of patterns) {
            byType[pattern.patternType] = (byType[pattern.patternType] ?? 0) + 1;
        }
        return {
            totalPatterns: patterns.length,
            byType
        };
    }
}
//# sourceMappingURL=pattern-detector.js.map