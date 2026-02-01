import { EnforcementMode } from '../primitives/policy.js';
export interface SubstrateFlags {
    enabled: boolean;
    assertionGraphEnabled: boolean;
    beliefEngineEnabled: boolean;
    contradictionDetection: boolean;
    humanGovernance: boolean;
    economicSignals: boolean;
    patternDetection: boolean;
    enforcementMode: EnforcementMode;
    telemetryEnabled: boolean;
    telemetrySamplingRate: number;
    replayEnabled: boolean;
    replayStoragePath: string | null;
}
export declare const DEFAULT_FLAGS: SubstrateFlags;
export declare const OBSERVE_ONLY_FLAGS: SubstrateFlags;
export declare const WARN_MODE_FLAGS: SubstrateFlags;
export declare const ENFORCE_MODE_FLAGS: SubstrateFlags;
export declare function createFlags(overrides?: Partial<SubstrateFlags>): SubstrateFlags;
export declare function isAnyEnabled(flags: SubstrateFlags): boolean;
//# sourceMappingURL=flags.d.ts.map