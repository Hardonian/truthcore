import { Assertion } from '../primitives/assertion.js';
import { Evidence } from '../primitives/evidence.js';
export interface AssertionLineage {
    rootAssertion: Assertion;
    upstreamAssertions: Assertion[];
    evidenceChain: Evidence[];
    transformations: string[];
}
export declare class AssertionGraph {
    private assertions;
    private evidence;
    private edges;
    addAssertion(assertion: Assertion): void;
    addEvidence(evidence: Evidence): void;
    getAssertion(assertionId: string): Assertion | undefined;
    getEvidence(evidenceId: string): Evidence | undefined;
    getLineage(assertionId: string): AssertionLineage | null;
    getAllAssertions(): Assertion[];
    getAllEvidence(): Evidence[];
    size(): {
        assertions: number;
        evidence: number;
    };
    clear(): void;
    toDict(): Record<string, unknown>;
}
//# sourceMappingURL=assertion-graph.d.ts.map