import { EnforcementMode } from '../primitives/policy.js';
export const DEFAULT_FLAGS = {
    enabled: false,
    assertionGraphEnabled: false,
    beliefEngineEnabled: false,
    contradictionDetection: false,
    humanGovernance: false,
    economicSignals: false,
    patternDetection: false,
    enforcementMode: EnforcementMode.OBSERVE,
    telemetryEnabled: true,
    telemetrySamplingRate: 0.1,
    replayEnabled: false,
    replayStoragePath: null
};
export const OBSERVE_ONLY_FLAGS = {
    enabled: true,
    assertionGraphEnabled: true,
    beliefEngineEnabled: true,
    contradictionDetection: true,
    humanGovernance: false,
    economicSignals: false,
    patternDetection: true,
    enforcementMode: EnforcementMode.OBSERVE,
    telemetryEnabled: true,
    telemetrySamplingRate: 1.0,
    replayEnabled: false,
    replayStoragePath: null
};
export const WARN_MODE_FLAGS = {
    ...OBSERVE_ONLY_FLAGS,
    humanGovernance: true,
    economicSignals: true,
    enforcementMode: EnforcementMode.WARN
};
export const ENFORCE_MODE_FLAGS = {
    ...WARN_MODE_FLAGS,
    enforcementMode: EnforcementMode.BLOCK,
    replayEnabled: true
};
export function createFlags(overrides) {
    return {
        ...DEFAULT_FLAGS,
        ...overrides
    };
}
export function isAnyEnabled(flags) {
    return (flags.enabled &&
        (flags.assertionGraphEnabled ||
            flags.beliefEngineEnabled ||
            flags.contradictionDetection ||
            flags.humanGovernance ||
            flags.economicSignals ||
            flags.patternDetection));
}
//# sourceMappingURL=flags.js.map