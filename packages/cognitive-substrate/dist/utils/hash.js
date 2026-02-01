import { createHash } from 'crypto';
/**
 * Content-addressed hash utilities for deterministic identification
 */
export function hashObject(obj) {
    const normalized = JSON.stringify(obj, Object.keys(obj).sort());
    return createHash('sha256').update(normalized).digest('hex');
}
export function hashString(str) {
    return createHash('sha256').update(str).digest('hex');
}
export function generateId(prefix, data) {
    return `${prefix}_${hashObject(data).substring(0, 12)}`;
}
//# sourceMappingURL=hash.js.map