/**
 * @truthcore/cognitive-substrate
 *
 * Shared cognitive substrate for truth representation, belief formation,
 * and decision governance.
 *
 * @module
 */

// Primitives - explicit exports to avoid naming conflicts
export * from './primitives/assertion.js';
export * from './primitives/belief.js';
export {
  createDecision,
  conflictsWith,
  decisionToDict,
  decisionFromDict,
  isExpired as isDecisionExpired
} from './primitives/decision.js';
export type { Decision, DecisionInput, Authority } from './primitives/decision.js';
export { DecisionType } from './primitives/decision.js';
export * from './primitives/economic.js';
export {
  createEvidence,
  isStale as isEvidenceStale,
  evidenceToDict,
  evidenceFromDict
} from './primitives/evidence.js';
export type { Evidence, EvidenceInput } from './primitives/evidence.js';
export { EvidenceType } from './primitives/evidence.js';
export * from './primitives/meaning.js';
export * from './primitives/policy.js';

export * from './config/index.js';
export * from './graph/index.js';
export * from './governance/index.js';
export * from './economic/index.js';
export * from './learning/index.js';
export * from './telemetry/index.js';
export * from './utils/index.js';

export { SubstrateRuntime } from './substrate-runtime.js';
