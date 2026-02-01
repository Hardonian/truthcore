import { createHash } from 'crypto';

/**
 * Content-addressed hash utilities for deterministic identification
 */

export function hashObject(obj: unknown): string {
  const normalized = JSON.stringify(obj, Object.keys(obj as object).sort());
  return createHash('sha256').update(normalized).digest('hex');
}

export function hashString(str: string): string {
  return createHash('sha256').update(str).digest('hex');
}

export function generateId(prefix: string, data: unknown): string {
  return `${prefix}_${hashObject(data).substring(0, 12)}`;
}
