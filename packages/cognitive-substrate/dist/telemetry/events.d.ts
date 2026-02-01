export declare enum EventType {
    ASSERTION_CREATED = "assertion.created",
    BELIEF_UPDATED = "belief.updated",
    BELIEF_DECAYED = "belief.decayed",
    CONTRADICTION_DETECTED = "contradiction.detected",
    ECONOMIC_SIGNAL = "economic.signal",
    PATTERN_DETECTED = "pattern.detected",
    OVERRIDE_CREATED = "override.created",
    OVERRIDE_EXPIRED = "override.expired",
    DIVERGENCE_DETECTED = "divergence.detected",
    POLICY_VIOLATION = "policy.violation"
}
export interface TelemetryEvent {
    readonly eventType: EventType;
    readonly timestamp: string;
    readonly data: Record<string, unknown>;
    readonly metadata?: Record<string, unknown>;
}
export declare function createEvent(eventType: EventType, data: Record<string, unknown>, metadata?: Record<string, unknown>): TelemetryEvent;
//# sourceMappingURL=events.d.ts.map