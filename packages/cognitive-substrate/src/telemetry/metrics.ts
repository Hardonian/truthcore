import { SubstrateFlags } from '../config/flags.js';
import { TelemetryEvent, EventType, createEvent } from './events.js';

export type EventHandler = (event: TelemetryEvent) => void;

export class MetricsCollector {
  private flags: SubstrateFlags;
  private events: TelemetryEvent[] = [];
  private handlers: EventHandler[] = [];

  constructor(flags: SubstrateFlags) {
    this.flags = flags;
  }

  emit(eventType: EventType, data: Record<string, unknown>, metadata?: Record<string, unknown>): void {
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
      } catch (error) {
        // Telemetry failures should not break operations
        // In production, log to error tracking
      }
    }
  }

  subscribe(handler: EventHandler): () => void {
    this.handlers.push(handler);
    return () => {
      const index = this.handlers.indexOf(handler);
      if (index > -1) {
        this.handlers.splice(index, 1);
      }
    };
  }

  getEvents(filter?: { eventType?: EventType; since?: Date }): TelemetryEvent[] {
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

  clear(): void {
    this.events = [];
  }

  stats(): { totalEvents: number; eventsByType: Record<string, number> } {
    const eventsByType: Record<string, number> = {};

    for (const event of this.events) {
      eventsByType[event.eventType] = (eventsByType[event.eventType] ?? 0) + 1;
    }

    return {
      totalEvents: this.events.length,
      eventsByType
    };
  }
}
