import { SubstrateConfig, DEFAULT_CONFIG } from './config/substrate-config.js';
import { isAnyEnabled } from './config/flags.js';
import { MetricsCollector } from './telemetry/metrics.js';
import { EventType } from './telemetry/events.js';
import { ReportGenerator, CognitiveSummary } from './telemetry/reports.js';

import { AssertionGraph } from './graph/assertion-graph.js';
import { BeliefEngine, CompositionStrategy } from './graph/belief-engine.js';
import { ContradictionDetector } from './graph/contradiction.js';

import { HumanOverrideManager } from './governance/human-override.js';
import { ReconciliationEngine } from './governance/reconciliation.js';

import { EconomicSignalProcessor } from './economic/signal-processor.js';
import { EconomicInvariantEvaluator } from './economic/invariants.js';

import { PatternDetector } from './learning/pattern-detector.js';
import { detectStageGate, detectToolingMismatch, StageIndicators } from './learning/stage-gate.js';

import {
  Assertion,
  AssertionInput,
  createAssertion,
  Evidence,
  EvidenceInput,
  createEvidence,
  Belief,
  BeliefInput,
  Decision,
  DecisionInput,
  createDecision,
  EconomicSignal,
  EconomicSignalInput,
  createEconomicSignal,
  CognitivePolicy,
  MeaningVersion
} from './primitives/index.js';

/**
 * SubstrateRuntime - Main entry point for cognitive substrate
 *
 * Zero-cost abstraction when disabled. All methods check flags before any work.
 */
export class SubstrateRuntime {
  private config: SubstrateConfig;
  private _anyEnabled: boolean;

  private metrics: MetricsCollector;
  private reportGenerator: ReportGenerator;

  private assertionGraph: AssertionGraph;
  private beliefEngine: BeliefEngine;
  private contradictionDetector: ContradictionDetector;

  private overrideManager: HumanOverrideManager;
  private reconciliationEngine: ReconciliationEngine;

  private economicProcessor: EconomicSignalProcessor;
  // Economic evaluator for future invariant checking
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  private _economicEvaluator: EconomicInvariantEvaluator;

  private patternDetector: PatternDetector;

  constructor(config: SubstrateConfig = DEFAULT_CONFIG) {
    this.config = config;
    this._anyEnabled = isAnyEnabled(config.flags);

    this.metrics = new MetricsCollector(config.flags);
    this.reportGenerator = new ReportGenerator();

    this.assertionGraph = new AssertionGraph();
    this.beliefEngine = new BeliefEngine(this.assertionGraph);
    this.contradictionDetector = new ContradictionDetector(this.assertionGraph, this.beliefEngine);

    this.overrideManager = new HumanOverrideManager();
    this.reconciliationEngine = new ReconciliationEngine();

    this.economicProcessor = new EconomicSignalProcessor();
    this._economicEvaluator = new EconomicInvariantEvaluator();

    this.patternDetector = new PatternDetector();
  }

  // ========================================
  // ASSERTION & EVIDENCE
  // ========================================

  recordAssertion(input: AssertionInput): Assertion | null {
    if (!this._anyEnabled || !this.config.flags.assertionGraphEnabled) {
      return null;
    }

    const assertion = createAssertion(input);
    this.assertionGraph.addAssertion(assertion);

    this.metrics.emit(EventType.ASSERTION_CREATED, {
      assertion_id: assertion.assertionId,
      claim: assertion.claim,
      evidence_count: assertion.evidenceIds.length,
      source: assertion.source
    });

    return assertion;
  }

  recordEvidence(input: EvidenceInput): Evidence | null {
    if (!this._anyEnabled || !this.config.flags.assertionGraphEnabled) {
      return null;
    }

    const evidence = createEvidence(input);
    this.assertionGraph.addEvidence(evidence);

    return evidence;
  }

  getAssertion(assertionId: string): Assertion | undefined {
    return this.assertionGraph.getAssertion(assertionId);
  }

  getLineage(assertionId: string): ReturnType<AssertionGraph['getLineage']> {
    return this.assertionGraph.getLineage(assertionId);
  }

  // ========================================
  // BELIEFS
  // ========================================

  formBelief(input: BeliefInput): Belief | null {
    if (!this._anyEnabled || !this.config.flags.beliefEngineEnabled) {
      return null;
    }

    const belief = this.beliefEngine.formBelief({
      ...input,
      decayRate: input.decayRate ?? this.config.beliefDefaults.defaultDecayRate
    });

    this.metrics.emit(EventType.BELIEF_UPDATED, {
      belief_id: belief.beliefId,
      assertion_id: belief.assertionId,
      confidence: belief.confidence,
      version: belief.version
    });

    return belief;
  }

