import { BeliefEngine } from '../graph/belief-engine.js';
import { ContradictionDetector } from '../graph/contradiction.js';
import { HumanOverrideManager } from '../governance/human-override.js';
import { EconomicSignalProcessor } from '../economic/signal-processor.js';
import { PatternDetector } from '../learning/pattern-detector.js';
import { StageGate } from '../learning/stage-gate.js';

export interface CognitiveSummary {
  readonly generatedAt: string;
  readonly organizationId: string;
  readonly periodDays: number;
  readonly beliefHealth: BeliefHealthSummary;
  readonly contradictions: ContradictionSummary;
  readonly humanOverrides: OverrideSummary;
  readonly economic: EconomicSummary;
  readonly organizational: OrganizationalSummary;
}

export interface BeliefHealthSummary {
  readonly totalBeliefs: number;
  readonly highConfidence: number;
  readonly highConfidencePercent: number;
  readonly lowConfidence: number;
  readonly lowConfidencePercent: number;
  readonly decayedBeliefs: number;
  readonly decayedPercent: number;
  readonly averageConfidence: number;
}

export interface ContradictionSummary {
  readonly total: number;
  readonly resolved: number;
  readonly unresolved: number;
  readonly bySeverity: Record<string, number>;
  readonly topContradictions: Array<{ type: string; count: number }>;
}

export interface OverrideSummary {
  readonly total: number;
  readonly active: number;
  readonly expired: number;
  readonly averageRenewals: number;
  readonly mostOverriddenRule: { ruleId: string; count: number } | null;
}

export interface EconomicSummary {
  readonly totalCost: number;
  readonly averageCostPerDecision: number;
  readonly budgetPressure: string;
  readonly budgetUtilization: number | null;
  readonly highCostDecisions: number;
}

export interface OrganizationalSummary {
  readonly detectedStage: string;
  readonly stageConfidence: number;
  readonly keyIndicators: readonly string[];
  readonly toolingMismatch: string | null;
  readonly recommendation: string | null;
}

export class ReportGenerator {
  generateCognitiveSummary(
    organizationId: string,
    periodDays: number,
    beliefEngine: BeliefEngine,
    contradictionDetector: ContradictionDetector,
    overrideManager: HumanOverrideManager,
    economicProcessor: EconomicSignalProcessor,
    _patternDetector: PatternDetector,
    stageGate: StageGate | null
  ): CognitiveSummary {
    const generatedAt = new Date().toISOString();

    const beliefStats = beliefEngine.stats();
    const beliefHealth: BeliefHealthSummary = {
      totalBeliefs: beliefStats.total,
      highConfidence: beliefStats.highConfidence,
      highConfidencePercent: beliefStats.total > 0 ? (beliefStats.highConfidence / beliefStats.total) * 100 : 0,
      lowConfidence: beliefStats.lowConfidence,
      lowConfidencePercent: beliefStats.total > 0 ? (beliefStats.lowConfidence / beliefStats.total) * 100 : 0,
      decayedBeliefs: 0,
      decayedPercent: 0,
      averageConfidence: beliefStats.averageConfidence
    };

    const contradictionStats = contradictionDetector.stats();
    const contradictions: ContradictionSummary = {
      total: contradictionStats.total,
      resolved: contradictionStats.total - contradictionStats.unresolved,
      unresolved: contradictionStats.unresolved,
      bySeverity: contradictionStats.bySeverity,
      topContradictions: Object.entries(contradictionStats.byType).map(([type, count]) => ({ type, count }))
    };

    const overrideStats = overrideManager.stats();
    const overrides: OverrideSummary = {
      total: overrideStats.total,
      active: overrideStats.active,
      expired: overrideStats.expired,
      averageRenewals: overrideStats.averageRenewals,
      mostOverriddenRule: null
    };

    const economicStats = economicProcessor.stats();
    const economic: EconomicSummary = {
      totalCost: economicStats.totalCost,
      averageCostPerDecision: economicStats.totalSignals > 0 ? economicStats.totalCost / economicStats.totalSignals : 0,
      budgetPressure: 'UNKNOWN',
      budgetUtilization: null,
      highCostDecisions: 0
    };

    const organizational: OrganizationalSummary = {
      detectedStage: stageGate?.stage ?? 'UNKNOWN',
      stageConfidence: stageGate?.confidence ?? 0,
      keyIndicators: stageGate?.indicators ?? [],
      toolingMismatch: null,
      recommendation: null
    };

    return {
      generatedAt,
      organizationId,
      periodDays,
      beliefHealth,
      contradictions,
      humanOverrides: overrides,
      economic,
      organizational
    };
  }

