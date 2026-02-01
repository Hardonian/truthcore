import { createEvent } from './events.js';
export class MetricsCollector {
    flags;
    events = [];
    handlers = [];
    constructor(flags) {
        this.flags = flags;
    }
    emit(eventType, data, metadata) {
        if (!this.flags.telemetryEnabled) {
            return;
        }
        if (Math.random() > this.flags.telemetrySamplingRate) {
            return;
        }
        const event = createEvent(eventType, data, metadata);
        this.events.push(event);
        for (const handler of this.handlers) {
            try {
                handler(event);
            }
            catch (error) {
                // Telemetry failures should not break operations
                // In production, log to error tracking
            }
        }
    }
    subscribe(handler) {
        this.handlers.push(handler);
        return () => {
            const index = this.handlers.indexOf(handler);
            if (index > -1) {
                this.handlers.splice(index, 1);
            }
        };
    }
    getEvents(filter) {
        let filtered = this.events;
        if (filter?.eventType !== undefined) {
            filtered = filtered.filter((e) => e.eventType === filter.eventType);
        }
        if (filter?.since !== undefined) {
            const since = filter.since;
            filtered = filtered.filter((e) => new Date(e.timestamp) >= since);
        }
        return filtered;
    }
    clear() {
        this.events = [];
    }
    stats() {
        const eventsByType = {};
        for (const event of this.events) {
            eventsByType[event.eventType] = (eventsByType[event.eventType] ?? 0) + 1;
        }
        return {
            totalEvents: this.events.length,
            eventsByType
        };
    }
}
//# sourceMappingURL=metrics.js.map