  updateBeliefConfidence(beliefId: string, newConfidence: number): Belief | null {
    if (!this._anyEnabled || !this.config.flags.beliefEngineEnabled) {
      return null;
    }

    const belief = this.beliefEngine.updateBeliefConfidence(beliefId, newConfidence);

    this.metrics.emit(EventType.BELIEF_UPDATED, {
      belief_id: belief.beliefId,
      confidence: belief.confidence,
      confidence_delta: newConfidence - belief.confidence,
      version: belief.version
    });

    return belief;
  }

  composeBeliefsForAssertion(assertionId: string, strategy: CompositionStrategy = CompositionStrategy.WEIGHTED_AVERAGE): number {
    if (!this._anyEnabled || !this.config.flags.beliefEngineEnabled) {
      return 0.0;
    }

    return this.beliefEngine.composeBeliefsForAssertion(assertionId, strategy);
  }

  propagateDecay(upstreamBeliefId: string): Belief[] {
    if (!this._anyEnabled || !this.config.flags.beliefEngineEnabled) {
      return [];
    }

    const decayThreshold = this.config.beliefDefaults.confidenceThresholds.medium;
    const updated = this.beliefEngine.propagateDecay(upstreamBeliefId, decayThreshold);

    for (const belief of updated) {
      this.metrics.emit(EventType.BELIEF_DECAYED, {
        belief_id: belief.beliefId,
        confidence: belief.confidence,
        upstream_belief_id: upstreamBeliefId
      });
    }

    return updated;
  }

  // ========================================
  // CONTRADICTIONS
  // ========================================

  detectContradictions(): void {
    if (!this._anyEnabled || !this.config.flags.contradictionDetection) {
      return;
    }

    const assertions = this.contradictionDetector.detectAssertionConflicts();

    for (const contradiction of assertions) {
      this.metrics.emit(EventType.CONTRADICTION_DETECTED, {
        contradiction_id: contradiction.contradictionId,
        type: contradiction.contradictionType,
        severity: contradiction.severity,
        conflicting_items: contradiction.conflictingItems.length
      });
    }
  }

  detectPolicyConflicts(policies: CognitivePolicy[]): void {
    if (!this._anyEnabled || !this.config.flags.contradictionDetection) {
      return;
    }

    const conflicts = this.contradictionDetector.detectPolicyConflicts(policies);

    for (const contradiction of conflicts) {
      this.metrics.emit(EventType.CONTRADICTION_DETECTED, {
        contradiction_id: contradiction.contradictionId,
        type: contradiction.contradictionType,
        severity: contradiction.severity
      });
    }
  }

  detectSemanticDrift(meanings: MeaningVersion[]): void {
    if (!this._anyEnabled || !this.config.flags.contradictionDetection) {
      return;
    }

    const drifts = this.contradictionDetector.detectSemanticDrift(meanings);

    for (const contradiction of drifts) {
      this.metrics.emit(EventType.CONTRADICTION_DETECTED, {
        contradiction_id: contradiction.contradictionId,
        type: contradiction.contradictionType,
        severity: contradiction.severity
      });
    }
  }

  // ========================================
  // DECISIONS & GOVERNANCE
  // ========================================

  recordDecision(input: DecisionInput): Decision | null {
    if (!this._anyEnabled) {
      return null;
    }

    const decision = createDecision(input);

    if (this.config.flags.patternDetection) {
      this.patternDetector.recordDecision(decision);
    }

    return decision;
  }

  createHumanOverride(
    originalDecision: Decision,
    overrideDecision: Decision,
    authority: { actor: string; scope: string; validUntil: string | null; requiresRenewal: boolean },
    scope: { scopeType: string; target: string; constraints: Record<string, unknown> },
    rationale: string,
    expiresAt: string
  ): ReturnType<HumanOverrideManager['createOverride']> | null {
    if (!this._anyEnabled || !this.config.flags.humanGovernance) {
      return null;
    }

    const override = this.overrideManager.createOverride({
      originalDecision,
      overrideDecision,
      authority,
      scope: scope as never,
      rationale,
      expiresAt
    });

    this.patternDetector.recordOverride(override);

    this.metrics.emit(EventType.OVERRIDE_CREATED, {
      override_id: override.overrideId,
      original_action: originalDecision.action,
      override_action: overrideDecision.action,
      expires_at: expiresAt
    });

    return override;
  }

  reconcile(systemBelief: Belief, humanOverride: ReturnType<HumanOverrideManager['createOverride']>): ReturnType<ReconciliationEngine['reconcile']> | null {
    if (!this._anyEnabled || !this.config.flags.humanGovernance) {
      return null;
    }

    const result = this.reconciliationEngine.reconcile(systemBelief, humanOverride);

    if (!result.aligned) {
      this.metrics.emit(EventType.DIVERGENCE_DETECTED, {
        system_belief_id: systemBelief.beliefId,
        human_decision_id: humanOverride.overrideDecision.decisionId,
        divergence_score: result.divergenceScore
      });
    }

    return result;
  }

  // ========================================
  // ECONOMIC
  // ========================================