  generateMarkdownReport(summary: CognitiveSummary): string {
    const lines: string[] = [];

    lines.push('# Cognitive Substrate Report');
    lines.push('');
    lines.push(`**Generated:** ${summary.generatedAt}`);
    lines.push(`**Organization:** ${summary.organizationId}`);
    lines.push(`**Period:** Last ${summary.periodDays} days`);
    lines.push('');

    lines.push('## Belief Health');
    lines.push(`- Total beliefs: ${summary.beliefHealth.totalBeliefs}`);
    lines.push(`- High confidence (>0.8): ${summary.beliefHealth.highConfidence} (${summary.beliefHealth.highConfidencePercent.toFixed(1)}%)`);
    lines.push(`- Low confidence (<0.5): ${summary.beliefHealth.lowConfidence} (${summary.beliefHealth.lowConfidencePercent.toFixed(1)}%)`);
    lines.push(`- Average confidence: ${summary.beliefHealth.averageConfidence.toFixed(2)}`);
    lines.push('');

    lines.push('## Contradictions');
    lines.push(`- Total detected: ${summary.contradictions.total}`);
    lines.push(`- Resolved: ${summary.contradictions.resolved}`);
    lines.push(`- Unresolved: ${summary.contradictions.unresolved}`);

    if (summary.contradictions.topContradictions.length > 0) {
      lines.push('- Top contradictions:');
      for (const { type, count } of summary.contradictions.topContradictions.slice(0, 3)) {
        lines.push(`  - **${type}**: ${count} instances`);
      }
    }
    lines.push('');

    lines.push('## Human Overrides');
    lines.push(`- Total overrides: ${summary.humanOverrides.total}`);
    lines.push(`- Active: ${summary.humanOverrides.active}`);
    lines.push(`- Expired: ${summary.humanOverrides.expired}`);
    lines.push(`- Average renewals: ${summary.humanOverrides.averageRenewals.toFixed(1)}`);

    if (summary.humanOverrides.mostOverriddenRule !== null) {
      lines.push(`- Most overridden rule: \`${summary.humanOverrides.mostOverriddenRule.ruleId}\` (${summary.humanOverrides.mostOverriddenRule.count} times)`);
      lines.push('- **Recommendation:** Consider adjusting rule threshold');
    }
    lines.push('');

    lines.push('## Economic Signals');
    lines.push(`- Total cost tracked: $${summary.economic.totalCost.toFixed(2)}`);
    lines.push(`- Average cost per decision: $${summary.economic.averageCostPerDecision.toFixed(2)}`);
    lines.push(`- Budget pressure: ${summary.economic.budgetPressure}`);

    if (summary.economic.budgetUtilization !== null) {
      lines.push(`- Budget utilization: ${(summary.economic.budgetUtilization * 100).toFixed(1)}%`);
    }
    lines.push('');

    lines.push('## Organizational Patterns');
    lines.push(`- Detected stage: **${summary.organizational.detectedStage}**`);
    lines.push(`- Confidence: ${(summary.organizational.stageConfidence * 100).toFixed(1)}%`);

    if (summary.organizational.keyIndicators.length > 0) {
      lines.push('- Key indicators:');
      for (const indicator of summary.organizational.keyIndicators) {
        lines.push(`  - ${indicator}`);
      }
    }

    if (summary.organizational.toolingMismatch !== null) {
      lines.push(`- **Tooling mismatch detected:** ${summary.organizational.toolingMismatch}`);
    }

    if (summary.organizational.recommendation !== null) {
      lines.push(`- **Recommendation:** ${summary.organizational.recommendation}`);
    } else {
      lines.push('- **Recommendation:** No tooling mismatch detected');
    }

    lines.push('');

    return lines.join('\n');
  }

  generateJSONReport(summary: CognitiveSummary): string {
    return JSON.stringify(summary, null, 2);
  }
}
