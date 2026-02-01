export interface Assertion {
    readonly assertionId: string;
    readonly claim: string;
    readonly evidenceIds: readonly string[];
    readonly transformation: string | null;
    readonly source: string;
    readonly timestamp: string;
    readonly metadata: Record<string, unknown>;
}
export interface AssertionInput {
    claim: string;
    evidenceIds: string[];
    transformation?: string | null;
    source: string;
    metadata?: Record<string, unknown>;
}
export declare function createAssertion(input: AssertionInput): Assertion;
export declare function assertionToDict(assertion: Assertion): Record<string, unknown>;
export declare function assertionFromDict(data: Record<string, unknown>): Assertion;
//# sourceMappingURL=assertion.d.ts.map