  recordEconomicSignal(input: EconomicSignalInput): EconomicSignal | null {
    if (!this._anyEnabled || !this.config.flags.economicSignals) {
      return null;
    }

    const signal = createEconomicSignal(input);
    this.economicProcessor.recordSignal(signal);

    this.metrics.emit(EventType.ECONOMIC_SIGNAL, {
      signal_id: signal.signalId,
      signal_type: signal.signalType,
      amount: signal.amount,
      unit: signal.unit,
      applies_to: signal.appliesTo
    });

    return signal;
  }

  evaluateBudgetPressure(organizationId: string, budgetLimit: number | null = null): ReturnType<EconomicSignalProcessor['evaluateBudgetPressure']> | null {
    if (!this._anyEnabled || !this.config.flags.economicSignals) {
      return null;
    }

    return this.economicProcessor.evaluateBudgetPressure(organizationId, budgetLimit);
  }

  influenceBeliefWithEconomics(belief: Belief, signals: EconomicSignal[]): Belief | null {
    if (!this._anyEnabled || !this.config.flags.economicSignals) {
      return null;
    }

    return this.economicProcessor.influenceBelief(belief, signals);
  }

  // ========================================
  // LEARNING & PATTERNS
  // ========================================

  detectPatterns(organizationId: string, lookbackDays: number = 30): ReturnType<PatternDetector['detectUsagePatterns']> {
    if (!this._anyEnabled || !this.config.flags.patternDetection) {
      return [];
    }

    const patterns = this.patternDetector.detectUsagePatterns(organizationId, lookbackDays);

    for (const pattern of patterns) {
      this.metrics.emit(EventType.PATTERN_DETECTED, {
        pattern_id: pattern.patternId,
        pattern_type: pattern.patternType,
        frequency: pattern.frequency,
        confidence: pattern.confidence
      });
    }

    return patterns;
  }

  detectStageGate(indicators: StageIndicators, policies: CognitivePolicy[], decisions: Decision[]): ReturnType<typeof detectStageGate> | null {
    if (!this._anyEnabled || !this.config.flags.patternDetection) {
      return null;
    }

    const patterns = this.patternDetector.getAllPatterns();
    return detectStageGate(indicators, patterns, policies, decisions);
  }

  detectToolingMismatch(stageGate: ReturnType<typeof detectStageGate>, indicators: StageIndicators): ReturnType<typeof detectToolingMismatch> {
    if (!this._anyEnabled || !this.config.flags.patternDetection || stageGate === null) {
      return null;
    }

    return detectToolingMismatch(stageGate, indicators);
  }

  // ========================================
  // REPORTING
  // ========================================

  generateReport(organizationId: string, periodDays: number = 30): CognitiveSummary | null {
    if (!this._anyEnabled) {
      return null;
    }

    const stageGate = this.detectStageGate(
      {
        teamSize: 0,
        policyCount: 0,
        overrideRate: 0,
        deployFrequency: 0,
        avgDecisionTime: 0
      },
      [],
      []
    );

    return this.reportGenerator.generateCognitiveSummary(
      organizationId,
      periodDays,
      this.beliefEngine,
      this.contradictionDetector,
      this.overrideManager,
      this.economicProcessor,
      this.patternDetector,
      stageGate
    );
  }

  generateMarkdownReport(organizationId: string, periodDays: number = 30): string | null {
    const summary = this.generateReport(organizationId, periodDays);
    if (summary === null) {
      return null;
    }

    return this.reportGenerator.generateMarkdownReport(summary);
  }

  generateJSONReport(organizationId: string, periodDays: number = 30): string | null {
    const summary = this.generateReport(organizationId, periodDays);
    if (summary === null) {
      return null;
    }

    return this.reportGenerator.generateJSONReport(summary);
  }

  // ========================================
  // UTILITIES
  // ========================================

  stats(): {
    assertions: number;
    evidence: number;
    beliefs: ReturnType<BeliefEngine['stats']>;
    contradictions: ReturnType<ContradictionDetector['stats']>;
    overrides: ReturnType<HumanOverrideManager['stats']>;
    economic: ReturnType<EconomicSignalProcessor['stats']>;
    patterns: ReturnType<PatternDetector['stats']>;
    telemetry: ReturnType<MetricsCollector['stats']>;
  } {
    const graphSize = this.assertionGraph.size();

    return {
      assertions: graphSize.assertions,
      evidence: graphSize.evidence,
      beliefs: this.beliefEngine.stats(),
      contradictions: this.contradictionDetector.stats(),
      overrides: this.overrideManager.stats(),
      economic: this.economicProcessor.stats(),
      patterns: this.patternDetector.stats(),
      telemetry: this.metrics.stats()
    };
  }

  getMetrics(): MetricsCollector {
    return this.metrics;
  }

  getConfig(): SubstrateConfig {
    return this.config;
  }

  isEnabled(): boolean {
    return this._anyEnabled;
  }
}
