/**
 * Truth Core Contract Types
 *
 * TypeScript definitions for truth-core contract artifacts.
 * Supports both v1 and v2 verdict formats with full backward compatibility.
 *
 * @module @truth-core/contract-sdk/types
 */

// ============================================================================
// Contract Metadata
// ============================================================================

/**
 * Contract metadata present in all truth-core artifacts.
 * Identifies the artifact type, version, and provenance.
 */
export interface ContractMetadata {
  /** Type of artifact (e.g., "verdict", "readiness") */
  artifact_type: string;
  /** Contract version following semver */
  contract_version: string;
  /** Version of truth-core that produced this artifact */
  truthcore_version: string;
  /** Optional engine versions used */
  engine_versions?: Record<string, string>;
  /** ISO 8601 timestamp when artifact was created */
  created_at: string;
  /** Path or URL to the JSON schema */
  schema: string;
}

// ============================================================================
// Severity Levels
// ============================================================================

/**
 * Severity levels for findings and checks.
 * Ordered from most to least severe.
 */
export type SeverityLevel = "BLOCKER" | "HIGH" | "MEDIUM" | "LOW" | "INFO";

/**
 * Verdict states.
 */
export type VerdictState = "PASS" | "FAIL" | "WARN" | "UNKNOWN";

// ============================================================================
// Finding (v1) / Item (v2)
// ============================================================================

/**
 * A single finding or item in a verdict.
 * Represents one observation, issue, or piece of evidence.
 */
export interface Finding {
  /** Unique identifier for this finding */
  id: string;
  /** Severity level */
  severity: SeverityLevel;
  /** Human-readable message describing the finding */
  message: string;
  /** Optional category for grouping */
  category?: string;
  /** Optional name of the engine that produced this finding */
  engine?: string;
  /** Optional source reference (file, line, URL, etc.) */
  source?: string;
  /** Optional confidence score (0-1) */
  confidence?: number;
}

// ============================================================================
// Verdict v1.0.0
// ============================================================================

/**
 * Verdict artifact format v1.0.0
 * @deprecated Use VerdictV2 for new implementations
 */
export interface VerdictV1 {
  /** Contract metadata */
  _contract: ContractMetadata & { contract_version: "1.0.0"; artifact_type: "verdict" };
  /** Overall verdict state */
  verdict: VerdictState;
  /** Overall score (0-100) */
  score: number;
  /** Array of findings */
  findings: Finding[];
  /** Optional metadata */
  metadata?: Record<string, unknown>;
  /** Optional engine-specific outputs */
  engine_outputs?: Record<string, unknown>;
}

// ============================================================================
// Verdict v2.0.0
// ============================================================================

/**
 * Verdict artifact format v2.0.0
 * Current recommended format with confidence scores.
 */
export interface VerdictV2 {
  /** Contract metadata */
  _contract: ContractMetadata & { contract_version: "2.0.0"; artifact_type: "verdict" };
  /** Overall verdict state */
  verdict: VerdictState;
  /** Overall value/score (0-100), renamed from 'score' in v1 */
  value: number;
  /** Confidence in the verdict (0-1) */
  confidence: number;
  /** Array of items (renamed from 'findings' in v1) */
  items: Finding[];
  /** Optional references to supporting evidence */
  evidence_refs?: string[];
  /** Optional metadata */
  metadata?: Record<string, unknown>;
  /** Optional engine-specific outputs */
  engine_outputs?: Record<string, unknown>;
}

/**
 * Union type for all Verdict versions.
 * Can be narrowed using `_contract.contract_version`.
 */
export type Verdict = VerdictV1 | VerdictV2;

// ============================================================================
// Readiness Check
// ============================================================================

/**
 * Individual readiness check result.
 */
export interface ReadinessCheck {
  /** Name of the check */
  name: string;
  /** Whether the check passed */
  passed: boolean;
  /** Optional human-readable message */
  message?: string;
  /** Optional detailed information */
  details?: Record<string, unknown>;
}

/**
 * Readiness check artifact format v1.0.0
 */
export interface ReadinessV1 {
  /** Contract metadata */
  _contract: ContractMetadata & { artifact_type: "readiness" };
  /** Whether the system is ready */
  ready: boolean;
  /** Array of individual checks */
  checks: ReadinessCheck[];
  /** Optional summary message */
  summary?: string;
}

/**
 * Union type for all Readiness versions.
 */
export type Readiness = ReadinessV1;

// ============================================================================
// Generic Artifact Types
// ============================================================================

/**
 * Union of all truth-core artifact types.
 */
export type TruthCoreArtifact = Verdict | Readiness;

/**
 * Type guard to check if an artifact is a Verdict.
 */
export function isVerdict(artifact: TruthCoreArtifact): artifact is Verdict {
  return artifact._contract.artifact_type === "verdict";
}

/**
 * Type guard to check if an artifact is a Readiness check.
 */
export function isReadiness(artifact: TruthCoreArtifact): artifact is Readiness {
  return artifact._contract.artifact_type === "readiness";
}

/**
 * Type guard to check if a Verdict is v2 format.
 */
export function isVerdictV2(verdict: Verdict): verdict is VerdictV2 {
  return verdict._contract.contract_version === "2.0.0";
}

/**
 * Type guard to check if a Verdict is v1 format.
 */
export function isVerdictV1(verdict: Verdict): verdict is VerdictV1 {
  return verdict._contract.contract_version === "1.0.0";
}
