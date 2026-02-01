/**
 * Core type definitions for Truth Core Dashboard
 * All types mirror the Python data structures exactly
 */

// Severity levels
export type Severity = 'BLOCKER' | 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO';

// Verdict states
export type VerdictState = 'PASS' | 'FAIL' | 'CONDITIONAL';

// Finding structure
export interface Finding {
  id: string;
  severity: Severity;
  category: string;
  engine: string;
  rule: string;
  message: string;
  file?: string;
  line?: number;
  column?: number;
  context?: Record<string, unknown>;
}

// Verdict structure
export interface VerdictData {
  version: string;
  timestamp: string;
  run_id: string;
  verdict: VerdictState;
  score: number;
  threshold: number;
  total_findings: number;
  findings_by_severity: Record<Severity, number>;
  findings: Finding[];
  subscores?: {
    security?: number;
    quality?: number;
    performance?: number;
    style?: number;
  };
}

// Run manifest structure
export interface RunManifest {
  version: string;
  run_id: string;
  command: string;
  timestamp: string;
  duration_ms: number;
  profile: string;
  config: Record<string, unknown>;
  input_hash: string;
  config_hash: string;
  cache_key?: string;
  cache_hit?: boolean;
  metadata: Record<string, unknown>;
}

// Readiness data
export interface ReadinessData {
  version: string;
  timestamp: string;
  profile: string;
  passed: boolean;
  score?: number;
  findings: ReadinessFinding[];
}

export interface ReadinessFinding {
  id: string;
  check: string;
  passed: boolean;
  severity?: Severity;
  message?: string;
}

// Invariant data
export interface InvariantData {
  version: string;
  timestamp: string;
  results: InvariantResult[];
}

export interface InvariantResult {
  rule_id: string;
  name: string;
  passed: boolean;
  severity: Severity;
  message?: string;
  explanation?: string;
}

// Policy data
export interface PolicyData {
  version: string;
  timestamp: string;
  pack_name: string;
  rules_evaluated: number;
  rules_triggered: number;
  findings: PolicyFinding[];
}

export interface PolicyFinding {
  rule_id: string;
  severity: Severity;
  message: string;
  file?: string;
  redacted?: boolean;
}

// Provenance data
export interface ProvenanceData {
  version: string;
  timestamp: string;
  bundle_hash: string;
  files: ProvenanceFile[];
  signature?: {
    algorithm: string;
    public_key_fingerprint: string;
    signature: string;
  };
}

export interface ProvenanceFile {
  path: string;
  hash: string;
  algorithm: string;
  size: number;
}

// Intel scorecard
export interface IntelScorecard {
  version: string;
  timestamp: string;
  mode: string;
  score: number;
  history_count: number;
  trends: {
    improving: string[];
    degrading: string[];
    stable: string[];
  };
}

// Complete run data structure
export interface RunData {
  run_id: string;
  manifest: RunManifest;
  verdict?: VerdictData;
  readiness?: ReadinessData;
  invariants?: InvariantData;
  policy?: PolicyData;
  provenance?: ProvenanceData;
  intel_scorecard?: IntelScorecard;
  files: string[];
}

// Dashboard state
export interface DashboardState {
  runsDir: string | null;
  runs: RunData[];
  selectedRunId: string | null;
  theme: 'light' | 'dark';
  view: 'runs' | 'run-detail' | 'settings';
}

// Filter state
export interface FilterState {
  severity: Severity[];
  category: string[];
  engine: string[];
  search: string;
}
