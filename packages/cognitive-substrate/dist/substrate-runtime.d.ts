import { SubstrateConfig } from './config/substrate-config.js';
import { MetricsCollector } from './telemetry/metrics.js';
import { CognitiveSummary } from './telemetry/reports.js';
import { AssertionGraph } from './graph/assertion-graph.js';
import { BeliefEngine, CompositionStrategy } from './graph/belief-engine.js';
import { ContradictionDetector } from './graph/contradiction.js';
import { HumanOverrideManager } from './governance/human-override.js';
import { ReconciliationEngine } from './governance/reconciliation.js';
import { EconomicSignalProcessor } from './economic/signal-processor.js';
import { PatternDetector } from './learning/pattern-detector.js';
import { detectStageGate, detectToolingMismatch, StageIndicators } from './learning/stage-gate.js';
import { Assertion, AssertionInput, Evidence, EvidenceInput, Belief, BeliefInput, Decision, DecisionInput, EconomicSignal, EconomicSignalInput, CognitivePolicy, MeaningVersion } from './primitives/index.js';
/**
 * SubstrateRuntime - Main entry point for cognitive substrate
 *
 * Zero-cost abstraction when disabled. All methods check flags before any work.
 */
export declare class SubstrateRuntime {
    private config;
    private _anyEnabled;
    private metrics;
    private reportGenerator;
    private assertionGraph;
    private beliefEngine;
    private contradictionDetector;
    private overrideManager;
    private reconciliationEngine;
    private economicProcessor;
    private _economicEvaluator;
    private patternDetector;
    constructor(config?: SubstrateConfig);
    recordAssertion(input: AssertionInput): Assertion | null;
    recordEvidence(input: EvidenceInput): Evidence | null;
    getAssertion(assertionId: string): Assertion | undefined;
    getLineage(assertionId: string): ReturnType<AssertionGraph['getLineage']>;
    formBelief(input: BeliefInput): Belief | null;
    updateBeliefConfidence(beliefId: string, newConfidence: number): Belief | null;
    composeBeliefsForAssertion(assertionId: string, strategy?: CompositionStrategy): number;
    propagateDecay(upstreamBeliefId: string): Belief[];
    detectContradictions(): void;
    detectPolicyConflicts(policies: CognitivePolicy[]): void;
    detectSemanticDrift(meanings: MeaningVersion[]): void;
    recordDecision(input: DecisionInput): Decision | null;
    createHumanOverride(originalDecision: Decision, overrideDecision: Decision, authority: {
        actor: string;
        scope: string;
        validUntil: string | null;
        requiresRenewal: boolean;
    }, scope: {
        scopeType: string;
        target: string;
        constraints: Record<string, unknown>;
    }, rationale: string, expiresAt: string): ReturnType<HumanOverrideManager['createOverride']> | null;
    reconcile(systemBelief: Belief, humanOverride: ReturnType<HumanOverrideManager['createOverride']>): ReturnType<ReconciliationEngine['reconcile']> | null;
    recordEconomicSignal(input: EconomicSignalInput): EconomicSignal | null;
    evaluateBudgetPressure(organizationId: string, budgetLimit?: number | null): ReturnType<EconomicSignalProcessor['evaluateBudgetPressure']> | null;
    influenceBeliefWithEconomics(belief: Belief, signals: EconomicSignal[]): Belief | null;
    detectPatterns(organizationId: string, lookbackDays?: number): ReturnType<PatternDetector['detectUsagePatterns']>;
    detectStageGate(indicators: StageIndicators, policies: CognitivePolicy[], decisions: Decision[]): ReturnType<typeof detectStageGate> | null;
    detectToolingMismatch(stageGate: ReturnType<typeof detectStageGate>, indicators: StageIndicators): ReturnType<typeof detectToolingMismatch>;
    generateReport(organizationId: string, periodDays?: number): CognitiveSummary | null;
    generateMarkdownReport(organizationId: string, periodDays?: number): string | null;
    generateJSONReport(organizationId: string, periodDays?: number): string | null;
    stats(): {
        assertions: number;
        evidence: number;
        beliefs: ReturnType<BeliefEngine['stats']>;
        contradictions: ReturnType<ContradictionDetector['stats']>;
        overrides: ReturnType<HumanOverrideManager['stats']>;
        economic: ReturnType<EconomicSignalProcessor['stats']>;
        patterns: ReturnType<PatternDetector['stats']>;
        telemetry: ReturnType<MetricsCollector['stats']>;
    };
    getMetrics(): MetricsCollector;
    getConfig(): SubstrateConfig;
    isEnabled(): boolean;
}
//# sourceMappingURL=substrate-runtime.d.ts.map