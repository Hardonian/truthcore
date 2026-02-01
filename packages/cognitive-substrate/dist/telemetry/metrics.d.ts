import { SubstrateFlags } from '../config/flags.js';
import { TelemetryEvent, EventType } from './events.js';
export type EventHandler = (event: TelemetryEvent) => void;
export declare class MetricsCollector {
    private flags;
    private events;
    private handlers;
    constructor(flags: SubstrateFlags);
    emit(eventType: EventType, data: Record<string, unknown>, metadata?: Record<string, unknown>): void;
    subscribe(handler: EventHandler): () => void;
    getEvents(filter?: {
        eventType?: EventType;
        since?: Date;
    }): TelemetryEvent[];
    clear(): void;
    stats(): {
        totalEvents: number;
        eventsByType: Record<string, number>;
    };
}
//# sourceMappingURL=metrics.d.ts.map