export var EventType;
(function (EventType) {
    EventType["ASSERTION_CREATED"] = "assertion.created";
    EventType["BELIEF_UPDATED"] = "belief.updated";
    EventType["BELIEF_DECAYED"] = "belief.decayed";
    EventType["CONTRADICTION_DETECTED"] = "contradiction.detected";
    EventType["ECONOMIC_SIGNAL"] = "economic.signal";
    EventType["PATTERN_DETECTED"] = "pattern.detected";
    EventType["OVERRIDE_CREATED"] = "override.created";
    EventType["OVERRIDE_EXPIRED"] = "override.expired";
    EventType["DIVERGENCE_DETECTED"] = "divergence.detected";
    EventType["POLICY_VIOLATION"] = "policy.violation";
})(EventType || (EventType = {}));
export function createEvent(eventType, data, metadata) {
    return {
        eventType,
        timestamp: new Date().toISOString(),
        data,
        metadata
    };
}
//# sourceMappingURL=events.js.map