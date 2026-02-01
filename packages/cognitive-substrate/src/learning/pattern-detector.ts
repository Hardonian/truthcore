import { Decision } from '../primitives/decision.js';
import { HumanOverride } from '../governance/human-override.js';
import { generateId } from '../utils/hash.js';

export enum PatternType {
  FREQUENT_OVERRIDE = 'frequent_override',
  CONSISTENT_APPROVAL = 'consistent_approval',
  RISK_AVERSE = 'risk_averse',
  COST_SENSITIVE = 'cost_sensitive',
  VELOCITY_FOCUSED = 'velocity_focused'
}

export interface UsagePattern {
  readonly patternId: string;
  readonly patternType: PatternType;
  readonly frequency: string;
  readonly confidence: number;
  readonly firstSeen: string;
  readonly lastSeen: string;
  readonly exampleInstances: readonly string[];
  readonly metadata: Record<string, unknown>;
}

export interface UsagePatternInput {
  patternType: PatternType;
  frequency: string;
  confidence: number;
  firstSeen: string;
  lastSeen: string;
  exampleInstances: string[];
  metadata?: Record<string, unknown>;
}

export function createUsagePattern(input: UsagePatternInput): UsagePattern {
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
  private patterns: Map<string, UsagePattern> = new Map();
  private decisions: Decision[] = [];
  private overrides: HumanOverride[] = [];

  recordDecision(decision: Decision): void {
    this.decisions.push(decision);
  }

  recordOverride(override: HumanOverride): void {
    this.overrides.push(override);
  }

  detectUsagePatterns(_organizationId: string, lookbackDays: number = 30): UsagePattern[] {
    const now = new Date();
    const cutoff = new Date(now.getTime() - lookbackDays * 24 * 60 * 60 * 1000);

    const recentDecisions = this.decisions.filter(
      (d) => new Date(d.createdAt) >= cutoff
    );

    const recentOverrides = this.overrides.filter(
      (o) => new Date(o.createdAt) >= cutoff
    );

    const detected: UsagePattern[] = [];

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

  private detectFrequentOverrides(overrides: HumanOverride[]): UsagePattern | null {
    if (overrides.length < 5) {
      return null;
    }

    const overridesByRule = new Map<string, HumanOverride[]>();

    for (const override of overrides) {
      const ruleId = override.originalDecision.policyIds[0] ?? 'unknown';
      if (!overridesByRule.has(ruleId)) {
        overridesByRule.set(ruleId, []);
      }
      overridesByRule.get(ruleId)!.push(override);
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

  private detectConsistentApprovals(decisions: Decision[]): UsagePattern | null {
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

  private detectRiskAversion(decisions: Decision[]): UsagePattern | null {
    const riskRelatedDecisions = decisions.filter((d) =>
      d.rationale.some((r) => r.toLowerCase().includes('risk'))
    );

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

  private calculateFrequency(items: Array<{ createdAt: string }>): string {
    if (items.length < 2) {
      return 'rare';
    }

    const timestamps = items.map((item) => new Date(item.createdAt).getTime()).sort((a, b) => a - b);

    const intervals: number[] = [];
    for (let i = 1; i < timestamps.length; i++) {
      intervals.push(timestamps[i] - timestamps[i - 1]);
    }

    const avgInterval = intervals.reduce((sum, interval) => sum + interval, 0) / intervals.length;
    const avgDays = avgInterval / (1000 * 60 * 60 * 24);

    if (avgDays < 1) {
      return 'daily';
    } else if (avgDays < 7) {
      return 'weekly';
    } else if (avgDays < 30) {
      return 'monthly';
    }

    return 'rare';
  }

  getAllPatterns(): UsagePattern[] {
    return Array.from(this.patterns.values());
  }

  getPattern(patternId: string): UsagePattern | undefined {
    return this.patterns.get(patternId);
  }

  stats(): { totalPatterns: number; byType: Record<string, number> } {
    const patterns = this.getAllPatterns();

    const byType: Record<string, number> = {};

    for (const pattern of patterns) {
      byType[pattern.patternType] = (byType[pattern.patternType] ?? 0) + 1;
    }

    return {
      totalPatterns: patterns.length,
      byType
    };
  }
}
