/**
 * Basic Usage Example - Cognitive Substrate
 *
 * Demonstrates how to use the cognitive substrate for truth representation,
 * belief formation, and decision governance.
 */

import {
  SubstrateRuntime,
  OBSERVE_ONLY_FLAGS,
  DEFAULT_CONFIG,
  EvidenceType,
  DecisionType,
  EconomicSignalType
} from '../src/index.js';

async function main(): Promise<void> {
  console.log('=== Cognitive Substrate - Basic Usage ===\n');

  const runtime = new SubstrateRuntime({
    ...DEFAULT_CONFIG,
    name: 'example-app',
    flags: OBSERVE_ONLY_FLAGS
  });

  console.log(`Substrate enabled: ${runtime.isEnabled()}\n`);

  console.log('1. Recording Evidence and Assertions\n');

  const evidence1 = runtime.recordEvidence({
    evidenceType: EvidenceType.DERIVED,
    content: { test_results: ['pass', 'pass', 'pass'] },
    source: 'test-runner'
  });

  const evidence2 = runtime.recordEvidence({
    evidenceType: EvidenceType.RAW,
    content: { coverage: 0.85 },
    source: 'coverage-tool'
  });

  console.log(`  Evidence 1: ${evidence1!.evidenceId.substring(0, 12)}`);
  console.log(`  Evidence 2: ${evidence2!.evidenceId.substring(0, 12)}\n`);

  const assertion = runtime.recordAssertion({
    claim: 'Deployment is ready',
    evidenceIds: [evidence1!.evidenceId, evidence2!.evidenceId],
    source: 'readiness-engine',
    transformation: 'aggregated test and coverage results'
  });

  console.log(`  Assertion: ${assertion!.assertionId.substring(0, 12)}`);
  console.log(`  Claim: "${assertion!.claim}"\n`);

  console.log('2. Forming Beliefs\n');

  const belief = runtime.formBelief({
    assertionId: assertion!.assertionId,
    confidence: 0.9,
    decayRate: 0.01
  });

  console.log(`  Belief: ${belief!.beliefId.substring(0, 12)}`);
  console.log(`  Confidence: ${belief!.confidence}`);
  console.log(`  Decay Rate: ${belief!.decayRate}\n`);

  console.log('3. Recording Economic Signals\n');

  const costSignal = runtime.recordEconomicSignal({
    signalType: EconomicSignalType.COST,
    amount: 45.0,
    unit: 'USD',
    source: 'billing-api',
    appliesTo: 'deployment-123'
  });

  console.log(`  Cost Signal: $${costSignal!.amount}`);
  console.log(`  Applies to: ${costSignal!.appliesTo}\n`);

  console.log('4. Making Decisions\n');

  const systemDecision = runtime.recordDecision({
    decisionType: DecisionType.SYSTEM,
    action: 'approve',
    rationale: [
      'High belief confidence (0.9)',
      'All tests passed',
      'Coverage above threshold',
      'Cost within budget'
    ],
    beliefIds: [belief!.beliefId]
  });

  console.log(`  Decision: ${systemDecision!.decisionId.substring(0, 12)}`);
  console.log(`  Type: ${systemDecision!.decisionType}`);
  console.log(`  Action: ${systemDecision!.action}`);
  console.log(`  Rationale:`);
  for (const reason of systemDecision!.rationale) {
    console.log(`    - ${reason}`);
  }
  console.log();

  console.log('5. Detecting Contradictions\n');

  runtime.recordAssertion({
    claim: 'Coverage is 72%',
    evidenceIds: [],
    source: 'alternate-coverage-tool'
  });

  runtime.detectContradictions();

  const contradictionStats = runtime.stats().contradictions;
  console.log(`  Total contradictions detected: ${contradictionStats.total}`);
  console.log(`  Unresolved: ${contradictionStats.unresolved}\n`);

  console.log('6. Generating Report\n');

  const markdownReport = runtime.generateMarkdownReport('example-org', 30);

  console.log(markdownReport!.split('\n').slice(0, 15).join('\n'));
  console.log('  ...\n');

  console.log('7. Stats Overview\n');

  const stats = runtime.stats();

  console.log(`  Assertions: ${stats.assertions}`);
  console.log(`  Evidence: ${stats.evidence}`);
  console.log(`  Beliefs: ${stats.beliefs.total}`);
  console.log(`    - High confidence: ${stats.beliefs.highConfidence}`);
  console.log(`    - Low confidence: ${stats.beliefs.lowConfidence}`);
  console.log(`    - Average: ${stats.beliefs.averageConfidence.toFixed(2)}`);
  console.log(`  Contradictions: ${stats.contradictions.total}`);
  console.log(`  Economic signals: ${stats.economic.totalSignals}`);
  console.log(`    - Total cost: $${stats.economic.totalCost.toFixed(2)}`);
  console.log(`  Telemetry events: ${stats.telemetry.totalEvents}\n`);

  console.log('=== Example Complete ===');
}

main().catch(console.error);
